import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.init_db import init_db
from app.workers.notification_worker import run_notification_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


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
    version="0.3.0",
    description=(
        "Модульный монолит сервиса подачи и отслеживания заявок жителей в УК.\n\n"
        "**Статусы заявок:** `accepted` (Принята), `master_assigned` (Мастер назначен), "
        "`pending_confirmation` (Ожидает подтверждения), `closed` (Закрыта), `returned` (Возвращена)."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)