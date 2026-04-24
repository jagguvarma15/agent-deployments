"""Document ingestion route handlers."""

import hashlib
import uuid

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document
from app.db.session import get_session
from app.models.schemas import DocumentIngestRequest, DocumentIngestResponse
from app.tools.chunker import chunk_document
from app.tools.retriever import store_chunks

logger = structlog.get_logger()

router = APIRouter()


@router.post("/documents", response_model=DocumentIngestResponse)
async def ingest_document(
    request: DocumentIngestRequest,
    session: AsyncSession = Depends(get_session),
):
    """Ingest a document: chunk it, store in DB and vector store."""
    doc_id = str(uuid.uuid4())
    content_hash = hashlib.sha256(request.content.encode()).hexdigest()

    log = logger.bind(document_id=doc_id, title=request.title)
    log.info("ingesting_document")

    # Chunk the content
    chunks = chunk_document(request.content)
    log.info("document_chunked", chunk_count=len(chunks))

    # Store document in DB
    document = Document(
        id=doc_id,
        title=request.title,
        content_hash=content_hash,
        chunk_count=len(chunks),
    )
    session.add(document)

    # Store chunks in DB
    for i, chunk_text in enumerate(chunks):
        chunk = Chunk(
            document_id=doc_id,
            text=chunk_text,
            position=i,
        )
        session.add(chunk)

    await session.commit()

    # Store in vector store for retrieval
    store_chunks(doc_id, request.title, chunks)

    return DocumentIngestResponse(
        document_id=doc_id,
        chunk_count=len(chunks),
        status="ingested",
    )
