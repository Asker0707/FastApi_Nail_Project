"""
Модуль аутентификации пользователей.

Включает функции для проверки учетных данных пользователя,
создания JWT токенов и установки куки для сессий,
а также вспомогательные исключения и основной поток логина.

Функции:
- authenticate_user: Проверка email и пароля,
    опциональная проверка прав администратора.
- create_auth_response: Формирование HTTP-редиректа
    с установкой JWT токена в cookie.
- authenticate_and_check_admin: Обертка для аутентификации
    с проверкой прав администратора.
- common_login_flow: Основной поток логина
    с обработкой исключений и редиректом.

Классы:
- AuthRedirectException: Исключение для управления
    редиректом при отсутствии аутентификации.

Используемые библиотеки:
- FastAPI (HTTPException, status, RedirectResponse)
- SQLAlchemy (AsyncSession, select)
- passlib (CryptContext)
- Локальные модули: auth.cookies, auth.security, db.models
"""
import logging

from fastapi import HTTPException, status
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext  # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from auth.cookies import create_flash_error_redirect, set_auth_cookie
from auth.security import create_access_token, verify_password
from db import models

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthRedirectException(HTTPException):
    """
    Исключение для редиректа неаутентифицированных пользователей.
    """

    def __init__(self, redirect_url: str):
        super().__init__(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            detail="Требуется аутентификация",
        )
        self.redirect_url = redirect_url


async def authenticate_user(
    email: str, password: str, db: AsyncSession, require_admin: bool = False
) -> models.User:
    """
    Аутентифицировать пользователя по email и паролю,
    проверить права администратора.

    Args:
        email (str): Email пользователя.
        password (str): Пароль пользователя.
        db (AsyncSession): Асинхронная сессия базы данных.
        require_admin (bool): Требовать права администратора.

    Raises:
        HTTPException: Если пользователь не найден,
        пароль неверен или нет прав администратора.

    Returns:
        models.User: Объект аутентифицированного пользователя.
    """
    normalized_email = email.lower().strip()
    result = await db.execute(
        select(models.User).where(models.User.email == normalized_email)
    )
    user = result.scalars().first()

    if not user or not verify_password(password, str(user.hashed_password)):
        logger.warning("Неудачная попытка входа для email: %s",
                       normalized_email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учетные данные"
        )

    if require_admin and not user.is_admin:
        logger.warning(
            "Пользователь %s попытался зайти в админку без прав",
            normalized_email
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас нет доступа к админке"
        )

    logger.info("Пользователь %s успешно аутентифицирован", normalized_email)
    return user


def create_auth_response(
        user: models.User,
        redirect_url: str
) -> RedirectResponse:
    """
    Создать RedirectResponse с JWT токеном в cookie
    для аутентифицированного пользователя.

    Args:
        user (models.User): Пользователь.
        redirect_url (str): URL для редиректа после входа.

    Returns:
        RedirectResponse: Ответ с редиректом и куки аутентификации.
    """
    token = create_access_token(data={"sub": user.email})
    response = RedirectResponse(
        url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    return set_auth_cookie(response, token)


async def authenticate_and_check_admin(
    email: str, password: str, db: AsyncSession, require_admin: bool = False
) -> models.User:
    """
    Аутентифицировать пользователя и проверить,
    является ли он администратором при необходимости.

    Args:
        email (str): Email пользователя.
        password (str): Пароль пользователя.
        db (AsyncSession): Асинхронная сессия базы данных.
        require_admin (bool): Флаг, требующий права администратора.

    Raises:
        HTTPException: Если аутентификация не удалась
        или нет прав администратора.

    Returns:
        models.User: Объект пользователя из базы данных.
    """
    user = await authenticate_user(
        email=email, password=password, db=db, require_admin=require_admin
    )
    return user


async def common_login_flow(
    username: str,
    password: str,
    db: AsyncSession,
    redirect_url: str,
    require_admin: bool = False,
) -> RedirectResponse:
    """
    Основной поток логина: аутентификация и
    создание ответа с куки и редиректом.

    Args:
        username (str): Email пользователя.
        password (str): Пароль пользователя.
        db (AsyncSession): Асинхронная сессия базы данных.
        redirect_url (str): URL для редиректа после успешного входа.
        require_admin (bool): Флаг, требующий права администратора.

    Returns:
        RedirectResponse: Ответ с редиректом и авторизационными куки.
    """
    try:
        user = await authenticate_and_check_admin(
            username, password, db,
            require_admin
        )
        return create_auth_response(user, redirect_url)
    except HTTPException as e:
        logger.warning(
            "Ошибка аутентификации пользователя %s: %s", username, e.detail)
        if e.status_code == 403:
            return create_flash_error_redirect(
                "/auth/login", "У вас нет доступа к админке"
            )
        return create_flash_error_redirect("/auth/login",
                                           "Неверный email или пароль")
    except Exception as e:
        logger.error(
            "Неожиданная ошибка при входе пользователя %s: %s", username, e)
        return create_flash_error_redirect("/auth/login",
                                           "Произошла ошибка при входе")
