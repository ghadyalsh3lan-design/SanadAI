"""
Pre-bid RFP analysis for the RFP Intelligence System.

Takes the full text of an incoming RFP and a loaded company KB vector store.
Returns a structured report: requirement coverage table + severity-tagged
clarifying questions.

Design:
  - Step 1: Extract all requirements from the RFP as a structured list.
  - Step 2: For each requirement, search the company KB and assess coverage.
  - Step 3: Generate clarifying questions with severity tags.
  - Step 4: Assemble and return the PreBidAnalysis report.

Coverage levels: fully_covered, partially_covered, not_covered.
Severity tags: blocker, important, nice_to_clarify.
"""
import re
from typing import Literal

from langchain_chroma import Chroma
from pydantic import BaseModel, Field

from src import config
from src.retrieval.vector_store import search_with_scores, rerank, DEFAULT_RELEVANCE_THRESHOLD

DEFAULT_MODEL = None  # None → use the configured provider's default model
# All overridable via .env (see .env.example).
# Cap how many requirements we assess to avoid excessive API calls on large RFPs
MAX_REQUIREMENTS = config.env_int("BID_MAX_REQUIREMENTS", 10)
# How many KB chunks to retrieve per requirement for coverage assessment
RETRIEVAL_K = config.env_int("BID_RETRIEVAL_K_PER_REQ", 4)
# How many company-KB chunks to retrieve for the overall bid recommendation
BID_RETRIEVAL_K = config.env_int("BID_RETRIEVAL_K", 12)
# Truncate RFP text sent to LLM to stay within context limits
RFP_TEXT_LIMIT = config.env_int("RFP_TEXT_LIMIT", 14000)


# ---------------------------------------------------------------------------
# Output models (returned to callers and serialised by FastAPI)
# ---------------------------------------------------------------------------

class RequirementCoverage(BaseModel):
    """Coverage assessment for a single RFP requirement."""
    requirement: str = Field(description="The requirement as extracted from the RFP")
    coverage: Literal["fully_covered", "partially_covered", "not_covered"] = Field(
        description="How well the company KB covers this requirement"
    )
    evidence: str = Field(
        description="Quote or summary from the KB that supports the coverage level"
    )
    source: str | None = Field(
        default=None,
        description="Filename of the KB document the evidence came from"
    )
    relevance: float | None = Field(
        default=None,
        description="Relevance score (0-1) of the strongest matching KB chunk",
    )
    comply: Literal["yes", "partial", "no"] | None = Field(
        default=None,
        description="User's compliance decision: yes / partial / no bid"
    )


class ClarifyingQuestion(BaseModel):
    """A question to ask the client before committing to a bid."""
    question: str = Field(description="The clarifying question")
    severity: Literal["blocker", "important", "nice_to_clarify"] = Field(
        description=(
            "blocker = must know before bidding; "
            "important = affects scope or pricing; "
            "nice_to_clarify = useful but not critical"
        )
    )


class CoverageSummary(BaseModel):
    """Counts of requirements at each coverage level."""
    fully_covered: int
    partially_covered: int
    not_covered: int


class DetailedAnalysis(BaseModel):
    """Per-area assessment behind the overall bid recommendation."""
    submission_deadline: str = ""
    project_scope: str = ""
    eligibility: str = ""
    required_documents: str = ""
    exclusion_criteria: str = ""
    technical_capability: str = ""
    relevant_experience: str = ""
    resource_availability: str = ""


class BidRecommendation(BaseModel):
    """Overall bid/no-bid recommendation for an RFP."""
    recommendation: Literal["Bid", "No Bid", "Bid with Risks"] = Field(
        description="Overall recommendation on whether to pursue the bid"
    )
    confidence: float = Field(
        description="Confidence in the recommendation, from 0.0 to 1.0"
    )
    strengths: list[str] = Field(
        default_factory=list, description="Reasons this is a good fit"
    )
    risks: list[str] = Field(
        default_factory=list, description="Risks or gaps that threaten the bid"
    )
    missing_requirements: list[str] = Field(
        default_factory=list,
        description="Mandatory requirements the company appears unable to meet",
    )
    detailed_analysis: DetailedAnalysis = Field(
        default_factory=DetailedAnalysis,
        description="Assessment across the eight bid-decision areas",
    )
    summary: str = Field(
        default="", description="3-5 sentence overall recommendation with reasoning"
    )


class PreBidAnalysis(BaseModel):
    """Full pre-bid analysis report for an RFP."""
    rfp_filename: str
    requirements: list[RequirementCoverage]
    clarifying_questions: list[ClarifyingQuestion]
    coverage_summary: CoverageSummary
    bid_recommendation: BidRecommendation | None = None


# ---------------------------------------------------------------------------
# Internal structured-output helpers (not exposed outside this module)
# ---------------------------------------------------------------------------

class _RequirementList(BaseModel):
    requirements: list[str]


