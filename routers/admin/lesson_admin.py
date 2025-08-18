"""
Модуль административных маршрутов для управления уроками.

Предоставляет администратору интерфейс для:
- Просмотра списка уроков в курсе
- Создания новых уроков
- Редактирования существующих уроков
- Удаления уроков
- Загрузки видеофайлов для уроков

Основные особенности:
- Использует асинхронные запросы к базе данных
- Поддерживает загрузку видеофайлов
- Реализует инвалидацию кеша при изменении уроков
- Требует прав администратора для всех операций
- Использует шаблоны Jinja2 для рендеринга HTML
"""

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from .file_utils import save_upload_file, create_dir, delete_file_async
from auth.dependencies import require_admin
from db import models
from db.database import get_db
from redis_client import redis

templates = Jinja2Templates(directory="templates/")
router = APIRouter(prefix="/admin", tags=["Админские маршруты для уроков"])


def get_lesson_cache_key(lesson_id: UUID) -> str:
    """
    Генерирует ключ для хранения кеша урока в Redis.

    Args:
        lesson_id (UUID): Идентификатор урока

    Returns:
        str: Ключ для хранения в Redis в формате "lesson:{lesson_id}"
    """
    return f"lesson:{lesson_id}"


@router.get("/courses/{course_id}/lessons", response_class=HTMLResponse)
async def admin_lessons_list(
    request: Request,
    course_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    stmt = (
        select(models.Course)
        .options(selectinload(models.Course.lessons))
        .filter(models.Course.id == course_id)
    )

    result = await db.execute(stmt)
    course = result.scalars().first()

    if not course:
        raise HTTPException(404, "Курс не найден")

    return templates.TemplateResponse(
        "admin/lessons_list.html",
        {
            "request": request,
            "course": course,
            "lessons": course.lessons,
            "user": current_user,
        },
    )


@router.get("/courses/{course_id}/lessons/new", response_class=HTMLResponse)
async def new_lesson_page(
    request: Request,
    course_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    stmt = select(models.Course).filter(models.Course.id == course_id)
    result = await db.execute(stmt)
    course = result.scalars().first()

    if not course:
        raise HTTPException(404, "Курс не найден")

    return templates.TemplateResponse(
        "admin/lesson_form.html",
        {"request": request, "course": course, "lesson": None, "user": current_user},
    )


@router.post("/courses/{course_id}/lessons/create")
async def create_lesson(
    course_id: UUID = Path(...),
    title: str = Form(...),
    text_content: str = Form(""),
    video_file: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    stmt = select(models.Course).filter(models.Course.id == course_id)
    result = await db.execute(stmt)
    course = result.scalars().first()

    if not course:
        raise HTTPException(404, "Курс не найден")

    video_path = None
    if video_file and video_file.filename:
        save_dir = "static/videos"
        await create_dir(save_dir)
        save_path = f"{save_dir}/{video_file.filename}"
        await save_upload_file(video_file, save_path)
        video_path = save_path

    lesson = models.Lesson(
        course_id=course.id,
        title=title,
        text_content=text_content,
        video_path=video_path,
    )
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)

    return RedirectResponse(
        f"/admin/courses/{course_id}/lessons", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/lessons/{lesson_id}/edit", response_class=HTMLResponse)
async def edit_lesson_page(
    request: Request,
    lesson_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    stmt = (
        select(models.Lesson)
        .options(selectinload(models.Lesson.course))
        .filter(models.Lesson.id == lesson_id)
    )

    result = await db.execute(stmt)
    lesson = result.scalars().first()

    if not lesson:
        raise HTTPException(404, "Урок не найден")

    return templates.TemplateResponse(
        "admin/lesson_form.html",
        {
            "request": request,
            "course": lesson.course,
            "lesson": lesson,
            "user": current_user,
        },
    )


@router.post("/lessons/{lesson_id}/update")
async def update_lesson(
    lesson_id: UUID = Path(...),
    title: str = Form(...),
    text_content: str = Form(""),
    video_file: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    stmt = select(models.Lesson).filter(models.Lesson.id == lesson_id)
    result = await db.execute(stmt)
    lesson = result.scalars().first()

    if not lesson:
        raise HTTPException(404, "Урок не найден")

    if video_file and video_file.filename:
        if lesson.video_path:
            await delete_file_async(lesson.video_path)

        save_dir = "static/videos"
        await create_dir(save_dir)
        save_path = f"{save_dir}/{video_file.filename}"

        await save_upload_file(video_file, save_path)
        lesson.video_path = save_path

    lesson.title = title
    lesson.text_content = text_content
    await db.commit()

    lesson_cache_key = get_lesson_cache_key(lesson_id)
    await redis.delete(lesson_cache_key)

    return RedirectResponse(
        f"/admin/courses/{lesson.course_id}/lessons",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/lessons/{lesson_id}/delete")
async def delete_lesson(
    lesson_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    stmt = select(models.Lesson).filter(models.Lesson.id == lesson_id)
    result = await db.execute(stmt)
    lesson = result.scalars().first()

    if not lesson:
        raise HTTPException(404, "Урок не найден")

    course_id = lesson.course_id

    if lesson.video_path:
        await delete_file_async(lesson.video_path)

    await db.delete(lesson)
    await db.commit()

    lesson_cache_key = get_lesson_cache_key(lesson_id)
    await redis.delete(lesson_cache_key)

    pattern = f"user:*:lesson:{lesson_id}:completed"
    keys = redis.keys(pattern)
    if keys:
        redis.delete(*keys)

    return RedirectResponse(
        f"/admin/courses/{course_id}/lessons", status_code=status.HTTP_303_SEE_OTHER
    )
