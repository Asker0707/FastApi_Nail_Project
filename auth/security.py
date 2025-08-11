"""
Модуль security

В этом модуле реализованы функции для работы с безопасностью:
- Хеширование и проверка паролей с использованием bcrypt.
- Создание и декодирование JWT access токенов.
- Работа с черным списком JWT токенов в Redis (добавление и проверка).
- Обработка ошибок безопасности с использованием HTTP исключений и логирования.

Используемые библиотеки:
- passlib для безопасного хеширования паролей.
- jose для работы с JWT токенами.
- redis для хранения черного списка токенов.
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


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверить соответствие открытого пароля хешу.

    Args:
        plain_password (str): Открытый пароль.
        hashed_password (str): Хешированный пароль.

    Returns:
        bool: True, если пароль совпадает, иначе False.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Хешировать пароль с использованием bcrypt.

    Args:
        password (str): Открытый пароль.

    Returns:
        str: Хеш пароля.
    """
    return pwd_context.hash(password)


def create_access_token(data: dict) -> str:
    """
    Создать JWT access токен с временем жизни.

    Args:
        data (dict): Данные для кодирования в токене
        (например, {"sub": email}).

    Returns:
        str: Закодированный JWT токен.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


async def add_to_blacklist(token: str):
    """
    Добавить JWT токен в черный список Redis на время его жизни.

    Args:
        token (str): JWT токен.
    """
    try:
        expire_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        await redis.setex(f"blacklist:{token}", expire_seconds, "1")
        logger.info("Токен успешно добавлен в черный список")
    except RedisError as e:
        logger.error("Ошибка при добавлении токена в черный список: %s", e)


async def is_token_blacklisted(token: str) -> bool:
    """
    Проверить, находится ли токен в черном списке.

    Args:
        token (str): JWT токен.

    Returns:
        bool: True, если токен заблокирован, иначе False.
    """
    try:
        exists = await redis.exists(f"blacklist:{token}") == 1
        logger.debug("Проверка токена в черном списке: %s", exists)
        return exists
    except RedisError as e:
        logger.error("Ошибка при проверке токена в черном списке: %s", e)
        return False


async def decode_token(
    token: Optional[str],
    raise_exc: bool = True
) -> Optional[str]:
    """
    Декодировать JWT токен, проверить черный
    список и вернуть email пользователя.

    Args:
        token (Optional[str]): JWT токен.
        raise_exc (bool): Выбрасывать исключение
        при ошибке (по умолчанию True).

    Raises:
        HTTPException: Если токен отсутствует, отозван или некорректен.

    Returns:
        Optional[str]: Email пользователя из токена или None.
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
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: Optional[str] = payload.get("sub")
        if not email:
            if raise_exc:
                logger.warning("В токене отсутствует поле sub (email)")
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED, detail="Неверный токен"
                )
            return None
        return email
    except JWTError as e:
        logger.warning("Ошибка при декодировании токена: %s", e)
        if raise_exc:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Неверный токен"
            ) from e
        return None
