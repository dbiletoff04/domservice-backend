import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request as FastAPIRequest, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.init_db import init_db
from app.workers.notification_worker import run_notification_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

FIELD_LABELS = {
    "address": "адрес",
    "apartment": "номер квартиры",
    "category_id": "категорию проблемы",
    "description": "описание проблемы",
    "phone": "номер телефона",
    "code": "СМС-код",
    "comment": "комментарий",
}


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
    version="0.4.0",
    description=(
        "Модульный монолит сервиса подачи и отслеживания заявок жителей в УК.\n\n"
        "**Статусы заявок:** `accepted` (Принята), `master_assigned` (Мастер назначен), "
        "`pending_confirmation` (Ожидает подтверждения), `closed` (Закрыта), `returned` (Возвращена)."
    ),
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: FastAPIRequest, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    messages: list[str] = []

    for err in errors:
        loc = err.get("loc", ())
        field = str(loc[-1]) if loc else "поле"
        label = FIELD_LABELS.get(field, field)
        msg = str(err.get("msg", "Некорректное значение"))

        if msg.startswith("Value error, "):
            msg = msg.removeprefix("Value error, ")
        elif err.get("type") == "missing":
            msg = f"Не заполнено обязательное поле: {label}"
        elif err.get("type") in {"int_parsing", "int_type"}:
            msg = f"Поле «{label}» должно быть целым числом"
        elif err.get("type") == "greater_than_equal":
            msg = f"Некорректное значение поля «{label}»"

        messages.append(msg)

    detail = "; ".join(dict.fromkeys(messages)) if messages else "Некорректные входные данные"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": detail},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)