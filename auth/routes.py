"""
Модуль аутентификации FastAPI.

Обеспечивает:
- Регистрацию новых пользователей через веб-форму
- Аутентификацию пользователей (обычных и администраторов)
- Выход из системы
- Обновление access и refresh токенов
- Отображение страниц входа/регистрации с flash-сообщениями
- Обработку ошибок аутентификации

Основные улучшения:
- Унифицированная обработка flash-сообщений
- Вынесенные функции для рендеринга шаблонов и генерации RedirectResponse с токенами
- Расширенное логирование ошибок и неудачных попыток входа
- Централизованное создание и обновление токенов
"""

import logging
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.cookies import (
    clear_auth_cookie,
    clear_refresh_cookie,
    create_flash_error_redirect,
    set_auth_cookie,
    set_refresh_cookie
)
from auth.security import (
    add_to_blacklist,
    decode_token,
    get_password_hash,
    is_token_blacklisted,
    create_access_token,
    create_refresh_token
)
from auth.utils import common_login_flow
from db import models
from db.database import get_db

router = APIRouter(prefix="/auth", tags=["Аутентификация"])
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)

FLASH_EXPIRE_SECONDS = 300

def render_template_with_flash(request: Request, template_name: str, context: dict = {}) -> HTMLResponse:
    """
    Рендерит шаблон Jinja2 и автоматически извлекает flash_error из cookie.
    После рендера flash_error удаляется.

    Args:
        request (Request): HTTP запрос.
        template_name (str): Имя шаблона Jinja2.
        context (dict): Дополнительный контекст для шаблона.

    Returns:
        HTMLResponse: Отрендеренный шаблон с flash-сообщением.
    """
    flash_error = request.cookies.get("flash_error")
    if flash_error:
        flash_error = unquote(flash_error)
    context.update({"request": request, "flash_error": flash_error})
    response = templates.TemplateResponse(template_name, context)
    if flash_error:
        response.delete_cookie("flash_error")
    return response


async def perform_logout(request: Request) -> RedirectResponse:
    """
    Выход пользователя из системы:
    - Добавляет access token в черный список
    - Очищает cookie access_token и refresh_token

    Args:
        request (Request): HTTP запрос.

    Returns:
        RedirectResponse: Редирект на главную страницу.
    """
    access_token = request.cookies.get("access_token")
    if access_token and not await is_token_blacklisted(access_token):
        await add_to_blacklist(access_token)
        logger.info("Access token добавлен в черный список при logout")

    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response = clear_auth_cookie(response)
    response = clear_refresh_cookie(response)
    return response


