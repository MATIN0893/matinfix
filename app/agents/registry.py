from __future__ import annotations

from enum import StrEnum


class AgentName(StrEnum):
    CUSTOMER = "customer"
    MASTER = "master"
    ADMIN = "admin"


AGENT_NAMES = tuple(agent.value for agent in AgentName)
