# Nailis.hub - Онлайн Платформа для Обучения Маникюру
## Описание проекта
Nailis.hub - это современная веб-платформа для онлайн обучения маникюру, разработанная с использованием FastAPI. Платформа предоставляет возможность проходить курсы, смотреть видео-уроки, делать заметки и отслеживать прогресс обучения.
## Основные функции
- 🔐 Аутентификация и авторизация пользователей
- 📚 Управление курсами и уроками
- 📝 Система заметок к урокам
- 📊 Отслеживание прогресса обучения
- 🎥 Поддержка видео-контента
- 💾 Кеширование данных через Redis
- 👩‍💼 Административная панель
## Технологический стек
- **Backend**: FastAPI, Python 3.8+
- **База данных**: PostgreSQL, SQLAlchemy (async)
- **Кеширование**: Redis
- **Фронтенд**: HTML, CSS, JavaScript, Bootstrap 5
- **Шаблонизатор**: Jinja2
- **Аутентификация**: JWT tokens
- **Миграции**: Alembic
## Установка и запуск
### Предварительные требования
- Python 3.8+
- PostgreSQL
- Redis
### Установка зависимостей
bash
pip install -r requirements.txt



### Настройка окружения
1. Создайте файл `.env` в корневой директории проекта:
env
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname
REDIS_URL=redis://localhost
COOKIE_SECURE=false
SAMESITE=lax
LESSON_CACHE_TTL=3600
COMPLETION_CACHE_TTL=3600



2. Создайте базу данных:
bash
createdb dbname



3. Примените миграции:
bash
alembic upgrade head



### Запуск приложения
bash
uvicorn main:app --reload



## Структура проекта
FAST_API_1/
├── alembic/              # Миграции базы данных
├── auth/                 # Аутентификация и авторизация
├── core/                 # Основные настройки
├── db/                   # Модели и конфигурация БД
├── routers/             # Маршруты API
├── schemas/             # Pydantic модели
├── services/            # Бизнес-логика
├── static/              # Статические файлы
├── templates/           # HTML шаблоны
└── tests/               # Тесты



## API Endpoints
### Аутентификация
- `POST /auth/register` - Регистрация нового пользователя
- `POST /auth/login` - Вход в систему
- `GET /auth/logout` - Выход из системы
### Курсы и уроки
- `GET /courses` - Список всех курсов
- `GET /courses/{course_id}` - Детали курса
- `GET /lessons/{lesson_id}` - Просмотр урока
- `PUT /lessons/{lesson_id}/complete` - Отметить урок как завершенный
### Заметки
- `GET /lessons/{lesson_id}/notes` - Получить заметки к уроку
- `POST /lessons/{lesson_id}/note` - Создать новую заметку
- `PUT /lessons/{lesson_id}/note/{note_id}` - Обновить заметку
- `DELETE /lessons/{lesson_id}/note/{note_id}` - Удалить заметку
## Тестирование
bash
pytest



## Разработчики
- [Аскер] - Основной разработчик
## Лицензия
MIT License
## Контакты
Email: [asker_original@mail.ru]