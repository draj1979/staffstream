import asyncio
from types import SimpleNamespace

from events import Publisher, schedule_publish


class FakePublisher(Publisher):
    def __init__(self, *, fail: bool = False):
        self.published: list[tuple[str, bytes]] = []
        self._fail = fail
        self._event = asyncio.Event()

    async def publish(self, routing_key: str, payload: bytes) -> None:
        if self._fail:
            raise RuntimeError("broker unreachable")
        self.published.append((routing_key, payload))
        self._event.set()

    async def close(self) -> None:
        pass

    async def wait(self, timeout: float = 1.0) -> None:
        await asyncio.wait_for(self._event.wait(), timeout=timeout)


async def test_schedule_publish_delivers_without_blocking_the_caller():
    app_state = SimpleNamespace(background_tasks=set())
    publisher = FakePublisher()

    schedule_publish(app_state, publisher, "audit.logged", b'{"x": 1}')

    assert len(app_state.background_tasks) == 1  # scheduled synchronously
    await publisher.wait()
    assert publisher.published == [("audit.logged", b'{"x": 1}')]


async def test_schedule_publish_swallows_failures():
    app_state = SimpleNamespace(background_tasks=set())
    publisher = FakePublisher(fail=True)

    schedule_publish(app_state, publisher, "audit.logged", b"{}")

    # give the background task a turn to run and fail internally
    for _ in range(10):
        if not app_state.background_tasks:
            break
        await asyncio.sleep(0.01)
    # no exception raised here is the assertion — a failing publish must
    # never propagate out of the fire-and-forget task.


async def test_schedule_publish_discards_task_reference_when_done():
    app_state = SimpleNamespace(background_tasks=set())
    publisher = FakePublisher()

    schedule_publish(app_state, publisher, "audit.logged", b"{}")
    await publisher.wait()
    for _ in range(10):
        if not app_state.background_tasks:
            break
        await asyncio.sleep(0.01)
    assert app_state.background_tasks == set()
