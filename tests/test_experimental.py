from __future__ import annotations

def test_experimental_pipeline_failure() -> None:
    """Deliberately fails to verify CI pipeline error catching and recovery mechanisms."""
    from app.experimental import broken
