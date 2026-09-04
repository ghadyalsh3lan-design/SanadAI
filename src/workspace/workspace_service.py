"""
Workspace service — persists tracked RFP bids across sessions.

Each bid represents one RFP the team is actively working on. The workspace
stores bid metadata and status so the dashboard shows real pipeline data
instead of sample data.

Storage: data/workspace.json (gitignored alongside chroma_db — may contain
client-specific RFP filenames).
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

WORKSPACE_PATH = Path("data/workspace.json")


class WorkspaceBid(BaseModel):
    """One tracked RFP bid in the proposal pipeline."""
    bid_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    rfp_filename: str
    status: Literal[
        "analyzing", "analyzed", "drafting", "drafted", "reviewing", "won", "lost"
    ] = "analyzed"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    # Full pre-bid analysis report saved with the bid (recommendation, coverage,
    # clarifying questions, compliance decisions). Stored as a plain dict so the
    # workspace doesn't depend on the analysis schema.
    analysis: dict[str, Any] | None = None


def _load() -> list[WorkspaceBid]:
    if not WORKSPACE_PATH.exists():
        return []
    try:
        data = json.loads(WORKSPACE_PATH.read_text(encoding="utf-8"))
        return [WorkspaceBid.model_validate(b) for b in data]
    except Exception:
        return []


def _save(bids: list[WorkspaceBid]) -> None:
    WORKSPACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    WORKSPACE_PATH.write_text(
        json.dumps([b.model_dump() for b in bids], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def list_bids() -> list[WorkspaceBid]:
    """List all tracked bids, newest first."""
    return sorted(_load(), key=lambda b: b.created_at, reverse=True)


def add_bid(
    rfp_filename: str,
    status: str = "analyzed",
    analysis: dict[str, Any] | None = None,
) -> WorkspaceBid:
    """
    Add a new bid to the workspace.

    A bid is unique per RFP filename: saving the same RFP again updates the
    existing bid (refreshing its analysis and timestamp) instead of creating a
    duplicate. The original created_at and pipeline status are preserved.

    Args:
        rfp_filename: The original RFP filename.
        status: Initial pipeline status (used only when creating a new bid).
        analysis: Optional full pre-bid analysis report to store with the bid.

    Returns:
        The created or updated WorkspaceBid.
    """
    bids = _load()
    for existing in bids:
        if existing.rfp_filename == rfp_filename:
            if analysis is not None:
                existing.analysis = analysis
            existing.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            _save(bids)
            return existing

    bid = WorkspaceBid(rfp_filename=rfp_filename, status=status, analysis=analysis)  # type: ignore[arg-type]
    bids.append(bid)
    _save(bids)
    return bid


def update_bid_status(bid_id: str, status: str) -> WorkspaceBid | None:
    """
    Update a bid's pipeline status.

    Args:
        bid_id: The bid's unique identifier.
        status: New status value.

    Returns:
        The updated WorkspaceBid, or None if not found.
    """
    bids = _load()
    for bid in bids:
        if bid.bid_id == bid_id:
            bid.status = status  # type: ignore[assignment]
            bid.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            _save(bids)
            return bid
    return None


def delete_bid(bid_id: str) -> bool:
    """
    Remove a bid from the workspace.

    Args:
        bid_id: The bid's unique identifier.

    Returns:
        True if found and removed, False otherwise.
    """
    bids = _load()
    filtered = [b for b in bids if b.bid_id != bid_id]
    if len(filtered) == len(bids):
        return False
    _save(filtered)
    return True
