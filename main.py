from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from auth import routes
from auth.utils import AuthRedirectException
from logging_config import setup_logging
from routers import frontend, lessons, notes, user_profile
from routers.admin import course_admin, lesson_admin

templates = Jinja2Templates(directory="templates")
setup_logging()


app = FastAPI(
    title="Онлайн платформа по маникюру",
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.exception_handler(AuthRedirectException)
async def auth_redirect_exception_handler(request: Request, exc: AuthRedirectException):
    """Обработчик для перенаправления при ошибках аутентификации"""
    return RedirectResponse(url=exc.redirect_url, status_code=exc.status_code)


@app.get("/", response_class=HTMLResponse)
async def read_root(
    request: Request,
):
    """
    Главная страница приложения.
    """
    return templates.TemplateResponse(request, "index.html")


# Подключение роутеров
app.include_router(frontend.router)
app.include_router(notes.router)
app.include_router(user_profile.router)
app.include_router(lessons.router)
app.include_router(course_admin.router)
app.include_router(lesson_admin.router)
app.include_router(routes.router)
