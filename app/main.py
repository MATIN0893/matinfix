from fastapi import FastAPI

from app.api.system import router as system_router
from app.api.v1 import router as api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="MATIN — repair service operating platform and AI Core.",
)
app.include_router(system_router)
app.include_router(api_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "matinfix", "version": app.version}
