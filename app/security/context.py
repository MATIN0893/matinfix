from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceContext:
    workspace_id: str
    master_id: str


def require_workspace(workspace_id: str | None, master_id: str | None) -> WorkspaceContext:
    if not workspace_id or not master_id:
        raise ValueError("workspace context is required")
    return WorkspaceContext(workspace_id=workspace_id, master_id=master_id)
