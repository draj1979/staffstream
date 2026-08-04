import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class EmployeeBase(BaseModel):
    department: str | None = None
    designation: str | None = None
    manager_id: uuid.UUID | None = None
    phone: str | None = None
    email: EmailStr
    agent_id: uuid.UUID | None = None
    roles: list[str] = []


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    department: str | None = None
    designation: str | None = None
    manager_id: uuid.UUID | None = None
    phone: str | None = None
    email: EmailStr | None = None
    agent_id: uuid.UUID | None = None
    roles: list[str] | None = None


class EmployeeOut(EmployeeBase):
    model_config = ConfigDict(from_attributes=True)

    employee_id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
