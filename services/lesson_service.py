"""
Модуль для работы с уроками и их кешированием.

Основные функции:
- Получение данных урока (с поддержкой кеширования в Redis)
- Проверка и отметка завершения уроков пользователями
- Преобразование markdown-контента в HTML
- Управление кешем (запись, чтение, инвалидация)

Архитектура кеширования:
- Используется двухуровневое кеширование (Redis + БД)
- Ключи кеша версионируются для возможности сброса кеша
- Автоматическое обновление кеша при изменении данных
"""

import json
import logging
from uuid import UUID

import markdown
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from core.config import settings
from db import models
from redis_client import redis

logger = logging.getLogger(__name__)

CACHE_VERSION = "v1"
CACHE_LESSON_EXPIRE_SECONDS = settings.LESSON_CACHE_TTL
CACHE_COMPLETION_EXPIRE_SECONDS = settings.COMPLETION_CACHE_TTL


def get_lesson_cache_key(lesson_id: UUID) -> str:
    """
    Создаёт ключ кеша для урока.

    Args:
        lesson_id (UUID): UUID урока.

    Returns:
        str: Ключ кеша для Redis.
    """
    return f"{CACHE_VERSION}:lesson:{lesson_id}"


def get_completion_cache_key(user_id: UUID, lesson_id: UUID) -> str:
    """
    Создаёт ключ кеша для статуса завершения урока пользователем.

    Args:
        user_id (UUID): UUID пользователя.
        lesson_id (UUID): UUID урока.

    Returns:
        str: Ключ кеша для Redis.
    """
    return f"{CACHE_VERSION}:user:{user_id}:lesson:{lesson_id}:completed"


async def fetch_lesson_from_db(lesson_id: UUID, db: AsyncSession):
    """
    Получить данные урока из базы данных.

    Args:
        lesson_id (UUID): UUID урока.
        db (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        tuple: (словарь с данными урока, словарь с данными курса,
               html-текст урока)
        или (None, None, None), если урок не найден.

    Логирует ошибки преобразования markdown.
    """
    stmt = (
        select(models.Lesson)
        .options(joinedload(models.Lesson.course))
        .filter(models.Lesson.id == lesson_id)
    )
    result = await db.execute(stmt)
    lesson_obj = result.scalars().first()

    if not lesson_obj:
        logger.info("Урок с ID %s не найден в базе данных", lesson_id)
        return None, None, None

    video_url = f"/{lesson_obj.video_path}" if lesson_obj.video_path else None

    lesson = {
        "id": str(lesson_obj.id),
        "title": lesson_obj.title,
        "text_content": lesson_obj.text_content or "",
        "video_url": video_url,
        "course_id": str(lesson_obj.course_id),
    }
    course = {
        "id": str(lesson_obj.course.id),
        "title": lesson_obj.course.title,
    }

    try:
        text_html = markdown.markdown(lesson["text_content"])
    except Exception as e:
        logger.warning(
            "Ошибка рендеринга markdown для урока %s: %s", lesson_id, e
        )
        text_html = lesson["text_content"]

    return lesson, course, text_html


async def cache_lesson_data(
    cache_key: str, lesson: dict, course: dict, text_html: str
) -> None:
    """
    Кешировать данные урока в Redis.

    Args:
        cache_key (str): Ключ кеша.
        lesson (dict): Данные урока.
        course (dict): Данные курса.
        text_html (str): HTML-текст урока.

    Логирует ошибки при записи в Redis.
    """
    try:
        payload = {"lesson": lesson, "course": course, "text_html": text_html}
        logger.info("Сохраняем кеш урока по ключу %s", cache_key)
        await redis.setex(cache_key, CACHE_LESSON_EXPIRE_SECONDS,
                          json.dumps(payload))
    except Exception as e:
        logger.warning(
            "Ошибка Redis при записи кеша урока %s: %s", cache_key, e)


