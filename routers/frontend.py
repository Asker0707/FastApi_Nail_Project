"""
Модуль маршрутов веб-интерфейса FastAPI.

Обеспечивает отображение HTML-страниц через Jinja2 шаблоны и взаимодействие
с базой данных для следующих функций:
- Аутентификация (страница входа)
- Личный кабинет (дашборд, профиль)
- Работа с курсами (список, детали курса)
- Работа с уроками (просмотр, заметки)

Основные компоненты:
- Роутеры FastAPI для обработки HTTP GET запросов
- Интеграция с Jinja2 шаблонами
- Асинхронное взаимодействие с базой данных через SQLAlchemy
- Зависимости для получения текущего пользователя и сессии БД
- Кеширование данных уроков через Redis
"""

import logging
from urllib.parse import unquote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from services.lesson_service import get_lesson_data
from auth.dependencies import get_current_user
from db import models
from db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """
    Отображает страницу входа с возможностью показа flash-сообщения об ошибке.

    Args:
        request (Request): Объект HTTP запроса.

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


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request,
                         db: AsyncSession = Depends(get_db),
                         current_user: models.User = Depends(get_current_user)
                         ):
    """
    Отображает дашборд пользователя с его последними заметками.

    Args:
        deps (dict): Общие зависимости (db, current_user).
        request (Request): HTTP запрос.

    Returns:
        HTMLResponse: Рендеринг страницы дашборда с заметками.
    """

    stmt = (
        select(models.Note, models.Lesson)
        .join(models.Lesson, models.Note.lesson_id == models.Lesson.id)
        .filter(models.Note.user_id == current_user.id)
        .order_by(models.Note.created_at.desc())
    )
    result = await db.execute(stmt)
    notes = result.all()

    note_data = [
        {
            "lesson_id": lesson.id,
            "lesson_title": lesson.title,
            "content": note.content,
        }
        for note, lesson in notes
    ]

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": current_user, "notes": note_data},
    )


@router.get("/courses", response_class=HTMLResponse)
async def courses_page(request: Request,
                       db: AsyncSession = Depends(get_db),
                       current_user: models.User = Depends(get_current_user)
                       ):
    """
    Страница отображает список всех курсов.

    Args:
        deps (dict): Общие зависимости (db, current_user).
        request (Request): HTTP запрос.

    Returns:
        HTMLResponse: Рендеринг страницы со списком курсов.
    """

    result = await db.execute(select(models.Course))
    courses = result.scalars().all()

    return templates.TemplateResponse(
        "courses.html", {"request": request,
                         "user": current_user, "courses": courses}
    )


@router.get("/courses/{course_id}", response_class=HTMLResponse)
async def course_page(
    request: Request,
    course_id: UUID = Path(..., description="UUID курса"),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Отображает детальную страницу курса с его уроками.

    Args:
        course_id (UUID): Идентификатор курса.
        deps (dict): Общие зависимости (db, current_user).
        request (Request): HTTP запрос.

    Raises:
        HTTPException 404: Если курс с заданным ID не найден.

    Returns:
        HTMLResponse: Рендеринг страницы с деталями курса и списком уроков.
    """
    course_result = await db.execute(
        select(models.Course)
        .options(joinedload(models.Course.lessons))
        .filter(models.Course.id == course_id)
    )
    course = course_result.scalars().first()

    if not course:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Курс не найден")

    lessons_list = course.lessons or []

    return templates.TemplateResponse(
        "course_detail.html",
        {
            "request": request,
            "user": current_user,
            "is_admin": current_user.is_admin,
            "course": course,
            "lessons": lessons_list,
        },
    )


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request,
                       current_user: models.User = Depends(get_current_user)):
    """
    Отображает страницу профиля пользователя с личными данными.

    Args:
        deps (dict): Общие зависимости (db, current_user).
        request (Request): HTTP запрос.

    Returns:
        HTMLResponse: Рендеринг страницы профиля.
    """

    return templates.TemplateResponse(
        "profile.html", {"request": request, "user": current_user}
    )


@router.get("/lessons/{lesson_id}", response_class=HTMLResponse)
async def lesson_page(
    request: Request,
    lesson_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Отображает страницу урока.

    Args:
        
        lesson_id: id урока
        db (AsyncSession): Асинхронная сессия базы данных
        current_user (models.User): Текущий аутентифицированный пользователь
        request (Request): HTTP запрос.

    Returns:
        HTMLResponse: Рендеринг страницы профиля.
    """
    lesson, course, text_html = await get_lesson_data(lesson_id, db)

    if not lesson:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Урок не найден")

    note_result = await db.execute(
        select(models.Note).filter_by(
            user_id=current_user.id, lesson_id=lesson_id)
    )
    note = note_result.scalars().first()
    note_content = note.content if note else ""

    return templates.TemplateResponse(
        "lesson/lesson_detail.html",
        {
            "request": request,
            "user": current_user,
            "lesson": lesson,
            "lesson_text_html": text_html,
            "course": course,
            "note_content": note_content,
        },
    )
