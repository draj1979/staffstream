from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SkillEnablementOut(BaseModel):
    """One catalog skill plus this tenant's enablement state for it —
    "opt-in per tenant, not globally on" means the enablement flag is
    always shown alongside the catalog entry, never separately."""

    model_config = ConfigDict(from_attributes=True)

    skill_id: str
    name: str
    description: str
    connector: str
    enabled: bool
    config: dict


class SkillEnablementUpdate(BaseModel):
    enabled: bool
    config: dict = {}


class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill_id: str
    connected: bool
    external_account: str | None = None
    granted_scope: str | None = None
    connected_at: datetime | None = None


class AuthorizeOut(BaseModel):
    authorize_url: str


class ToolOut(BaseModel):
    skill_id: str
    name: str
    description: str
    input_schema: dict


class InvokeRequest(BaseModel):
    tool_name: str
    input: dict = {}


class InvokeResponse(BaseModel):
    output: dict