async def get_lesson_data(lesson_id: UUID, db: AsyncSession):
    """
    Получить данные урока, используя кеш Redis при наличии.

    Args:
        lesson_id (UUID): UUID урока.
        db (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        tuple: (словарь с данными урока,
                словарь с данными курса, html-текст урока)
    """
    cache_key = get_lesson_cache_key(lesson_id)

    try:
        cached = await redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            if isinstance(data, dict) and "lesson" in data:
                logger.info(
                    "Загружены данные урока из кеша по ключу %s", cache_key)
                return data["lesson"], data["course"], data["text_html"]
            logger.warning("Неверный формат кеша по ключу %s", cache_key)
    except json.JSONDecodeError as e:
        logger.warning(
            "Ошибка декодирования JSON из Redis для ключа %s: %s",
            cache_key, e)
    except Exception as e:
        logger.warning(
            "Ошибка Redis при чтении кеша урока %s: %s", cache_key, e)

    lesson, course, text_html = await fetch_lesson_from_db(lesson_id, db)

    if lesson:
        await cache_lesson_data(cache_key, lesson, course, text_html)

    return lesson, course, text_html


async def is_lesson_completed(lesson_id: UUID,
                              user_id: UUID,
                              db: AsyncSession) -> bool:
    """
    Проверяет, завершил ли пользователь урок.
    Использует кеш Redis для ускорения.

    Args:
        lesson_id (UUID): UUID урока.
        user_id (UUID): UUID пользователя.
        db (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        bool: True, если урок завершён пользователем, иначе False.

    Логирует ошибки работы с кешем.
    """
    cache_key = get_completion_cache_key(user_id, lesson_id)
    try:
        cached_status = await redis.get(cache_key)
        if cached_status is not None:
            logger.info(
                "Статус завершения урока %s пользователя %s взят из кеша",
                lesson_id, user_id
            )
            return cached_status == "true"
    except Exception:
        logger.exception(
            "Ошибка Redis при получении статуса завершения урока из кеша")

    stmt = select(models.LessonCompletion).filter_by(
        user_id=user_id, lesson_id=lesson_id
    )
    result = await db.execute(stmt)
    completed = result.scalars().first() is not None

    try:
        await redis.setex(
            cache_key, CACHE_COMPLETION_EXPIRE_SECONDS,
            "true" if completed else "false"
        )
        logger.info(
            "Обновлён кеш статуса завершения урока %s пользователя %s",
            lesson_id, user_id
        )
    except Exception:
        logger.exception(
            "Ошибка Redis при записи статуса завершения урока в кеш")

    return completed


async def mark_lesson_completed(
    lesson_id: UUID, user_id: UUID, db: AsyncSession
) -> bool | None:
    """
    Отметить урок как завершённый для пользователя.
    Возвращает:
        True — если отметка успешно добавлена,
        False — если урок уже был отмечен,
        None — если урок не найден.

    Args:
        lesson_id (UUID): UUID урока.
        user_id (UUID): UUID пользователя.
        db (AsyncSession): Асинхронная сессия базы данных.

    Логирует ошибки кеша и состояния базы.
    """
    stmt = select(models.Lesson).filter(models.Lesson.id == lesson_id)
    result = await db.execute(stmt)
    lesson = result.scalars().first()

    if not lesson:
        logger.info(
            "Урок с ID %s не найден при попытке отметить как завершённый",
            lesson_id
        )
        return None

    stmt = select(models.LessonCompletion).filter_by(
        user_id=user_id, lesson_id=lesson_id
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()

    if existing:
        logger.info(
            "Урок с ID %s уже отмечен как завершённый пользователем %s",
            lesson_id, user_id
        )
        return False

    completion = models.LessonCompletion(lesson_id=lesson_id, user_id=user_id)
    db.add(completion)
    await db.commit()
    logger.info(
        "Урок с ID %s успешно отмечен как завершённый пользователем %s",
        lesson_id, user_id
    )

    cache_key = get_completion_cache_key(user_id, lesson_id)
    try:
        await redis.setex(cache_key, CACHE_COMPLETION_EXPIRE_SECONDS, "true")
        logger.info(
            "Обновлён кеш статуса завершения урока для пользователя %s",
            user_id)
    except Exception as e:
        logger.warning(
            "Ошибка Redis при записи кеша статуса завершения урока: %s", e)

    lesson_cache_key = get_lesson_cache_key(lesson_id)
    try:
        await redis.delete(lesson_cache_key)
        logger.info("Инвалидация кеша урока с ключом %s", lesson_cache_key)
    except Exception as e:
        logger.warning("Ошибка Redis при удалении кеша урока: %s", e)

    return True
