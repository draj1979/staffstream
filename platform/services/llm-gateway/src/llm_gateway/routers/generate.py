import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from auth import Principal, require_auth
from events import ROUTING_KEY_LLM_USAGE, LLMUsageEvent, Publisher

from ..dependencies import get_gateway, get_publisher
from ..errors import ProviderError, UnknownProviderError
from ..gateway import LLMGateway
from ..models import LLMResponse
from ..pricing import estimate_cost_usd
from ..schemas import GenerateRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["generate"])
user_auth = require_auth()


async def _publish_usage_event(publisher: Publisher, event: LLMUsageEvent) -> None:
    try:
        await publisher.publish(ROUTING_KEY_LLM_USAGE, event.model_dump_json().encode())
    except Exception:
        # Analytics ingestion is best-effort: a broker hiccup here must
        # never surface as a chat-facing error, and this already isn't
        # awaited by the caller, so there's nothing to retry inline.
        logger.exception("failed to publish LLM usage event")


@router.post("/generate", response_model=LLMResponse)
async def generate(
    data: GenerateRequest,
    request: Request,
    principal: Principal = Depends(user_auth),
    gateway: LLMGateway = Depends(get_gateway),
    publisher: Publisher = Depends(get_publisher),
):
    try:
        response = await gateway.complete(data.provider, data)
    except UnknownProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    event = LLMUsageEvent(
        tenant_id=principal.tenant_id,
        employee_id=principal.employee_id,
        agent_id=data.agent_id,
        provider=data.provider,
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cost_usd=estimate_cost_usd(
            response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        ),
    )
    # Fire-and-forget: scheduled, never awaited, so publishing never adds
    # to this request's latency. A strong reference lives on app.state
    # until the task finishes, so it can't be garbage-collected mid-flight
    # (asyncio.create_task's well-known gotcha).
    task = asyncio.create_task(_publish_usage_event(publisher, event))
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)

    return response
