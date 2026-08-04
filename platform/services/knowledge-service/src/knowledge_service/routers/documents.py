import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import Principal, require_auth

from .. import crud
from ..chunking import chunk_text
from ..config import settings
from ..db import get_db
from ..dependencies import get_embedder
from ..embedder import Embedder
from ..errors import EmbeddingError, EmptyDocumentError, UnsupportedContentTypeError
from ..extraction import extract_text
from ..models import KnowledgeScope
from ..schemas import ChunkResult, DocumentOut, SearchRequest

router = APIRouter(tags=["knowledge"])
user_auth = require_auth()


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    scope: KnowledgeScope = Form(...),
    department: str | None = Form(None),
    file: UploadFile = File(...),
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
):
    if scope == KnowledgeScope.DEPARTMENT and not department:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="department is required for department-scoped documents",
        )

    # personal scope is always the uploader's own — no one uploads into
    # someone else's personal knowledge.
    employee_id = principal.employee_id if scope == KnowledgeScope.PERSONAL else None
    department = department if scope == KnowledgeScope.DEPARTMENT else None

    content = await file.read()
    document = await crud.create_document(
        db,
        scope=scope,
        department=department,
        employee_id=employee_id,
        uploaded_by_employee_id=principal.employee_id,
        filename=file.filename or "untitled",
        content_type=file.content_type or "application/octet-stream",
    )

    try:
        text = extract_text(content, document.content_type)
        chunks = chunk_text(
            text, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap
        )
        if not chunks:
            raise EmptyDocumentError("Document has no extractable text")
        embeddings = await embedder.embed(chunks, input_type="document")
        await crud.add_chunks(db, document, chunks, embeddings)
        return await crud.mark_ready(db, document)
    except (UnsupportedContentTypeError, EmptyDocumentError) as exc:
        await crud.mark_failed(db, document, str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except EmbeddingError as exc:
        await crud.mark_failed(db, document, str(exc))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    scope: KnowledgeScope | None = None,
    department: str | None = None,
    employee_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await crud.list_documents(
        db, scope=scope, department=department, employee_id=employee_id, limit=limit, offset=offset
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    document = await crud.get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    await crud.delete_document(db, document)


@router.post("/search", response_model=list[ChunkResult])
async def search(
    data: SearchRequest,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
):
    try:
        [query_embedding] = await embedder.embed([data.query], input_type="query")
    except EmbeddingError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    rows = await crud.search_chunks(
        db,
        query_embedding,
        department=data.department,
        employee_id=data.employee_id,
        top_k=data.top_k,
    )
    return [
        ChunkResult(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            filename=filename,
            scope=chunk.scope,
            content=chunk.content,
        )
        for chunk, filename in rows
    ]
