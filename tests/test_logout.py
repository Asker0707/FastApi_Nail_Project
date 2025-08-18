"""
    Тесты для проверки выхода пользователя (logout) в FastAPI-приложении.

    Сценарий:
        - test_logout_clears_cookie:
            Проверяет корректный выход пользователя.
            Ожидается:
                * редирект на главную страницу (/),
                * удаление или обнуление cookie access_token после logout.
"""

import pytest
from db.models import User

from auth.security import get_password_hash


@pytest.mark.asyncio
async def test_logout_clears_cookie(async_client, async_db):
    user = User(
        full_name="Logout Test",
        email="logout@example.com",
        hashed_password=get_password_hash("logoutpass"),
    )
    async_db.add(user)
    await async_db.commit()

    response = await async_client.post(
        "/auth/login", data={"username": "logout@example.com", "password": "logoutpass"}
    )

    assert response.status_code == 303
    assert "access_token" in response.cookies

    access_token = response.cookies.get("access_token")
    async_client.cookies.set("access_token", access_token)

    logout_response = await async_client.get("/auth/logout")

    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/"

    assert (
        "access_token" not in logout_response.cookies
        or logout_response.cookies.get("access_token") == ""
    )
