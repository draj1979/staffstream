import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .models import SubscriptionStatus


class TenantBase(BaseModel):
    company_name: str
    plan: str = "free"
    storage_quota_bytes: int = 0
    llm_config: dict = {}
    branding: dict = {}
    subscription_status: SubscriptionStatus = SubscriptionStatus.TRIAL


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    company_name: str | None = None
    plan: str | None = None
    storage_quota_bytes: int | None = None
    llm_config: dict | None = None
    branding: dict | None = None
    subscription_status: SubscriptionStatus | None = None


class TenantOut(TenantBase):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
