from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.dev_demo import router as dev_demo_router  # TEMPORARY (ЛР6)
from app.api.dispatcher import router as dispatcher_router
from app.api.health import router as health_router
from app.api.manager import router as manager_router
from app.api.master import router as master_router
from app.api.notifications import router as notifications_router
from app.api.references import router as references_router
from app.api.requests import router as requests_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(references_router)
api_router.include_router(auth_router)
api_router.include_router(requests_router)
api_router.include_router(notifications_router)
api_router.include_router(dispatcher_router)
api_router.include_router(master_router)
api_router.include_router(manager_router)
api_router.include_router(dev_demo_router)  # TEMPORARY (ЛР6): удалить в ЛР7