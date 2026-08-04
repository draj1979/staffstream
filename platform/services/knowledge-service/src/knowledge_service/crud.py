import uuid

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Chunk, Document, DocumentStatus, KnowledgeScope


async def create_document(
    db: AsyncSession,
    *,
    scope: KnowledgeScope,
    department: str | None,
    employee_id: uuid.UUID | None,
    uploaded_by_employee_id: uuid.UUID,
    filename: str,
    content_type: str,
) -> Document:
    document = Document(
        scope=scope,
        department=department,
        employee_id=employee_id,
        uploaded_by_employee_id=uploaded_by_employee_id,
        filename=filename,
        content_type=content_type,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def add_chunks(
    db: AsyncSession, document: Document, chunks: list[str], embeddings: list[list[float]]
) -> None:
    for index, (content, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
        db.add(
            Chunk(
                document_id=document.id,
                scope=document.scope,
                department=document.department,
                employee_id=document.employee_id,
                chunk_index=index,
                content=content,
                embedding=embedding,
            )
        )
    await db.commit()


async def mark_ready(db: AsyncSession, document: Document) -> Document:
    document.status = DocumentStatus.READY
    await db.commit()
    await db.refresh(document)
    return document


async def mark_failed(db: AsyncSession, document: Document, error_message: str) -> Document:
    document.status = DocumentStatus.FAILED
    document.error_message = error_message
    await db.commit()
    await db.refresh(document)
    return document


async def get_document(db: AsyncSession, document_id: uuid.UUID) -> Document | None:
    return await db.get(Document, document_id)


async def list_documents(
    db: AsyncSession,
    *,
    scope: KnowledgeScope | None = None,
    department: str | None = None,
    employee_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Document]:
    stmt = select(Document)
    if scope is not None:
        stmt = stmt.where(Document.scope == scope)
    if department is not None:
        stmt = stmt.where(Document.department == department)
    if employee_id is not None:
        stmt = stmt.where(Document.employee_id == employee_id)
    stmt = stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_document(db: AsyncSession, document: Document) -> None:
    await db.execute(delete(Chunk).where(Chunk.document_id == document.id))
    await db.delete(document)
    await db.commit()


async def search_chunks(
    db: AsyncSession,
    query_embedding: list[float],
    *,
    department: str | None,
    employee_id: uuid.UUID | None,
    top_k: int,
) -> list[tuple[Chunk, str]]:
    visibility = [Chunk.scope == KnowledgeScope.COMPANY]
    if department:
        visibility.append(
            (Chunk.scope == KnowledgeScope.DEPARTMENT) & (Chunk.department == department)
        )
    if employee_id:
        visibility.append(
            (Chunk.scope == KnowledgeScope.PERSONAL) & (Chunk.employee_id == employee_id)
        )

    stmt = (
        select(Chunk, Document.filename)
        .join(Document, Chunk.document_id == Document.id)
        .where(or_(*visibility))
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    result = await db.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]
