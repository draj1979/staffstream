import asyncio
import logging
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from auth import Principal, require_auth
from events import (
    ROUTING_KEY_CHAT_INTERACTION,
    ROUTING_KEY_SKILL_USAGE,
    ChatInteractionEvent,
    Publisher,
    SkillUsageEvent,
)

from ..agent_client import AgentClientError
from ..dependencies import get_publisher
from ..employee_client import EmployeeClientError
from ..knowledge_client import KnowledgeClientError
from ..llm_client import LLMClientError
from ..memory_client import MemoryClientError
from ..runtime import TurnContext, run_chat_turn
from ..schemas import ChatRequest, ChatResponse
from ..skill_client import SkillClientError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# Authentication + Identify Tenant + Identify Employee all happen right
# here, in one step: require_auth verifies the JWT and its Principal
# carries tenant_id and employee_id. Load Agent / Load Skills / LLM /
# Tool Calls all happen inside run_chat_turn (see runtime.py) — this
# route is just the HTTP edge.
user_auth = require_auth()

# Maps each downstream client's error type to the analytics "error_stage"
# label — also doubles as the classification used to pick an HTTP status
# below, so the two can never drift apart.
_UPSTREAM_ERRORS: tuple[tuple[type[Exception], str], ...] = (
    (AgentClientError, "agent"),
    (MemoryClientError, "memory"),
    (KnowledgeClientError, "knowledge"),
    (EmployeeClientError, "employee"),
    (SkillClientError, "skills"),
    (LLMClientError, "llm"),
)


async def _publish_interaction_event(publisher: Publisher, event: ChatInteractionEvent) -> None:
    try:
        await publisher.publish(ROUTING_KEY_CHAT_INTERACTION, event.model_dump_json().encode())
    except Exception:
        logger.exception("failed to publish chat interaction event")


async def _publish_skill_usage_event(publisher: Publisher, event: SkillUsageEvent) -> None:
    try:
        await publisher.publish(ROUTING_KEY_SKILL_USAGE, event.model_dump_json().encode())
    except Exception:
        logger.exception("failed to publish skill usage event")


def _schedule(request: Request, coro) -> None:
    # Fire-and-forget, same pattern as every other analytics event: never
    # awaited, so publishing never adds to the chat response's latency. A
    # strong reference lives on app.state until the task finishes.
    task = asyncio.create_task(coro)
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)


def _schedule_skill_usage_events(
    request: Request, publisher: Publisher, principal: Principal, context: TurnContext
) -> None:
    for usage in context.skill_usages:
        event = SkillUsageEvent(
            tenant_id=principal.tenant_id,
            employee_id=principal.employee_id,
            agent_id=context.agent_id,
            skill_name=usage["skill_name"],
            success=usage["success"],
        )
        _schedule(request, _publish_skill_usage_event(publisher, event))


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    request: Request,
    principal: Principal = Depends(user_auth),
    authorization: str = Header(...),
    publisher: Publisher = Depends(get_publisher),
):
    context = TurnContext()
    started = time.monotonic()

    try:
        response = await run_chat_turn(
            principal, data.message, bearer_token=authorization, context=context
        )
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        error_stage = next(
            (stage for exc_type, stage in _UPSTREAM_ERRORS if isinstance(exc, exc_type)), None
        )
        _schedule_skill_usage_events(request, publisher, principal, context)
        _schedule(
            request,
            _publish_interaction_event(
                publisher,
                ChatInteractionEvent(
                    tenant_id=principal.tenant_id,
                    employee_id=principal.employee_id,
                    agent_id=context.agent_id,
                    success=False,
                    error_stage=error_stage,
                    latency_ms=latency_ms,
                ),
            ),
        )

        if isinstance(exc, AgentClientError):
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No agent profile found for this employee",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail
            ) from exc
        if isinstance(
            exc,
            (
                LLMClientError,
                MemoryClientError,
                EmployeeClientError,
                KnowledgeClientError,
                SkillClientError,
            ),
        ):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc
        raise

    latency_ms = int((time.monotonic() - started) * 1000)
    _schedule_skill_usage_events(request, publisher, principal, context)
    _schedule(
        request,
        _publish_interaction_event(
            publisher,
            ChatInteractionEvent(
                tenant_id=principal.tenant_id,
                employee_id=principal.employee_id,
                agent_id=context.agent_id,
                success=True,
                error_stage=None,
                latency_ms=latency_ms,
            ),
        ),
    )
    return response
