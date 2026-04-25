"""Research route handlers."""

import uuid

from fastapi import APIRouter

from app.models.schemas import (
    ResearchRequest,
    ResearchResult,
    ResearchStatus,
    ResearchStep,
    Source,
)

router = APIRouter()

_results: dict[str, dict] = {}


@router.post("/research", response_model=ResearchResult)
async def start_research(request: ResearchRequest):
    """Start a research session."""
    research_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    steps = [
        ResearchStep(step=1, action="search", content=f"Searching for: {request.question}"),
        ResearchStep(step=2, action="analyze", content="Analyzing search results"),
        ResearchStep(step=3, action="synthesize", content="Synthesizing findings"),
    ]

    sources = [
        Source(
            title="Example Source",
            url="https://example.com",
            excerpt="Relevant information found here.",
        ),
    ]

    result = ResearchResult(
        id=research_id,
        question=request.question,
        steps=steps,
        answer=f"Based on research, here is the answer to: {request.question}",
        sources=sources,
        trace_id=trace_id,
    )

    _results[research_id] = {"status": "completed", "steps": len(steps)}
    return result


@router.get("/research/{research_id}/status", response_model=ResearchStatus)
async def get_research_status(research_id: str):
    """Get status of a research session."""
    info = _results.get(research_id, {"status": "not_found", "steps": 0})
    return ResearchStatus(
        id=research_id,
        status=info["status"],
        steps_completed=info["steps"],
    )
