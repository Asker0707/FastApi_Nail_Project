import pytest


@pytest.mark.asyncio
async def test_root_page(async_client):
    response = await async_client.get("/")
    assert response.status_code == 200
    assert "Онлайн платформа по маникюру" in response.text or "<html" in response.text
