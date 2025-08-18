# tests/test_auth.py

from urllib.parse import unquote

import pytest
from db.models import User
from sqlalchemy import select

from auth.security import get_password_hash


@pytest.mark.asyncio
async def test_register_success(async_client, async_db):
    response = await async_client.post(
        "/auth/register",
        data={
            "full_name": "Test User",
            "email": "test@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/courses"

    result = await async_db.execute(
        select(User).where(User.email == "test@example.com")
    )
    user = result.scalars().first()
    assert user is not None
    assert user.full_name == "Test User"


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client, async_db):
    user = User(
        full_name="Existing User",
        email="existing@example.com",
        hashed_password=get_password_hash("password"),
    )
    async_db.add(user)
    await async_db.commit()

    response = await async_client.post(
        "/auth/register",
        data={
            "full_name": "Another User",
            "email": "existing@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/auth/register"

    flash = response.cookies.get("flash_error")
    assert flash is not None
    assert unquote(flash) == "Email уже зарегистрирован"
