"""
Модуль для работы с cookie в FastAPI:
- Установка и удаление cookie аутентификации
- Создание flash-сообщений об ошибках через cookie
"""

import logging
from typing import Literal
from urllib.parse import quote

from fastapi.responses import RedirectResponse

from core.config import settings

logger = logging.getLogger(__name__)


def set_auth_cookie(
        response: RedirectResponse,
        token: str
) -> RedirectResponse:
    """
    Устанавливает cookie с JWT токеном для аутентификации пользователя.

    Args:
        response (RedirectResponse): HTTP ответ с редиректом.
        token (str): JWT токен для аутентификации.

    Returns:
        RedirectResponse: Обновленный ответ с установленной cookie.
    """
    try:
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            secure=settings.COOKIE_SECURE,
            samesite=settings.SAMESITE,
        )
        logger.debug("Установлен cookie access_token для аутентификации.")
    except (TypeError, ValueError) as e:
        logger.error("Ошибка при установке cookie access_token: %s", e)
    return response


def clear_auth_cookie(response: RedirectResponse) -> RedirectResponse:
    """
    Очищает cookie аутентификации (удаляет access_token).

    Args:
        response (RedirectResponse): HTTP ответ с редиректом.

    Returns:
        RedirectResponse: Обновленный ответ с удаленной cookie.
    """
    try:
        response.delete_cookie(key="access_token", path="/")
        logger.debug("Удален cookie access_token.")
    except (TypeError, ValueError) as e:
        logger.error("Ошибка при удалении cookie access_token: %s", e)
    return response


def create_flash_error_redirect(url: str, message: str) -> RedirectResponse:
    """
    Создает RedirectResponse с установкой flash-сообщения об ошибке в cookie.

    Args:
        url (str): URL для редиректа.
        message (str): Текст flash-сообщения об ошибке.

    Returns:
        RedirectResponse: Ответ с редиректом и установленной flash cookie.
    """
    try:
        response = RedirectResponse(url=url, status_code=303)
        response.set_cookie(
            key="flash_error",
            value=quote(message),
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite=settings.SAMESITE,
        )
        logger.debug("Установлено flash-сообщение в cookie: %s", message)
    except (TypeError, ValueError) as e:
        logger.error("Ошибка при установке flash-сообщения в cookie: %s", e)
        response = RedirectResponse(url=url, status_code=303)
    return response
