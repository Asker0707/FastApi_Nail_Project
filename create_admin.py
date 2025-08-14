import asyncio

from db.models import User
from sqlalchemy import select

from auth.security import get_password_hash
from db.database import async_session_factory



async def create_admin():
    admin_email = "admin@example.com"
    admin_password = "admin123"
    async with async_session_factory() as session:
        # Проверяем существование администратора
        result = await session.execute(
            select(User).where(User.email == admin_email)
        )
        existing = result.scalars().first()
        
        if existing:
            print("Администратор уже существует.")
            return

        # Создаем нового администратора
        admin = User(
            full_name="Администратор",
            email=admin_email,
            hashed_password=get_password_hash(admin_password),
            is_admin=True,
            role="admin"
        )
        
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        print(f"Администратор создан: {admin.email}")

if __name__ == "__main__":
    asyncio.run(create_admin())