import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    department: str | None = None
    designation: str | None = None
    phone: str | None = None
    roles: list[str] = []


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    tenant_id: uuid.UUID
    employee_id: uuid.UUID


class SsoConfigIn(BaseModel):
    client_id: str
    client_secret: str
    # Auth0 only — the tenant's Auth0 domain, e.g. "acme.us.auth0.com".
    issuer_domain: str | None = None
    # Google Workspace only — restrict SSO logins to this Workspace domain.
    hosted_domain: str | None = None
    enabled: bool = True


class SsoConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    client_id: str
    issuer_domain: str | None
    hosted_domain: str | None
    enabled: bool
    # Deliberately no client_secret field anywhere in this model — once
    # set, it's write-only from the API's point of view.
