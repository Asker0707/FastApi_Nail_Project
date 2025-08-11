"""
Модуль маршрутов для работы с уроками.

Предоставляет функционал:
- Просмотр страницы урока с содержимым
- Отметка урока как завершенного
- Проверка статуса завершения урока

Зависимости:
- Требуется аутентифицированный пользователь
- Доступ к базе данных через AsyncSession
- Сервисный слой lesson_service для работы с уроками

Особенности:
- Использует шаблоны Jinja2 для рендеринга HTML
- Поддерживает JSON API для операций с завершением уроков
- Интегрируется с системой заметок пользователя
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from auth.dependencies import get_current_user
from db import models
from db.database import get_db
from services.lesson_service import (
    get_lesson_data,
    is_lesson_completed,
    mark_lesson_completed,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lessons", tags=["lessons"])
templates = Jinja2Templates(directory="templates")


@router.get("/{lesson_id}", response_class=HTMLResponse)
async def lesson_page(
    request: Request,
    lesson_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Отображает страницу урока с детальной информацией.

    Args:
        request (Request): Объект HTTP запроса
        lesson_id (UUID): Идентификатор урока
        db (AsyncSession): Асинхронная сессия базы данных
        current_user (models.User): Текущий аутентифицированный пользователь

    Returns:
        HTMLResponse: HTML страница с деталями урока

    Raises:
        HTTPException: 404 если урок не найден
    """
    lesson, course, text_html = await get_lesson_data(lesson_id, db)

    if not lesson:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Урок не найден")

    stmt = select(models.Note).filter_by(user_id=current_user.id,
                                         lesson_id=lesson_id)
    result = await db.execute(stmt)
    note = result.scalars().first()
    note_content = note.content if note else ""

    return templates.TemplateResponse(
        "lesson_detail.html",
        {
            "request": request,
            "user": current_user,
            "lesson": lesson,
            "lesson_text_html": text_html,
            "course": course,
            "note_content": note_content,
        },
    )


@router.put("/{lesson_id}/complete")
async def complete_lesson(
    lesson_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Отмечает урок как завершенный для текущего пользователя.

    Args:
        lesson_id (UUID): Идентификатор урока
        db (AsyncSession): Асинхронная сессия базы данных
        current_user (models.User): Текущий аутентифицированный пользователь

    Returns:
        JSONResponse: Результат операции в формате JSON

    Raises:
        HTTPException: 404 если урок не найден
    """
    result = await mark_lesson_completed(lesson_id, current_user.id, db)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Урок не найден")
    if not result:
        return JSONResponse(
            {"detail": "Урок уже завершён"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    return JSONResponse(
        {"detail": "Урок завершён"}, status_code=status.HTTP_201_CREATED
    )


@router.get("/{lesson_id}/complete")
async def lesson_completed_status(
    lesson_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Проверяет статус завершения урока для текущего пользователя.

    Args:
        lesson_id (UUID): Идентификатор урока
        db (AsyncSession): Асинхронная сессия базы данных
        current_user (models.User): Текущий аутентифицированный пользователь

    Returns:
        dict: Словарь с ключом 'completed' и булевым значением статуса
    """
    completed = await is_lesson_completed(lesson_id, current_user.id, db)
    return {"completed": completed}
