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


async def issue_sms_code(db: AsyncSession, raw_phone: str) -> tuple[str, int, bool]:
    """Генерирует код в журнал и сообщает сайту, нужно ли запрашивать согласие ПДн."""
    phone = normalize_phone(raw_phone)
    user = await db.scalar(select(AppUser).where(AppUser.phone == phone))
    requires_consent = user is None or user.consent_at is None

    code = f"{secrets.randbelow(10000):04d}"
    ttl = settings.sms_code_ttl_seconds
    _SMS_CODES[phone] = SmsCodeRecord(
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl),
    )

    logger.info(
        "[SMS-ЗАГЛУШКА] Код для входа на номер %s: %s (действителен %s сек., требуется согласие ПДн: %s)",
        phone,
        code,
        ttl,
        requires_consent,
    )
    return phone, ttl, requires_consent


def validate_sms_code(phone: str, code: str) -> None:
    """Проверяет код, не удаляя его до прохождения проверки согласия на ПДн."""
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


def consume_sms_code(phone: str) -> None:
    _SMS_CODES.pop(phone, None)


async def authenticate_with_sms(
    db: AsyncSession,
    raw_phone: str,
    code: str,
    consent_accepted: bool,
) -> tuple[str, AppUser]:
    phone = normalize_phone(raw_phone)
    validate_sms_code(phone, code)

    user = await db.scalar(select(AppUser).where(AppUser.phone == phone))
    now = datetime.now(timezone.utc)

    if user is None:
        if not consent_accepted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Необходимо согласие на обработку данных",
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
        logger.info("[CONSENT] Зарегистрирован новый пользователь и записано согласие: phone=%s, consent_at=%s", phone, now.isoformat())
    elif user.consent_at is None:
        if not consent_accepted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Необходимо согласие на обработку данных",
            )
        user.consent_at = now
        await db.commit()
        await db.refresh(user)
        logger.info("[CONSENT] Записано согласие при первом входе: user_id=%s, consent_at=%s", user.user_id, now.isoformat())

    # Удаляем одноразовый код только после успешного входа
    consume_sms_code(phone)

    token = create_access_token(user)
    logger.info(
        "[AUTH] Успешный вход: user_id=%s, phone=%s, role=%s",
        user.user_id,
        user.phone,
        user.role_code,
    )
    return token, user