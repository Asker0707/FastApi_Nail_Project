"""
Модуль административных маршрутов для управления курсами.

Предоставляет администратору интерфейс для:
- Просмотра списка всех курсов
- Создания новых курсов
- Редактирования существующих курсов
- Удаления курсов

Основные функции:
- admin_courses_page: Отображение списка курсов
- new_course_page: Форма создания нового курса
- create_course_form: Обработка создания курса
- edit_course_page: Форма редактирования курса
- update_course: Обработка обновления курса
- delete_course: Удаление курса
"""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from auth.dependencies import require_admin
from db import models
from db.database import get_db

router = APIRouter(prefix="/admin/courses", tags=["Админские маршруты для курсов"])

templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def admin_courses_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    """
    Отображает страницу со списком всех курсов для администратора.

    Args:
        request (Request): Объект HTTP-запроса.
        db (AsyncSession): Асинхронная сессия базы данных.
        current_user (models.User): Текущий аутентифицированный 
                                    ользователь (администратор).

    Returns:
        HTMLResponse: Ответ с отрендеренным шаблоном списка курсов.
    """
    result = await db.execute(select(models.Course))
    courses = result.scalars().all()

    return templates.TemplateResponse(
        "admin/course_list.html",
        {
            "request": request,
            "courses": courses,
            "user": current_user,
            "is_admin": current_user.is_admin,
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_course_page(
    request: Request, current_user: models.User = Depends(require_admin)
):
    """
    Отображает форму для создания нового курса.

    Args:
        request (Request): Объект HTTP-запроса.
        current_user (models.User): Текущий аутентифицированный
                                    пользователь (администратор).

    Returns:
        HTMLResponse: Ответ с отрендеренной формой создания курса.
    """
    return templates.TemplateResponse(
        "admin/course_form.html",
        {"request": request, "course": None, "user": current_user},
    )


@router.post("/create")
async def create_course_form(
    title: str = Form(...),
    description: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    """
    Обрабатывает отправку формы создания нового курса.

    Args:
        title (str): Название курса из формы.
        description (str): Описание курса из формы.
        db (AsyncSession): Асинхронная сессия базы данных.
        current_user (models.User): Текущий аутентифицированный
                                    пользователь (администратор).

    Returns:
        RedirectResponse: Перенаправление на страницу
                          списка курсов после создания.
    """
    course = models.Course(title=title, description=description)
    db.add(course)
    await db.commit()
    return RedirectResponse("/admin/courses",
                            status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{course_id}/edit", response_class=HTMLResponse)
async def edit_course_page(
    course_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    """
    Отображает форму редактирования существующего курса.

    Args:
        course_id (str): UUID курса для редактирования.
        request (Request): Объект HTTP-запроса.
        db (AsyncSession): Асинхронная сессия базы данных.
        current_user (models.User): Текущий аутентифицированный
                                    пользователь (администратор).

    Returns:
        HTMLResponse: Ответ с отрендеренной формой редактирования курса.

    Raises:
        HTTPException: 404 если курс не найден.
    """
    result = await db.execute(
        select(models.Course).filter(models.Course.id == course_id)
    )
    course = result.scalars().first()

    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    return templates.TemplateResponse(
        "admin/course_edit.html",
        {"request": request, "course": course, "user": current_user},
    )


@router.post("/{course_id}/edit")
async def update_course(
    course_id: str,
    title: str = Form(...),
    description: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    """
    Обрабатывает отправку формы обновления курса.

    Args:
        course_id (str): UUID редактируемого курса.
        title (str): Новое название курса из формы.
        description (str): Новое описание курса из формы.
        db (AsyncSession): Асинхронная сессия базы данных.
        current_user (models.User): Текущий аутентифицированный
                                    пользователь (администратор).

    Returns:
        RedirectResponse: Перенаправление на страницу
                          списка курсов после обновления.

    Raises:
        HTTPException: 404 если курс не найден.
    """
    result = await db.execute(
        select(models.Course).filter(models.Course.id == course_id)
    )
    course = result.scalars().first()

    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    course.title = title
    course.description = description
    await db.commit()

    return RedirectResponse(url="/admin/courses", status_code=303)


@router.get("/{course_id}/delete")
async def delete_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    """
    Обрабатывает удаление курса.

    Args:
        course_id (str): UUID удаляемого курса.
        db (AsyncSession): Асинхронная сессия базы данных.
        current_user (models.User): Текущий аутентифицированный 
                                    пользователь (администратор).

    Returns:
        RedirectResponse: Перенаправление на страницу
                          списка курсов после удаления.

    Raises:
        HTTPException: 404 если курс не найден.
    """
    result = await db.execute(
        select(models.Course).filter(models.Course.id == course_id)
    )
    course = result.scalars().first()

    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    await db.delete(course)
    await db.commit()

    return RedirectResponse(url="/admin/courses", status_code=303)
