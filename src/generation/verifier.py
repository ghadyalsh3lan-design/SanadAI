"""
Answer verifier for the RFP Intelligence System.

Given a question, a generated answer, and the source chunks used to produce it,
checks whether the answer is faithful (no invented claims) and complete
(no key points dropped).

Called when POST /query receives verify=true.
"""
from langchain_core.documents import Document
from pydantic import BaseModel, Field

from src import config

DEFAULT_MODEL = None  # None → use the configured provider's default model

VERIFICATION_PROMPT = """You are a fact-checker reviewing an AI-generated answer against the source documents it was based on.

Question: {question}

Generated Answer:
{answer}

Source Documents:
{context}

Evaluate the answer on two dimensions:

1. FAITHFULNESS — Does the answer only make claims that are directly supported by the source documents?
   - Mark faithful=false and list any unsupported claims in flagged_claims.

2. COMPLETENESS — Does the answer cover the key points from the sources that are relevant to the question?
   - Mark complete=false and list any important missed points in missed_points.

Be precise. Only flag real issues."""


class VerificationResult(BaseModel):
    """Result of verifying an answer against its source documents."""
    faithful: bool = Field(description="True if every claim in the answer is supported by the sources")
    complete: bool = Field(description="True if the answer covers the key relevant points from the sources")
    missed_points: list[str] = Field(
        default_factory=list,
        description="Key points from the sources that the answer did not address"
    )
    flagged_claims: list[str] = Field(
        default_factory=list,
        description="Claims in the answer that are not supported by any source"
    )


def verify_answer(
    question: str,
    answer_text: str,
    source_chunks: list[Document],
    model: str | None = DEFAULT_MODEL,
) -> VerificationResult:
    """
    Check whether a generated answer is faithful and complete.

    Args:
        question: The original user question.
        answer_text: The generated answer to verify.
        source_chunks: The chunks the answer was grounded in.
        model: Groq model identifier.

    Returns:
        VerificationResult with flags and details.
    """
    context = "\n\n---\n\n".join(
        f"[Source {i + 1}: {chunk.metadata.get('source', 'unknown')}]\n{chunk.page_content}"
        for i, chunk in enumerate(source_chunks)
    )
    prompt = VERIFICATION_PROMPT.format(
        question=question,
        answer=answer_text,
        context=context,
    )
    llm = config.get_llm(model)
    verifier = llm.with_structured_output(VerificationResult)
    return verifier.invoke(config.date_prefix() + prompt)
