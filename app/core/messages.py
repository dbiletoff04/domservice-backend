# Тексты интерфейса и ошибок из таблицы дизайнера Д2
UI_ERROR_PHONE_NOT_FOUND = "Введённый номер телефона не существует"
UI_ERROR_WRONG_CODE = "Введён неправильный код"
UI_ERROR_CONSENT_REQUIRED = "Согласие на обработку персональных данных обязательно"
UI_ERROR_CATEGORY_REQUIRED = "Не указан тип проблемы"
UI_ERROR_PLACE_REQUIRED = "Не указано место проблемы"
UI_ERROR_SEND_FAILED = (
    "Произошла ошибка. Проверьте интернет-соединение и попытайтесь снова"
)

# Шаблоны текстов уведомлений жителю при смене статуса (US-5.3)
def format_status_notification(
    status_code: str,
    request_number: str,
    master_name: str | None = None,
    deadline_display: str | None = None,
) -> str:
    if status_code == "accepted":
        return f"Заявка {request_number} принята в работу."
    if status_code == "master_assigned":
        master_part = f"Назначен мастер {master_name}" if master_name else "Мастер назначен"
        deadline_part = f"Плановый срок: {deadline_display}" if deadline_display else "Срок: Уточняется"
        return f"Заявка {request_number}: {master_part}. {deadline_part}."
    if status_code == "pending_confirmation":
        return f"Заявка {request_number}: работа выполнена, подтвердите результат («Принять работу» или «Проблема не решена»)."
    if status_code == "closed":
        return f"Заявка {request_number} закрыта."
    if status_code == "returned":
        return f"Заявка {request_number} возвращена в работу."
    return f"Статус заявки {request_number} обновлён."