from fastapi import APIRouter, Depends, HTTPException, status

from auth import Principal, require_auth

from ..dependencies import get_gateway
from ..errors import ProviderError, UnknownProviderError
from ..gateway import LLMGateway
from ..models import LLMResponse
from ..schemas import GenerateRequest

router = APIRouter(tags=["generate"])
user_auth = require_auth()


@router.post("/generate", response_model=LLMResponse)
async def generate(
    data: GenerateRequest,
    principal: Principal = Depends(user_auth),
    gateway: LLMGateway = Depends(get_gateway),
):
    try:
        return await gateway.complete(data.provider, data)
    except UnknownProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
