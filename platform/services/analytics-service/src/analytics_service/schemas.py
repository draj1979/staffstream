import uuid
from datetime import date

from pydantic import BaseModel


class DateRange(BaseModel):
    from_date: date
    to_date: date


class AdminDashboard(BaseModel):
    range: DateRange
    total_conversations: int
    success_rate: float
    active_employees: int
    active_agents: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float


class ModelCost(BaseModel):
    model: str
    call_count: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


class EmployeeCost(BaseModel):
    employee_id: uuid.UUID
    call_count: int
    cost_usd: float


class DailyCost(BaseModel):
    day: str
    cost_usd: float


class FinanceDashboard(BaseModel):
    range: DateRange
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    cost_by_model: list[ModelCost]
    cost_by_employee: list[EmployeeCost]
    daily_cost: list[DailyCost]


class AgentHealth(BaseModel):
    agent_id: uuid.UUID
    request_count: int
    error_count: int
    avg_latency_ms: float


class StageErrorCount(BaseModel):
    error_stage: str
    count: int


class ITDashboard(BaseModel):
    range: DateRange
    total_requests: int
    error_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    requests_by_agent: list[AgentHealth]
    errors_by_stage: list[StageErrorCount]
