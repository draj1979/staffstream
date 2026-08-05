import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditLogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_employee_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: str | None
    metadata: dict = Field(validation_alias="entry_metadata", serialization_alias="metadata")
    created_at: datetime
