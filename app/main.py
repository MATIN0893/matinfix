import asyncio
from contextlib import asynccontextmanager, suppress

from aiogram import Bot, Dispatcher
from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from app.api.crm import router as crm_router
from app.api.master import router as master_router
from app.api.system import router as system_router
from app.api.v1 import router as api_router
from app.core.config import settings
from app.db.models import Base
from app.db.session import SessionLocal, engine
from app.telegram.bot import router as telegram_router


async def _run_telegram() -> None:
    if not settings.telegram_bot_token:
        return
    bot = Bot(settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(telegram_router)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    telegram_task = None
    if settings.telegram_bot_token:
        telegram_task = asyncio.create_task(_run_telegram())
    yield
    if telegram_task is not None:
        telegram_task.cancel()
        with suppress(asyncio.CancelledError):
            await telegram_task
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="MATIN — repair service operating platform and AI Core.",
    lifespan=lifespan,
)
app.include_router(system_router)
app.include_router(api_router)
app.include_router(crm_router)
app.include_router(master_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok", "service": "matinfix", "version": app.version}
