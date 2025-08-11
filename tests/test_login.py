from urllib.parse import unquote

import pytest
from models import User

from auth.utils import get_password_hash


@pytest.mark.asyncio
async def test_login_success(async_client, async_db):
    """Успешный логин с правильными данными"""
    user = User(
        full_name="Test Login User",
        email="login@example.com",
        hashed_password=get_password_hash("secure123"),
    )
    async_db.add(user)
    await async_db.commit()
    await async_db.refresh(user)

    # Отправка запроса на логин
    response = await async_client.post(
        "/auth/login",
        data={
            "username": "login@example.com",  # OAuth2PasswordRequestForm
            "password": "secure123",
        },
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/courses"

    # Проверка наличия и значения cookie
    cookies = response.cookies
    assert "access_token" in cookies
    assert cookies["access_token"]


@pytest.mark.asyncio
async def test_login_wrong_credentials(async_client, async_db):
    """Попытка логина с неверными данными"""
    # Убедимся, что БД пуста (пользователь не создаётся)
    # Не удаляем явно, чтобы не нарушить FK через Alembic
    # Просто используем email, которого не существует

    response = await async_client.post(
        "/auth/login",
        data={"username": "wrong@example.com", "password": "wrongpassword"},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"

    # Проверка flash-сообщения в cookie
    assert "flash_error" in response.cookies
    assert unquote(response.cookies["flash_error"]) == "Неверный email или пароль"