class _CoverageAssessment(BaseModel):
    # The LLM judges coverage and summarises evidence, but it does NOT name the
    # source — that comes from the retrieved chunk's metadata so the citation is
    # grounded in what we actually retrieved, never invented.
    coverage: Literal["fully_covered", "partially_covered", "not_covered"]
    evidence: str


class _ClarifyingQuestionList(BaseModel):
    questions: list[ClarifyingQuestion]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_EXTRACT_PROMPT = """You are analyzing an RFP document to extract all distinct requirements.

Identify every technical, functional, operational, and compliance requirement — both explicit and implied.
Write each as a single clear, complete sentence in plain text. Include constraints, standards, timelines, and deliverables where stated.

Strict output rules:
- Each item must be a self-contained requirement sentence — never a section heading, table separator, or fragment.
- Do not include Markdown or HTML (no "**", "#", "<br>", "|", table pipes, etc.) — plain text only.
- Do not return empty strings or placeholder items.

RFP content:
{rfp_text}

Return a structured list of all requirements."""


_COVERAGE_PROMPT = """You are assessing whether a consulting firm can fulfill an RFP requirement based on their past work.

Requirement:
{requirement}

Evidence from company knowledge base:
{context}

Assess coverage:
- "fully_covered": Past work clearly and directly demonstrates meeting this requirement
- "partially_covered": Relevant experience exists but does not fully address the requirement
- "not_covered": No relevant evidence found in the knowledge base

Provide a brief evidence quote or summary (1-2 sentences). If not covered, write "No relevant evidence found.\""""


_QUESTIONS_PROMPT = """You are a senior proposal consultant reviewing an RFP before deciding whether to bid.

Generate 5-10 clarifying questions the firm must ask the client.

Tag each question with a severity:
- "blocker": Must know before bidding — ambiguity could cause the firm to misprice or be disqualified
- "important": Significantly affects scope, timeline, or technical approach
- "nice_to_clarify": Useful context but not critical to the bid decision

RFP content:
{rfp_text}

Return a structured list of clarifying questions."""


_BID_SYSTEM_PROMPT = """You are SanadAI, an expert bid/no-bid analysis assistant.

Analyze the RFP against the company's knowledge base and provide a comprehensive
bid recommendation.

Evaluate the following 8 areas:
1. Submission deadline — Is there enough time?
2. Project scope alignment — Does this match our expertise?
3. Eligibility requirements — Do we meet all mandatory criteria?
4. Required documents — Can we provide all required documents?
5. Exclusion criteria — Are there any disqualifying factors?
6. Technical capability — Do we have the technical skills?
7. Relevant experience — Do we have relevant past projects?
8. Resource availability — Do we have the team and resources?

Base every judgement only on the provided RFP content and company knowledge base.
- For the submission deadline, compare every date in the RFP against today's date
  (stated above). If the submission deadline has already passed, say so explicitly,
  treat it as a blocking issue, and lean toward "No Bid" — never describe a past
  deadline as leaving time to prepare.
- recommendation must be exactly one of: "Bid", "No Bid", "Bid with Risks".
- confidence is a number from 0.0 to 1.0.
- strengths, risks, and missing_requirements are short, concrete bullet points.
- detailed_analysis must contain a 1-2 sentence assessment for each of the eight
  areas.
- summary is a 3-5 sentence overall recommendation with reasoning.
If the company knowledge base is empty or irrelevant, lean toward "No Bid" with
low confidence and say so."""


