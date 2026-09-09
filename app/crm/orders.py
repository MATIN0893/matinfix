from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class RepairOrder:
    id: str
    workspace_id: str
    customer_id: str
    device_brand: str
    device_model: str
    problem: str
    status: str = "new"
    created_at: datetime | None = None


VALID_STATUSES = {"new", "diagnostics", "waiting_part", "repairing", "ready", "issued", "cancelled"}


def transition(order: RepairOrder, status: str) -> RepairOrder:
    if status not in VALID_STATUSES:
        raise ValueError(f"unknown repair status: {status}")
    return RepairOrder(**{**order.__dict__, "status": status})
