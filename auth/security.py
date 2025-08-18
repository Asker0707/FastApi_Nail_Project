"""
Модуль security (улучшенная версия)

Функции:
- Хеширование и проверка паролей
- Создание и декодирование JWT access и refresh токенов
- Работа с черным списком JWT токенов в Redis
- Логирование и обработка ошибок безопасности
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt  # type: ignore
from passlib.context import CryptContext  # type: ignore
from redis.exceptions import RedisError

from core.config import settings
from redis_client import redis

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# -------------------- Вспомогательные функции -------------------- #

def utc_now() -> datetime:
    """Возвращает текущее UTC-время"""
    return datetime.now(timezone.utc)


def get_password_hash(password: str) -> str:
    """Хешировать пароль с использованием bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверить соответствие открытого пароля хешу"""
    return pwd_context.verify(plain_password, hashed_password)


# -------------------- JWT токены -------------------- #

def create_jwt_token(
    data: dict, expires_delta: timedelta,
    secret_key: str = settings.SECRET_KEY,
    algorithm: str = settings.ALGORITHM
) -> str:
    """
    Универсальная функция для создания JWT токена
    """
    to_encode = data.copy()
    now = utc_now()
    expire = now + expires_delta
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


def create_access_token(data: dict) -> str:
    """Создает JWT access токен"""
    return create_jwt_token(
        data,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(data: dict) -> str:
    """Создает JWT refresh токен на 30 дней"""
    return create_jwt_token(data, timedelta(days=30))


# -------------------- Черный список токенов -------------------- #

async def add_to_blacklist(token: str, raise_on_error: bool = False):
    """Добавить JWT токен в черный список Redis на время жизни токена"""
    try:
        expire_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        await redis.setex(f"blacklist:{token}", expire_seconds, "1")
        logger.info("Токен успешно добавлен в черный список")
    except RedisError as e:
        logger.error("Ошибка при добавлении токена в черный список: %s", e)
        if raise_on_error:
            raise


async def is_token_blacklisted(token: str) -> bool:
    """Проверить, находится ли токен в черном списке"""
    try:
        exists = await redis.exists(f"blacklist:{token}") == 1
        logger.debug("Проверка токена в черном списке: %s", exists)
        return exists
    except RedisError as e:
        logger.error("Ошибка при проверке токена в черном списке: %s", e)
        return False


# -------------------- Декодирование и проверка токена -------------------- #

async def decode_token(token: Optional[str], raise_exc: bool = True) -> Optional[str]:
    """
    Декодировать JWT токен, проверить черный список
    и вернуть email пользователя
    """
    if not token:
        if raise_exc:
            logger.warning("Отсутствует токен авторизации")
            raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                                detail="Не авторизован")
        return None

    if await is_token_blacklisted(token):
        if raise_exc:
            logger.warning("Токен был отозван и находится в черном списке")
            raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                                detail="Токен отозван")
        return None

    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        email = payload.get("sub")
        if not isinstance(email, str):
            if raise_exc:
                logger.warning(
                    "В токене отсутствует корректное поле sub (email)")
                raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                                    detail="Неверный токен")
            return None
        return email
    except JWTError as e:
        logger.warning("Ошибка при декодировании токена: %s", e)
        if raise_exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                                detail="Неверный токен") from e
        return None
