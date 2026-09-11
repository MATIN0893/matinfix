from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from app.api.crm import router as crm_router
from app.api.system import router as system_router
from app.api.v1 import router as api_router
from app.core.config import settings
from app.db.models import Base
from app.db.session import SessionLocal, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Safe bootstrap for a fresh environment. Alembic remains the migration authority.
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    description="MATIN — repair service operating platform and AI Core.",
    lifespan=lifespan,
)
app.include_router(system_router)
app.include_router(api_router)
app.include_router(crm_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Readiness check with a real database round-trip."""
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok", "service": "matinfix", "version": app.version}
