"""
    Конфигурация фикстур pytest для тестирования FastAPI-приложения.

    Содержит:
        - Подключение к временной базе данных SQLite в памяти.
        - Переопределение зависимости get_db для использования тестовой сессии.
        - Фикстуру prepare_database для создания и удаления таблиц на время сессии.
        - Фикстуру async_client для асинхронного тестового клиента (httpx.AsyncClient).
        - Фикстуру async_db для прямого доступа к тестовой БД внутри тестов.

    Использование:
        - async_client позволяет отправлять HTTP-запросы к приложению без запуска сервера.
        - async_db можно использовать для подготовки данных или проверки состояния базы.
"""
import pytest
from httpx import ASGITransport, AsyncClient
from db.models import Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from db.database import get_db
from main import app

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = async_sessionmaker(
    bind=engine_test, expire_on_commit=False, class_=AsyncSession
)


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture(scope="session", autouse=True)
async def prepare_database():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def async_client():
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
async def async_db():
    async with TestingSessionLocal() as session:
        yield session
