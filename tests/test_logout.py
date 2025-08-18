import pytest
from db.models import User

from auth.security import get_password_hash


@pytest.mark.asyncio
async def test_logout_clears_cookie(async_client, async_db):
    # 1. Создаём пользователя напрямую в БД
    user = User(
        full_name="Logout Test",
        email="logout@example.com",
        hashed_password=get_password_hash("logoutpass"),
    )
    async_db.add(user)
    await async_db.commit()

    # 2. Логинимся
    response = await async_client.post(
        "/auth/login", data={"username": "logout@example.com", "password": "logoutpass"}
    )

    assert response.status_code == 303
    assert "access_token" in response.cookies

    # 3. Устанавливаем cookie на клиенте
    access_token = response.cookies.get("access_token")
    async_client.cookies.set("access_token", access_token)

    # 4. Logout-запрос
    logout_response = await async_client.get("/auth/logout")

    assert logout_response.status_code in [303, 307]
    assert logout_response.headers["location"] == "/"

    # 5. Проверяем, что кука очищена
    assert (
        "access_token" not in logout_response.cookies
        or logout_response.cookies.get("access_token") == ""
    )
