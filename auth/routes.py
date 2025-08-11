"""
Модуль аутентификации FastAPI.

Обеспечивает следующие функции:
- Регистрация новых пользователей через веб-форму
- Аутентификация пользователей (обычных и администраторов)
- Выход из системы
- Отображение страниц входа/регистрации
- Обработка ошибок аутентификации

Основные компоненты:
- Роутеры FastAPI для обработки HTTP запросов
- Интеграция с Jinja2 шаблонами для рендеринга HTML
- Взаимодействие с базой данных через SQLAlchemy AsyncSession
- Работа с cookies для хранения токенов и flash-сообщений
- Логирование всех значимых событий аутентификации
"""

import logging
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.cookies import clear_auth_cookie, create_flash_error_redirect
from auth.security import (
    add_to_blacklist,
    get_password_hash,
    is_token_blacklisted
)
from auth.utils import common_login_flow, create_auth_response
from db import models
from db.database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])
templates = Jinja2Templates(directory="templates")

logger = logging.getLogger(__name__)


@router.post("/register")
async def register_form(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """
    Обработать регистрацию нового пользователя через POST форму.

    Args:
        request (Request): HTTP запрос.
        full_name (str): Полное имя пользователя из формы.
        email (str): Email пользователя из формы.
        password (str): Пароль пользователя из формы.
        db (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        RedirectResponse:
        Перенаправление на страницу курсов при успешной регистрации
        или обратно на регистрацию с сообщением об ошибке.

    Raises:
        HTTPException: В случае ошибок работы с базой.
    """
    normalized_email = email.lower().strip()
    user_exists = await db.scalar(
        select(exists().where(models.User.email == normalized_email))
    )
    if user_exists:
        logger.warning(
            "Попытка регистрации с уже существующим email: %s",
            normalized_email
        )
        return create_flash_error_redirect(
            "/auth/register", "Email уже зарегистрирован"
        )

    new_user = models.User(
        email=normalized_email,
        full_name=full_name.strip(),
        hashed_password=get_password_hash(password),
    )

    try:
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info("Новый пользователь зарегистрирован: %s", normalized_email)
    except Exception as e:
        logger.error("Ошибка при создании пользователя %s: %s",
                     normalized_email, e)
        await db.rollback()
        return create_flash_error_redirect(
            "/auth/register", "Ошибка при регистрации пользователя"
        )

    return create_auth_response(new_user, "/courses")


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """
    Отобразить страницу регистрации с возможностью
    показать flash-сообщение об ошибке.

    Args:
        request (Request): HTTP запрос.

    Returns:
        HTMLResponse: Рендеринг страницы регистрации.
    """
    flash_error = request.cookies.get("flash_error")
    if flash_error:
        flash_error = unquote(flash_error)

    response = templates.TemplateResponse(
        "register.html", {"request": request, "flash_error": flash_error}
    )

    if flash_error:
        response.delete_cookie("flash_error")

    return response


@router.post("/login")
async def login_api(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    """
    Обработать POST запрос для аутентификации пользователя.

    Args:
        form_data (OAuth2PasswordRequestForm): Данные формы с
        username и password.
        db (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        RedirectResponse: Перенаправление на страницу
        курсов или обратно с ошибкой.
    """
    username = form_data.username.lower().strip()
    try:
        response = await common_login_flow(
            username=username,
            password=form_data.password,
            db=db,
            redirect_url="/courses",
        )
        logger.info("Пользователь успешно вошел: %s", username)
        return response
    except Exception:
        logger.warning(
            "Неудачная попытка входа для пользователя: %s", username)
        return create_flash_error_redirect("/auth/login",
                                           "Неверный email или пароль")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """
    Отобразить страницу входа с возможностью
    показать flash-сообщение об ошибке.

    Args:
        request (Request): HTTP запрос.

    Returns:
        HTMLResponse: Рендеринг страницы входа.
    """
    flash_error = request.cookies.get("flash_error")
    if flash_error:
        flash_error = unquote(flash_error)

    response = templates.TemplateResponse(
        "login.html", {"request": request, "flash_error": flash_error}
    )

    if flash_error:
        response.delete_cookie("flash_error")

    return response


@router.post("/admin_login")
async def admin_login_api(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    """
    Обработать POST запрос на вход администратора.

    Args:
        form_data (OAuth2PasswordRequestForm): Данные формы
        с username и password.
        db (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        RedirectResponse: Перенаправление на админку
        при успехе или на главную с ошибкой.
    """
    username = form_data.username.lower().strip()
    try:
        response = await common_login_flow(
            username=username,
            password=form_data.password,
            db=db,
            redirect_url="/admin/courses",
            require_admin=True,
        )
        logger.info("Администратор успешно вошел: %s", username)
        return response
    except HTTPException as e:
        error_msg = "Неверный email или пароль"
        if e.status_code == 403:
            error_msg = "Нет доступа к админке"
        logger.warning(
            "Неудачная попытка входа администратора %s: %s",
            username, error_msg
        )
        return create_flash_error_redirect("/", error_msg)
    except Exception as e:
        logger.error(
            "Неожиданная ошибка при входе администратора %s: %s", username, e)
        return create_flash_error_redirect("/", "Произошла ошибка при входе")


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    """
    Обработать выход пользователя из системы:
    - Добавить токен в черный список.
    - Очистить куки аутентификации.

    Args:
        request (Request): HTTP запрос.

    Returns:
        RedirectResponse: Перенаправление на главную страницу.
    """
    token = request.cookies.get("access_token")
    if token and not await is_token_blacklisted(token):
        await add_to_blacklist(token)
        logger.info("Токен пользователя добавлен в черный список при выходе")

    response = RedirectResponse(url="/")
    return clear_auth_cookie(response)
