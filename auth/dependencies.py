"""
Модуль для получения текущего аутентифицированного пользователя
и проверки прав администратора в FastAPI приложении.

Содержит зависимости для извлечения пользователя из JWT токена,
хранящегося в cookie, а также проверку,
что пользователь является администратором.

Используется в маршрутах для ограничения доступа и аутентификации.
"""

import logging

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import models
from db.database import get_db

from .security import decode_token

logger = logging.getLogger(__name__)


async def get_current_user(
    request: Request,
    access_token: str = Cookie(default=None, alias="access_token"),
    db: AsyncSession = Depends(get_db),
    raise_exc: bool = True,
) -> models.User | None:
    """
    Получить текущего аутентифицированного пользователя из JWT токена в cookie.

    Args:
        request (Request): Объект HTTP запроса.
        access_token (str | None): JWT токен из cookie.
        db (AsyncSession): Асинхронная сессия базы данных.
        raise_exc (bool): Выбрасывать исключение при
                    отсутствии токена или пользователя.

    Raises:
        HTTPException: При отсутствии токена или пользователя,
        если raise_exc=True.

    Returns:
        models.User | None: Объект пользователя или None,
        если raise_exc=False и пользователь не найден.
    """
    if hasattr(request.state, "current_user") and isinstance(
        request.state.current_user, models.User
    ):
        logger.debug("Текущий пользователь уже загружен в request.state")
        return request.state.current_user

    if not access_token:
        logger.info("Отсутствует JWT токен (access_token) в cookie.")
        if raise_exc:
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/auth/login"},
            )
        return None

    email = await decode_token(access_token, raise_exc=False)
    if not email:
        logger.info("Токен недействителен или email не найден в токене.")
        if raise_exc:
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/auth/login"},
            )
        return None

    result = await db.execute(
        select(models.User).where(models.User.email == email)
    )
    user = result.scalars().first()
    if not user:
        logger.warning(
            "Пользователь с email %s не"
            "найден в базе данных.", email)
        if raise_exc:
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/auth/login"},
            )
        return None

    request.state.current_user = user
    logger.debug("Текущий пользователь загружен: %s", email)
    return user


async def require_admin(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    """Проверяет, имеет ли текущий пользователь права администратора.

    Args:
        current_user (models.User): Авторизованный пользователь,
                                    полученный через
                                    зависимость get_current_user.

    Returns:
        models.User: Тот же объект пользователя,
                     если проверка пройдена успешно.

    Raises:
        HTTPException: Возникает с кодом состояния 403 (Forbidden),
                       если у пользователя
                       нет прав администратора.
    """
    if not current_user.is_admin:
        logger.warning(
            "Пользователь %s пытается получить доступ без"
            "прав администратора.",
            current_user.email,
        )
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Требуются права администратора"
        )
    logger.debug("Пользователь %s имеет права администратора.",
                 current_user.email)
    return current_user
