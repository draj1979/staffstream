import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ConversationTurnCreate(BaseModel):
    role: str
    content: str


class ConversationTurnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    memory_namespace: str
    role: str
    content: str
    created_at: datetime


class LongTermMemoryCreate(BaseModel):
    content: str


class LongTermMemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    memory_namespace: str
    content: str
    created_at: datetime
    updated_at: datetime


class PreferenceSet(BaseModel):
    value: Any


class PreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    memory_namespace: str
    key: str
    value: Any
    created_at: datetime
    updated_at: datetime


class LearnedFactCreate(BaseModel):
    content: str


class LearnedFactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    memory_namespace: str
    content: str
    created_at: datetime
    updated_at: datetime