def create_auth_response(user: models.User, redirect_url: str) -> RedirectResponse:
    """
    Создает RedirectResponse с установкой access и refresh токенов для пользователя.

    Args:
        user (models.User): Пользователь, которому выдаются токены.
        redirect_url (str): URL для редиректа после аутентификации.

    Returns:
        RedirectResponse: Редирект с установленными cookie токенами.
    """
    access_token = create_access_token({"sub": user.email})
    refresh_token = create_refresh_token({"sub": user.email})

    response = RedirectResponse(
        url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    response = set_auth_cookie(response, access_token)
    response = set_refresh_cookie(response, refresh_token)
    return response


async def refresh_user_tokens(user: models.User, redirect_url: str = "/courses") -> RedirectResponse:
    """
    Создает новые access и refresh токены для пользователя и возвращает RedirectResponse.

    Args:
        user (models.User): Пользователь.
        redirect_url (str): URL для редиректа.

    Returns:
        RedirectResponse: Редирект с новыми токенами.
    """
    return create_auth_response(user, redirect_url)



@router.post("/register")
async def register_form(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """
    Обрабатывает POST-запрос регистрации нового пользователя.

    Args:
        request (Request): Объект HTTP запроса.
        full_name (str): Полное имя пользователя из формы.
        email (str): Email пользователя из формы.
        password (str): Пароль пользователя из формы.
        db (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        RedirectResponse: Редирект на страницу курсов при успешной регистрации,
                          или редирект на страницу регистрации с flash-сообщением об ошибке.
    """
    normalized_email = email.lower().strip()
    user_exists = await db.scalar(select(exists().where(models.User.email == normalized_email)))
    if user_exists:
        logger.warning(
            "Попытка регистрации с уже существующим email: %s", normalized_email)
        return create_flash_error_redirect("/auth/register", "Email уже зарегистрирован")

    new_user = models.User(
        email=normalized_email,
        full_name=" ".join(word.capitalize()
                           for word in full_name.strip().split()),
        hashed_password=get_password_hash(password)
    )

    try:
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info("Новый пользователь зарегистрирован: %s", normalized_email)
    except Exception:
        await db.rollback()
        logger.exception(
            "Ошибка при создании пользователя %s", normalized_email)
        return create_flash_error_redirect("/auth/register", "Ошибка при регистрации пользователя")

    return create_auth_response(new_user, "/courses")


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """
    Отображает страницу регистрации с возможностью flash-сообщений.

    Args:
        request (Request): Объект HTTP запроса.

    Returns:
        TemplateResponse: HTML страница регистрации.
    """
    return render_template_with_flash(request, "register.html")



@router.post("/login")
async def login_api(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    """
    Обрабатывает POST-запрос логина обычного пользователя.

    Args:
        form_data (OAuth2PasswordRequestForm): Данные формы логина (username, password).
        db (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        RedirectResponse: Редирект на страницу курсов при успешном входе,
                          или редирект на страницу логина с flash-сообщением об ошибке.
    """
    username = form_data.username.lower().strip()
    try:
        response = await common_login_flow(
            username=username,
            password=form_data.password,
            db=db,
            redirect_url="/courses",
        )
        return response
    except Exception:
        logger.warning(
            "Неудачная попытка входа для пользователя: %s", username, exc_info=True)
        return create_flash_error_redirect("/auth/login", "Неверный email или пароль")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """
    Отображает страницу логина с возможностью flash-сообщений.

    Args:
        request (Request): Объект HTTP запроса.

    Returns:
        TemplateResponse: HTML страница логина.
    """
    return render_template_with_flash(request, "login.html")


@router.post("/admin_login")
async def admin_login_api(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    """
    Обрабатывает POST-запрос логина администратора.

    Args:
        form_data (OAuth2PasswordRequestForm): Данные формы логина (username, password).
        db (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        RedirectResponse: Редирект на админскую страницу курсов при успешном входе,
                          или редирект на главную страницу с flash-сообщением об ошибке.
    """
    username = form_data.username.lower().strip()
    try:
        response = await common_login_flow(
            username=username,
            password=form_data.password,
            db=db,
            redirect_url="/admin/courses",
            require_admin=True
        )
        logger.info("Администратор успешно вошел: %s", username)
        return response
    except Exception as e:
        error_msg = "Неверный email или пароль"
        if getattr(e, "status_code", None) == 403:
            error_msg = "Нет доступа к админке"
        logger.warning("Неудачная попытка входа администратора %s: %s",
                       username, error_msg, exc_info=True)
        return create_flash_error_redirect("/", error_msg)



@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    """
    Выход пользователя: удаление cookie и редирект на главную страницу.

    Args:
        request (Request): Объект HTTP запроса.

    Returns:
        RedirectResponse: Редирект после успешного выхода.
    """
    return await perform_logout(request)


@router.post("/refresh")
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    """
    Обновление JWT токенов пользователя через refresh_token cookie.

    Args:
        request (Request): Объект HTTP запроса.
        db (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        RedirectResponse: Редирект на главную или целевую страницу,
                          либо flash-сообщение при ошибке обновления токена.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        logger.warning("Попытка обновления токена без refresh token")
        return create_flash_error_redirect("/auth/login", "Отсутствует refresh token")

    email = await decode_token(refresh_token, raise_exc=False)
    if not email:
        logger.warning("Некорректный refresh token")
        return create_flash_error_redirect("/auth/login", "Некорректный refresh token")

    result = await db.execute(select(models.User).where(models.User.email == email))
    user = result.scalars().first()
    if not user:
        logger.warning("Пользователь не найден для refresh token: %s", email)
        return create_flash_error_redirect("/auth/login", "Пользователь не найден")

    return await refresh_user_tokens(user)
