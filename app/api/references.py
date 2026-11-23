from fastapi import APIRouter
from app.schemas.common import RequestStatusCode
from app.schemas.references import CategoryReferenceItem, StatusReferenceItem

router = APIRouter(prefix="/references", tags=["Справочники"])


@router.get(
    "/statuses",
    response_model=list[StatusReferenceItem],
    summary="Получить перечень всех статусов заявки",
    description="Доступ: все пользователи. Возвращает 5 статусов жизненного цикла заявки (Р1).",
)
async def get_statuses() -> list[StatusReferenceItem]:
    return [
        StatusReferenceItem(
            status_code=RequestStatusCode.ACCEPTED,
            name="Принята",
            description="Заявка создана жителем или диспетчером",
        ),
        StatusReferenceItem(
            status_code=RequestStatusCode.MASTER_ASSIGNED,
            name="Мастер назначен",
            description="Назначены мастер и ориентировочный срок; после возврата выполняется заново",
        ),
        StatusReferenceItem(
            status_code=RequestStatusCode.PENDING_CONFIRMATION,
            name="Ожидает подтверждения",
            description="Мастер отметил работу выполненной, ожидается ответ жителя",
        ),
        StatusReferenceItem(
            status_code=RequestStatusCode.CLOSED,
            name="Закрыта",
            description="Житель подтвердил выполнение работ",
        ),
        StatusReferenceItem(
            status_code=RequestStatusCode.RETURNED,
            name="Возвращена",
            description="Житель сообщил, что проблема не решена; комментарий сохранён в истории",
        ),
    ]


@router.get(
    "/categories",
    response_model=list[CategoryReferenceItem],
    summary="Получить активные категории проблем",
    description="Доступ: все пользователи. Используется в форме создания заявки.",
)
async def get_categories() -> list[CategoryReferenceItem]:
    return [
        CategoryReferenceItem(category_id=1, name="Сантехника"),
        CategoryReferenceItem(category_id=2, name="Электрика"),
        CategoryReferenceItem(category_id=3, name="Отопление"),
        CategoryReferenceItem(category_id=4, name="Водоснабжение"),
        CategoryReferenceItem(category_id=5, name="Лифт"),
        CategoryReferenceItem(category_id=6, name="Другое"),
    ]