import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import DocumentStatus, KnowledgeScope


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    scope: KnowledgeScope
    department: str | None
    employee_id: uuid.UUID | None
    uploaded_by_employee_id: uuid.UUID
    filename: str
    content_type: str
    status: DocumentStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class SearchRequest(BaseModel):
    query: str
    department: str | None = None
    employee_id: uuid.UUID | None = None
    top_k: int = Field(default=5, gt=0, le=50)


class ChunkResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    scope: KnowledgeScope
    content: str
