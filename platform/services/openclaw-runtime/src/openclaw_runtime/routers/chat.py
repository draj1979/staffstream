import asyncio
import logging
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from auth import Principal, require_auth
from events import ROUTING_KEY_CHAT_INTERACTION, ChatInteractionEvent, Publisher

from ..agent_client import AgentClientError
from ..dependencies import get_publisher
from ..employee_client import EmployeeClientError
from ..knowledge_client import KnowledgeClientError
from ..llm_client import LLMClientError
from ..memory_client import MemoryClientError
from ..runtime import TurnContext, run_chat_turn
from ..schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# Authentication + Identify Tenant + Identify Employee all happen right
# here, in one step: require_auth verifies the JWT and its Principal
# carries tenant_id and employee_id. Load Agent / LLM happen inside
# run_chat_turn (see runtime.py) — this route is just the HTTP edge.
user_auth = require_auth()

# Maps each downstream client's error type to the analytics "error_stage"
# label — also doubles as the classification used to pick an HTTP status
# below, so the two can never drift apart.
_UPSTREAM_ERRORS: tuple[tuple[type[Exception], str], ...] = (
    (AgentClientError, "agent"),
    (MemoryClientError, "memory"),
    (KnowledgeClientError, "knowledge"),
    (EmployeeClientError, "employee"),
    (LLMClientError, "llm"),
)


async def _publish_interaction_event(publisher: Publisher, event: ChatInteractionEvent) -> None:
    try:
        await publisher.publish(ROUTING_KEY_CHAT_INTERACTION, event.model_dump_json().encode())
    except Exception:
        logger.exception("failed to publish chat interaction event")


def _schedule_publish(request: Request, publisher: Publisher, event: ChatInteractionEvent) -> None:
    # Fire-and-forget, same pattern as LLM Gateway's usage events: never
    # awaited, so publishing never adds to the chat response's latency. A
    # strong reference lives on app.state until the task finishes.
    task = asyncio.create_task(_publish_interaction_event(publisher, event))
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)


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
        _schedule_publish(
            request,
            publisher,
            ChatInteractionEvent(
                tenant_id=principal.tenant_id,
                employee_id=principal.employee_id,
                agent_id=context.agent_id,
                success=False,
                error_stage=error_stage,
                latency_ms=latency_ms,
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
            exc, (LLMClientError, MemoryClientError, EmployeeClientError, KnowledgeClientError)
        ):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc
        raise

    latency_ms = int((time.monotonic() - started) * 1000)
    _schedule_publish(
        request,
        publisher,
        ChatInteractionEvent(
            tenant_id=principal.tenant_id,
            employee_id=principal.employee_id,
            agent_id=context.agent_id,
            success=True,
            error_stage=None,
            latency_ms=latency_ms,
        ),
    )
    return response
