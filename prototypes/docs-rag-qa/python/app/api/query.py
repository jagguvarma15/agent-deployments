"""Query route handlers."""

import uuid

import structlog
from fastapi import APIRouter

from app.agent.qa import answer_question
from app.models.schemas import QueryRequest, QueryResponse

logger = structlog.get_logger()

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Answer a question using the RAG pipeline."""
    trace_id = str(uuid.uuid4())
    log = logger.bind(trace_id=trace_id, question=request.question)
    log.info("processing_query")

    answer, citations = await answer_question(request.question, top_k=request.top_k)
    log.info("query_answered", citation_count=len(citations))

    return QueryResponse(
        answer=answer,
        citations=[],
        trace_id=trace_id,
    )