_BID_HUMAN_PROMPT = """## RFP Content
{rfp_text}

## Company Knowledge Base
{company_context}

Perform a bid/no-bid analysis now."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _clean_requirements(raw: list[str]) -> list[str]:
    """Drop empty/fragment requirements and strip markdown/HTML artifacts.

    The extractor sometimes returns blank items or table/heading fragments when
    the RFP is heavy on Markdown tables or <br> tags. Keep only real, plain-text
    requirement sentences, de-duplicated in order.
    """
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = re.sub(r"<br\s*/?>", " ", item or "", flags=re.IGNORECASE)
        text = text.replace("*", "").replace("|", " ").strip(" -\t")
        text = re.sub(r"\s+", " ", text).strip()
        # Skip blanks and fragments too short to be a real requirement.
        if len(text) < 10:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def _assess_bid(llm, rfp_text: str, company_context: str) -> BidRecommendation:
    """One structured LLM call producing the overall bid recommendation."""
    assessor = llm.with_structured_output(BidRecommendation)
    return assessor.invoke(
        [
            ("system", config.date_prefix() + _BID_SYSTEM_PROMPT),
            ("human", _BID_HUMAN_PROMPT.format(
                rfp_text=rfp_text, company_context=company_context
            )),
        ]
    )

def analyze_rfp(
    rfp_text: str,
    rfp_filename: str,
    vectorstore: Chroma,
    model: str | None = DEFAULT_MODEL,
) -> PreBidAnalysis:
    """
    Analyze an incoming RFP against the company knowledge base.

    Args:
        rfp_text: Full text extracted from the RFP document.
        rfp_filename: Original filename, shown in the report.
        vectorstore: Loaded Chroma instance of the company KB.
        model: Groq model identifier.

    Returns:
        PreBidAnalysis with requirement coverage and clarifying questions.

    Raises:
        RuntimeError: If the LLM fails to extract any requirements.
    """
    llm = config.get_llm(model)
    truncated_text = rfp_text[:RFP_TEXT_LIMIT]

    # Step 1 — Extract requirements
    req_extractor = llm.with_structured_output(_RequirementList)
    extracted: _RequirementList = req_extractor.invoke(
        config.date_prefix() + _EXTRACT_PROMPT.format(rfp_text=truncated_text)
    )
    requirement_texts = _clean_requirements(extracted.requirements)[:MAX_REQUIREMENTS]

    if not requirement_texts:
        raise RuntimeError("No requirements could be extracted from the RFP text.")

    # Step 2 — Assess coverage for each requirement
    coverage_assessor = llm.with_structured_output(_CoverageAssessment)
    assessed: list[RequirementCoverage] = []

    for req_text in requirement_texts:
        # Over-fetch by embedding similarity, gate on cosine relevance, then
        # re-rank the survivors with the cross-encoder so the strongest evidence
        # (and its score) leads.
        scored = search_with_scores(
            vectorstore, req_text, k=RETRIEVAL_K * 2, filter={"source_type": "company_kb"}
        )
        survivors = [(doc, score) for doc, score in scored if score >= DEFAULT_RELEVANCE_THRESHOLD]

        # No chunk cleared the relevance bar — that's genuine non-coverage.
        # Skip the LLM call entirely: it's both faster and more honest than
        # asking the model to judge coverage from irrelevant context.
        if not survivors:
            assessed.append(RequirementCoverage(
                requirement=req_text,
                coverage="not_covered",
                evidence="No relevant evidence found in the company knowledge base.",
                source=None,
            ))
            continue

        try:
            relevant = rerank(req_text, [doc for doc, _ in survivors], k=RETRIEVAL_K)
        except Exception:
            relevant = survivors[:RETRIEVAL_K]

        context = "\n\n".join(doc.page_content for doc, _ in relevant)
        assessment: _CoverageAssessment = coverage_assessor.invoke(
            config.date_prefix() + _COVERAGE_PROMPT.format(requirement=req_text, context=context)
        )
        # Ground the citation in the strongest retrieved chunk, not the LLM's guess.
        top_doc, top_score = relevant[0]
        top_source = top_doc.metadata.get("source")
        not_covered = assessment.coverage == "not_covered"
        assessed.append(RequirementCoverage(
            requirement=req_text,
            coverage=assessment.coverage,
            evidence=assessment.evidence,
            source=None if not_covered else top_source,
            relevance=None if not_covered else round(top_score, 3),
        ))

    # Step 3 — Generate clarifying questions
    q_generator = llm.with_structured_output(_ClarifyingQuestionList)
    q_result: _ClarifyingQuestionList = q_generator.invoke(
        config.date_prefix() + _QUESTIONS_PROMPT.format(rfp_text=truncated_text)
    )

    # Step 4 — Build coverage summary
    counts: dict[str, int] = {"fully_covered": 0, "partially_covered": 0, "not_covered": 0}
    for r in assessed:
        counts[r.coverage] += 1

    # Step 5 — Overall bid/no-bid recommendation. Retrieve a broad slice of the
    # company KB and ask the LLM for a single high-level decision. Best-effort:
    # a failure here must not break the core coverage report.
    bid_recommendation: BidRecommendation | None = None
    try:
        bid_query = "company capabilities experience qualifications certifications team past projects"
        # Over-fetch then cross-encoder rerank to the strongest BID_RETRIEVAL_K chunks.
        company_scored = search_with_scores(
            vectorstore,
            bid_query,
            k=BID_RETRIEVAL_K * 3,
            filter={"source_type": "company_kb"},
        )
        company_docs = [doc for doc, _ in company_scored]
        if company_docs:
            try:
                ranked = rerank(bid_query, company_docs, k=BID_RETRIEVAL_K)
                company_docs = [doc for doc, _ in ranked]
            except Exception:
                company_docs = company_docs[:BID_RETRIEVAL_K]
            company_context = "\n\n".join(
                f"[{doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"
                for doc in company_docs
            )
        else:
            company_context = "(No company documents found in the knowledge base.)"
        bid_recommendation = _assess_bid(llm, truncated_text, company_context)
    except Exception:
        bid_recommendation = None

    return PreBidAnalysis(
        rfp_filename=rfp_filename,
        requirements=assessed,
        clarifying_questions=q_result.questions,
        coverage_summary=CoverageSummary(**counts),
        bid_recommendation=bid_recommendation,
    )
