from fastapi import APIRouter, Depends, Header, HTTPException, status

from auth import Principal, require_auth

from ..agent_client import AgentClientError
from ..employee_client import EmployeeClientError
from ..knowledge_client import KnowledgeClientError
from ..llm_client import LLMClientError
from ..memory_client import MemoryClientError
from ..runtime import run_chat_turn
from ..schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])

# Authentication + Identify Tenant + Identify Employee all happen right
# here, in one step: require_auth verifies the JWT and its Principal
# carries tenant_id and employee_id. Load Agent / LLM happen inside
# run_chat_turn (see runtime.py) — this route is just the HTTP edge.
user_auth = require_auth()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    principal: Principal = Depends(user_auth),
    authorization: str = Header(...),
):
    try:
        return await run_chat_turn(principal, data.message, bearer_token=authorization)
    except AgentClientError as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No agent profile found for this employee",
            ) from exc
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc
    except LLMClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc
    except MemoryClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc
    except EmployeeClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc
    except KnowledgeClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc
