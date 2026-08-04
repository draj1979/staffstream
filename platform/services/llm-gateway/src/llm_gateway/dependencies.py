from fastapi import Request

from .gateway import LLMGateway


def get_gateway(request: Request) -> LLMGateway:
    return request.app.state.gateway
