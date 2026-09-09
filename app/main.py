from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from app.api.system import router as system_router
from app.api.v1 import router as api_router
from app.core.config import settings
from app.db.session import SessionLocal

app = FastAPI(
    title=settings.app_name,
    version="0.2.1",
    description="MATIN — repair service operating platform and AI Core.",
)
app.include_router(system_router)
app.include_router(api_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Liveness/readiness check with a real database round-trip."""
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok", "service": "matinfix", "version": app.version}
