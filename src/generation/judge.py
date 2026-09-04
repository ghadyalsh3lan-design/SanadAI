"""
LLM-as-a-Judge evaluation for Ask-page answers.

Given a question, the generated answer, and the retrieved context, an LLM scores
the answer on faithfulness, relevance, completeness, groundedness, citation
quality, and whether it hallucinates. Used by the Ask page's "Evaluate" button.

Provider-agnostic: uses config.get_llm(), so it judges with whatever provider is
configured. The response is parsed defensively from JSON because not every
provider reliably supports structured output.
"""
import json
import re

from pydantic import BaseModel, Field

from src import config

_SYSTEM_PROMPT = """You are an expert evaluator of RAG QA systems.

Evaluate the ANSWER based on the CONTEXT.

Score each metric from 0 to 10:

1. **Faithfulness** — Is the answer factually consistent with the context? No hallucinations?
2. **Relevance** — Does the answer directly address the question?
3. **Completeness** — Does the answer cover all relevant aspects from the context?
4. **Groundedness** — Is every claim in the answer supported by the provided context?
5. **Citation Quality** — Are sources properly referenced and accurate?
6. **Hallucination** - Does the answer contain hallucination?

Return your evaluation as a JSON object with this EXACT structure (no extra text):

{
    "scores": {
        "faithfulness": <0-10>,
        "relevance": <0-10>,
        "completeness": <0-10>,
        "groundedness": <0-10>,
        "citation_quality": <0-10>,
        "hallucination": <0 | 10>
    },
    "summary": "<2-3 sentence overall assessment>",
    "recommendations": ["<improvement suggestion 1>", "<improvement suggestion 2>"]
}
"""


class EvaluationScores(BaseModel):
    """Per-metric scores from the LLM judge (0-10, hallucination is 0/10)."""
    faithfulness: float = 0.0
    relevance: float = 0.0
    completeness: float = 0.0
    groundedness: float = 0.0
    citation_quality: float = 0.0
    hallucination: int = 0


class EvaluationResponse(BaseModel):
    """Full judge result: scores, a summary, and improvement suggestions."""
    scores: EvaluationScores = Field(default_factory=EvaluationScores)
    summary: str = ""
    recommendations: list[str] = Field(default_factory=list)


_SCORE_KEYS = (
    "faithfulness", "relevance", "completeness",
    "groundedness", "citation_quality", "hallucination",
)


def _strip_json_noise(text: str) -> str:
    """Pull JSON out of a model reply and remove things json.loads rejects.

    Small models often wrap JSON in code fences, add `//` or `/* */` comments,
    or leave trailing commas. Strip all of that and isolate the outermost object.
    """
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0]

    cleaned = re.sub(r"//[^\n]*", "", cleaned)          # // line comments
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)  # /* block */
    cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)    # trailing commas

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        cleaned = cleaned[start:end + 1]
    return cleaned.strip()


def _scores_by_regex(text: str) -> EvaluationScores:
    """Last-resort extraction: pull each numeric score even from broken/truncated
    JSON so the UI shows real numbers instead of all zeros."""
    values: dict[str, float] = {}
    for key in _SCORE_KEYS:
        m = re.search(rf'"{key}"\s*:\s*([0-9]+(?:\.[0-9]+)?)', text)
        if m:
            values[key] = float(m.group(1))
    return EvaluationScores(
        faithfulness=values.get("faithfulness", 0.0),
        relevance=values.get("relevance", 0.0),
        completeness=values.get("completeness", 0.0),
        groundedness=values.get("groundedness", 0.0),
        citation_quality=values.get("citation_quality", 0.0),
        hallucination=int(values.get("hallucination", 0)),
    )


def _parse_response(text: str) -> EvaluationResponse:
    """Parse the LLM's JSON response, tolerating fences, comments, trailing
    commas, and truncation."""
    cleaned = _strip_json_noise(text)
    try:
        data = json.loads(cleaned)
        scores_data = data.get("scores", {})
        scores = EvaluationScores(
            faithfulness=float(scores_data.get("faithfulness", 0)),
            relevance=float(scores_data.get("relevance", 0)),
            completeness=float(scores_data.get("completeness", 0)),
            groundedness=float(scores_data.get("groundedness", 0)),
            citation_quality=float(scores_data.get("citation_quality", 0)),
            hallucination=int(scores_data.get("hallucination", 0)),
        )
        return EvaluationResponse(
            scores=scores,
            summary=data.get("summary", ""),
            recommendations=data.get("recommendations", []),
        )
    except (json.JSONDecodeError, KeyError, ValueError, IndexError):
        # Truncated or malformed JSON — salvage from the raw text by regex (the
        # cleaned string may have been trimmed at the inner "scores" brace).
        scores = _scores_by_regex(text)
        m = re.search(r'"summary"\s*:\s*"([^"]*)', text)
        summary = m.group(1).strip() if m else "Evaluation returned malformed output."
        return EvaluationResponse(scores=scores, summary=summary, recommendations=[])


def evaluate_answer(
    question: str,
    answer: str,
    context: list[str],
    citations: list[dict] | None = None,
) -> EvaluationResponse:
    """Run LLM-as-a-Judge evaluation on a QA result."""
    context_text = "\n\n---\n\n".join(context) if context else "(no context provided)"
    citations_text = json.dumps(citations or [], indent=2, ensure_ascii=False)

    prompt = (
        f"**Question:** {question}\n\n"
        f"**Answer:** {answer}\n\n"
        f"**Context:**\n{context_text}\n\n"
        f"**Citations:**\n{citations_text}\n\n"
        f"Evaluate this answer now."
    )

    try:
        llm = config.get_llm()
        response = llm.invoke(
            [
                ("system", config.date_prefix() + _SYSTEM_PROMPT),
                ("human", prompt),
            ]
        )
        return _parse_response(response.content)
    except Exception as exc:
        return EvaluationResponse(
            summary=f"Evaluation failed: {exc}",
            recommendations=["Retry evaluation or check LLM connectivity."],
        )
