import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import AppUser

logger = logging.getLogger("domservice.sms_auth")


@dataclass
class SmsCodeRecord:
    code: str
    expires_at: datetime
    attempts: int = 0


# Временное хранилище одноразовых СМС-кодов в памяти процесса (TTL = 5 минут)
_SMS_CODES: dict[str, SmsCodeRecord] = {}


def normalize_phone(raw_phone: str) -> str:
    digits = re.sub(r"\D", "", raw_phone)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    elif len(digits) == 11 and digits.startswith("7"):
        pass
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный формат номера телефона. Пример: +79001112233",
        )
    return f"+{digits}"


def issue_sms_code(raw_phone: str) -> tuple[str, int]:
    """Генерирует одноразовый 4-значный код и записывает его в журнал программы вместо отправки СМС."""
    phone = normalize_phone(raw_phone)
    code = f"{secrets.randbelow(10000):04d}"
    ttl = settings.sms_code_ttl_seconds
    _SMS_CODES[phone] = SmsCodeRecord(
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl),
    )

    logger.info(
        "[SMS-ЗАГЛУШКА] Код для входа на номер %s: %s (действителен %s сек.)",
        phone,
        code,
        ttl,
    )
    return phone, ttl


def verify_sms_code(phone: str, code: str) -> None:
    record = _SMS_CODES.get(phone)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Код не запрашивался или уже использован. Запросите новый код.",
        )

    now = datetime.now(timezone.utc)
    if now > record.expires_at:
        _SMS_CODES.pop(phone, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Срок действия СМС-кода истёк. Запросите новый код.",
        )

    if record.code != code.strip():
        record.attempts += 1
        if record.attempts >= 5:
            _SMS_CODES.pop(phone, None)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Превышено число неверных попыток. Запросите новый код.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный СМС-код.",
        )

    # Код одноразовый — удаляем сразу после успешной проверки
    _SMS_CODES.pop(phone, None)


async def authenticate_with_sms(
    db: AsyncSession,
    raw_phone: str,
    code: str,
    consent_accepted: bool,
) -> tuple[str, AppUser]:
    phone = normalize_phone(raw_phone)
    verify_sms_code(phone, code)

    user = await db.scalar(select(AppUser).where(AppUser.phone == phone))
    now = datetime.now(timezone.utc)

    if user is None:
        if not consent_accepted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Необходимо согласие на обработку персональных данных (ФЗ-152)",
            )
        user = AppUser(
            phone=phone,
            full_name=None,
            role_code="resident",
            company_id=None,
            consent_at=now,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif user.consent_at is None:
        if not consent_accepted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="При первом входе необходимо согласие на обработку персональных данных (ФЗ-152)",
            )
        user.consent_at = now
        await db.commit()
        await db.refresh(user)

    token = create_access_token(user)
    logger.info(
        "[AUTH] Успешный вход: user_id=%s, phone=%s, role=%s",
        user.user_id,
        user.phone,
        user.role_code,
    )
    return token, user