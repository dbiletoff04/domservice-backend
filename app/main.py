import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.init_db import init_db
from app.workers.notification_worker import run_notification_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_init_db:
        await init_db()

    worker_task = asyncio.create_task(run_notification_worker())
    try:
        yield
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Модульный монолит сервиса подачи и отслеживания заявок в УК",
    lifespan=lifespan,
)

app.include_router(api_router)