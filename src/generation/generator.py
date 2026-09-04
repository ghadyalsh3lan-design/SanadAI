"""
Generation layer for the RFP Intelligence System.

Takes a user question and retrieved chunks, returns a grounded answer
with structured source citations.

Design:
  - Uses Groq + Llama 3.3 70B (free tier, fast, good at instruction following).
  - Prompt explicitly grounds the answer in retrieved context.
  - Returns a Pydantic model so callers get validated, typed data.
  - LLM refuses ("I don't know") when context doesn't support an answer.
"""
from langchain_core.documents import Document
from pydantic import BaseModel, Field
from src import config

DEFAULT_MODEL = None  # None → use the configured provider's default model

GROUNDING_SYSTEM = """You are an assistant helping a proposal writer draft RFP responses.

Answer the user's question using ONLY the context provided in their message. Follow these rules strictly:
- If the context does not contain enough information to answer, respond exactly: "I don't have enough information to answer that based on the provided documents."
- Do not invent facts, numbers, dates, or claims that are not in the context.
- For any question about timelines, deadlines, scheduling, or feasibility, compare the dates in the context against today's date (stated above). Explicitly state when a date or deadline has already passed, and do not describe a past date as upcoming or still achievable.
- Use the earlier conversation only to understand what the user is referring to (pronouns, follow-ups); still ground every fact in the provided context.
- Keep the answer concise and grounded.
- Write in a professional tone suitable for a business proposal."""

GROUNDING_USER = """Context:
{context}

Question: {question}

Answer:"""

# Rephrases a follow-up into a standalone question so retrieval works without the
# surrounding conversation. Returns only the rephrased question.
_CONDENSE_PROMPT = """Given the conversation so far and a follow-up question, rewrite the follow-up as a standalone question that can be understood without the conversation. Resolve pronouns and references. If it is already standalone, return it unchanged. Return ONLY the rewritten question, nothing else.

Conversation:
{history}

Follow-up question: {question}

Standalone question:"""


class Source(BaseModel):
    """A single source citation."""
    source: str = Field(description="Original filename")
    chunk_index: int = Field(description="Position of the chunk within the source document")
    page: int | None = Field(default=None, description="Page number if available")
    preview: str = Field(description="First ~150 characters of the cited chunk")
    relevance: float | None = Field(
        default=None, description="Relevance score (0-1) of this chunk to the query"
    )


class Answer(BaseModel):
    """A grounded answer with its sources."""
    answer: str = Field(description="The generated answer text")
    sources: list[Source] = Field(description="Sources the answer is grounded in")
    refused: bool = Field(description="True if the LLM declined to answer for lack of context")


def _build_source(chunk: Document) -> Source:
    """Internal: convert a retrieved chunk into a Source citation."""
    return Source(
        source=chunk.metadata.get("source", "unknown"),
        chunk_index=chunk.metadata.get("chunk_index", -1),
        page=chunk.metadata.get("page"),
        preview=chunk.page_content[:1000],
        relevance=chunk.metadata.get("relevance"),
    )


def _was_refusal(answer_text: str) -> bool:
    """Internal: detect whether the LLM refused to answer."""
    return "don't have enough information" in answer_text.lower()


def _dedupe_chunks(chunks: list[Document]) -> list[Document]:
    """Internal: drop duplicate chunks, preserving retrieval order.

    Chroma can return the same chunk twice on small corpora, which would both
    waste context tokens and produce duplicate citations. Dedupe on
    (source, chunk_index), falling back to page_content when those are missing.
    """
    seen: set = set()
    unique: list[Document] = []
    for chunk in chunks:
        key = (
            chunk.metadata.get("source"),
            chunk.metadata.get("chunk_index"),
            chunk.metadata.get("page"),
        )
        if key == (None, None, None):
            key = chunk.page_content
        if key in seen:
            continue
        seen.add(key)
        unique.append(chunk)
    return unique


def _history_messages(history: list[dict] | None) -> list[tuple[str, str]]:
    """Convert stored chat turns into LangChain (role, content) message tuples.

    Only user/assistant text is carried (sources/evaluation payloads are dropped),
    giving the model conversational memory without bloating the prompt.
    """
    messages: list[tuple[str, str]] = []
    for turn in history or []:
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        role = "assistant" if turn.get("role") == "assistant" else "human"
        messages.append((role, content))
    return messages


def condense_question(
    question: str,
    history: list[dict] | None,
    model: str | None = DEFAULT_MODEL,
) -> str:
    """
    Rewrite a follow-up into a standalone question using the conversation.

    Returns the original question unchanged when there is no history (or on any
    failure), so retrieval still works for the first turn.
    """
    convo = _history_messages(history)
    if not convo:
        return question
    history_text = "\n".join(f"{role}: {content}" for role, content in convo)
    try:
        llm = config.get_llm(model)
        response = llm.invoke(
            config.date_prefix()
            + _CONDENSE_PROMPT.format(history=history_text, question=question)
        )
        rewritten = response.content.strip()
        return rewritten or question
    except Exception:
        return question


def generate_answer(
    question: str,
    retrieved_chunks: list[Document],
    model: str | None = DEFAULT_MODEL,
    history: list[dict] | None = None,
) -> Answer:
    """
    Generate a grounded answer from a question and retrieved context.

    Args:
        question: User's natural language question.
        retrieved_chunks: Output from src.retrieval.vector_store.search
        model: Groq model identifier.
        history: Prior conversation turns ([{role, content}, ...]) for memory.

    Returns:
        Answer object with the response text, source citations, and a
        refusal flag.

    Raises:
        ValueError: If retrieved_chunks is empty.
    """
    if not retrieved_chunks:
        raise ValueError(
            "Cannot generate without retrieved context. "
            "Either retrieval returned nothing, or it wasn't called."
        )

    retrieved_chunks = _dedupe_chunks(retrieved_chunks)
    context = "\n\n".join(chunk.page_content for chunk in retrieved_chunks)

    # System rules + prior turns (memory) + the grounded question.
    messages: list[tuple[str, str]] = [("system", config.date_prefix() + GROUNDING_SYSTEM)]
    messages += _history_messages(history)
    messages.append(("human", GROUNDING_USER.format(context=context, question=question)))

    llm = config.get_llm(model)
    response = llm.invoke(messages)
    answer_text = response.content

    refused = _was_refusal(answer_text)

    # Only attach sources when we actually used them
    sources = [_build_source(c) for c in retrieved_chunks] if not refused else []

    return Answer(
        answer=answer_text,
        sources=sources,
        refused=refused,
    )
