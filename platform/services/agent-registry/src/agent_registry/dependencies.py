from fastapi import Request

from events import Publisher


def get_publisher(request: Request) -> Publisher:
    return request.app.state.publisher
