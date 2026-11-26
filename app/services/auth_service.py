import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.messages import (
    UI_ERROR_CONSENT_REQUIRED,
    UI_ERROR_PHONE_NOT_FOUND,
    UI_ERROR_WRONG_CODE,
)
from app.core.security import create_access_token
from app.models.user import AppUser

logger = logging.getLogger("domservice.sms_auth")


@dataclass
class SmsCodeRecord:
    code: str
    expires_at: datetime
    attempts: int = 0


# Хранилище одноразовых кодов по ключу (назначение: "login" | "register", телефон)
_SMS_CODES: dict[tuple[str, str], SmsCodeRecord] = {}


def normalize_phone(raw_phone: str) -> str:
    """
    Приводит корректный российский номер к виду 7XXXXXXXXXX (11 цифр, без '+').
    Отклоняет любые буквы, лишние символы, нехватку цифр при префиксе +7/8/7 и лишние цифры.
    """
    cleaned = re.sub(r"[\s\-\(\)]+", "", raw_phone.strip())
    if not cleaned or not re.fullmatch(r"\+?\d+", cleaned):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный формат номера телефона: допускаются только цифры",
        )

    if cleaned.startswith("+"):
        if not cleaned.startswith("+7") or len(cleaned) != 12:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Некорректный номер телефона: после +7 должно быть ровно 10 цифр",
            )
        return cleaned[1:]

    if len(cleaned) == 11 and cleaned[0] in {"7", "8"}:
        return "7" + cleaned[1:]

    if len(cleaned) == 10 and cleaned[0] == "9":
        return "7" + cleaned

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Некорректный номер телефона. Введите 11 цифр (например, +79001112233 или 89001112233)",
    )


async def find_user_by_phone(db: AsyncSession, canonical_phone: str) -> AppUser | None:
    """Ищет пользователя в БД независимо от того, сохранён ли номер с '+' или без '+'."""
    candidates = [canonical_phone, f"+{canonical_phone}"]
    return await db.scalar(
        select(AppUser)
        .where(AppUser.phone.in_(candidates))
        .order_by(AppUser.user_id.asc())
    )


def validate_sms_code(purpose: str, phone: str, code: str) -> None:
    """Проверяет одноразовый код (без удаления до успешного завершения операции)."""
    key = (purpose, phone)
    record = _SMS_CODES.get(key)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Код не запрашивался или уже использован. Запросите новый код.",
        )

    now = datetime.now(timezone.utc)
    if now > record.expires_at:
        _SMS_CODES.pop(key, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Срок действия СМС-кода истёк. Запросите новый код.",
        )

    if record.code != code.strip():
        record.attempts += 1
        if record.attempts >= 5:
            _SMS_CODES.pop(key, None)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Превышено число неверных попыток. Запросите новый код.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=UI_ERROR_WRONG_CODE,
        )


def consume_sms_code(purpose: str, phone: str) -> None:
    _SMS_CODES.pop((purpose, phone), None)


async def issue_login_code(db: AsyncSession, raw_phone: str) -> tuple[str, int]:
    """Запрос кода для АВТОРИЗАЦИИ: только если пользователь уже существует в БД."""
    phone = normalize_phone(raw_phone)
    user = await find_user_by_phone(db, phone)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=UI_ERROR_PHONE_NOT_FOUND,
        )

    code = f"{secrets.randbelow(10000):04d}"
    ttl = settings.sms_code_ttl_seconds
    _SMS_CODES[("login", phone)] = SmsCodeRecord(
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl),
    )

    logger.info(
        "[SMS-АВТОРИЗАЦИЯ] Код для входа на номер %s (%s, роль=%s): %s (действителен %s сек.)",
        phone,
        user.full_name or "без ФИО",
        user.role_code,
        code,
        ttl,
    )
    return phone, ttl


async def authenticate_with_sms(
    db: AsyncSession,
    raw_phone: str,
    code: str,
) -> tuple[str, AppUser]:
    """АВТОРИЗАЦИЯ существующего пользователя: не создаёт новых записей и не спрашивает согласие."""
    phone = normalize_phone(raw_phone)
    user = await find_user_by_phone(db, phone)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=UI_ERROR_PHONE_NOT_FOUND,
        )

    validate_sms_code("login", phone, code)
    consume_sms_code("login", phone)

    token = create_access_token(user)
    logger.info(
        "[AUTH] Успешный вход: user_id=%s, phone=%s, role=%s",
        user.user_id,
        user.phone,
        user.role_code,
    )
    return token, user


async def issue_register_code(db: AsyncSession, raw_phone: str) -> tuple[str, int]:
    """Запрос кода для РЕГИСТРАЦИИ: только если такого номера ещё нет в БД."""
    phone = normalize_phone(raw_phone)
    existing = await find_user_by_phone(db, phone)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким номером телефона уже зарегистрирован. Выполните вход.",
        )

    code = f"{secrets.randbelow(10000):04d}"
    ttl = settings.sms_code_ttl_seconds
    _SMS_CODES[("register", phone)] = SmsCodeRecord(
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl),
    )

    logger.info(
        "[SMS-РЕГИСТРАЦИЯ] Код подтверждения регистрации для номера %s: %s (действителен %s сек.)",
        phone,
        code,
        ttl,
    )
    return phone, ttl


async def register_resident(
    db: AsyncSession,
    raw_phone: str,
    full_name: str,
    code: str,
    consent_accepted: bool,
) -> tuple[str, AppUser]:
    """РЕГИСТРАЦИЯ нового жителя: требует ФИО, СМС-код и обязательное согласие на ПДн."""
    phone = normalize_phone(raw_phone)
    existing = await find_user_by_phone(db, phone)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким номером телефона уже зарегистрирован. Выполните вход.",
        )

    validate_sms_code("register", phone, code)

    if not consent_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=UI_ERROR_CONSENT_REQUIRED,
        )

    consume_sms_code("register", phone)

    now = datetime.now(timezone.utc)
    new_user = AppUser(
        phone=phone,
        full_name=full_name,
        role_code="resident",
        company_id=None,
        consent_at=now,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    token = create_access_token(new_user)
    logger.info(
        "[REGISTER] Зарегистрирован житель: user_id=%s, phone=%s, full_name=%s, consent_at=%s",
        new_user.user_id,
        new_user.phone,
        new_user.full_name,
        now.isoformat(),
    )
    return token, new_user