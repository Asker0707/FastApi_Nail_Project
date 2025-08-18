"""
Модуль для работы с профилем пользователя.

Содержит API endpoints для получения статистики и данных профиля:
- Информация о прогрессе обучения
- Данные о завершенных уроках
- Последние пройденные уроки
- Достижения пользователя
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from auth.dependencies import get_current_user
from db import models
from db.database import get_db
from schemas.user_profile import ProfileDataResponse, LastLessonItem


router = APIRouter(tags=["Данные профиля"])


@router.get("/api/profile_data", response_model=ProfileDataResponse)
async def get_profile_data_api(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> ProfileDataResponse:
    """
    Возвращает статистику профиля текущего пользователя.

    Args:
        db (AsyncSession): Асинхронная сессия базы данных.
        current_user (models.User): Текущий аутентифицированный пользователь.

    Returns:
        ProfileDataResponse: Объект с данными профиля.
    """
    total_lessons = (await db.execute(select(
        func.count(models.Lesson.id)))).scalar() or 0

    completed = (await db.execute(
        select(func.count(models.LessonCompletion.id))
        .filter(models.LessonCompletion.user_id == current_user.id)
    )).scalar() or 0

    progress = round((completed / total_lessons) *
                     100, 2) if total_lessons else 0.0

    last_items = (await db.execute(
        select(models.LessonCompletion, models.Lesson)
        .join(models.Lesson,
              models.Lesson.id == models.LessonCompletion.lesson_id)
        .filter(models.LessonCompletion.user_id == current_user.id)
        .order_by(models.LessonCompletion.completed_at.desc())
        .limit(5)
    )).all()

    return ProfileDataResponse(
        full_name=current_user.full_name,
        email=current_user.email,
        progress_percent=progress,
        completed_lessons=completed,
        total_lessons=total_lessons,
        last_lessons=[
            LastLessonItem(
                title=lesson.title,
                date=completion.completed_at.strftime(
                    "%d.%m.%Y") if completion.completed_at else ""
            )
            for completion, lesson in last_items
        ]
    )
