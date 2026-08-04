from fastapi import Request

from events import Publisher

from .gateway import LLMGateway


def get_gateway(request: Request) -> LLMGateway:
    return request.app.state.gateway


def get_publisher(request: Request) -> Publisher:
    return request.app.state.publisher
