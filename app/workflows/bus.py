from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Awaitable


@dataclass(frozen=True)
class WorkflowEvent:
    name: str
    payload: dict[str, object]


Handler = Callable[[WorkflowEvent], Awaitable[None]]


class WorkflowBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    async def publish(self, event: WorkflowEvent) -> None:
        for handler in tuple(self._handlers.get(event.name, ())):
            await handler(event)
