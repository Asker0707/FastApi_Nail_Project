"""

Модуль конфигурации приложения.

Загружает настройки из переменных окружения или .env файла,
предоставляя типобезопасный доступ ко всем параметрам конфигурации.

Основные функции:
- Централизованное хранение всех настроек приложения
- Автоматическая загрузка из .env файла или переменных окружения
- Валидация типов и значений конфигурационных параметров
- Поддержка чувствительности к регистру для переменных окружения

"""


from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из переменных
       окружения или .env файла.

    Attributes:
        SECRET_KEY (str): Секретный ключ для генерации JWT токенов.
        ALGORITHM (str): Алгоритм шифрования для JWT (например, "HS256").
        ACCESS_TOKEN_EXPIRE_MINUTES (int): Время жизни access токена в минутах.
        DATABASE_URL (str): URL для подключения к основной базе данных.
        COOKIE_SECURE (bool): Флаг безопасных cookies (True для HTTPS).
        SAMESITE (str): Политика SameSite для cookies('lax', 'strict', 'none').
        REDIS_URL (str): URL для подключения к Redis (для кеширования).
        LESSON_CACHE_TTL (int): Время жизни кеша уроков в секундах.
        COMPLETION_CACHE_TTL (int): Время жизни кеша завершений в секундах.
        POSTGRES_USER (str): Имя пользователя PostgreSQL.
        POSTGRES_PASSWORD (str): Пароль PostgreSQL.
        POSTGRES_DB (str): Имя базы данных PostgreSQL.
        LOGIN_ATTEMPTS_LIMIT (int): Максимальное количество
                                    попыток входа перед блокировкой.
    """

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    DATABASE_URL: str
    COOKIE_SECURE: bool
    SAMESITE: str
    REDIS_URL: str
    LESSON_CACHE_TTL: int
    COMPLETION_CACHE_TTL: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    LOGIN_ATTEMPTS_LIMIT: int

    class Config:
        """Конфигурация для загрузки настроек.

        Attributes:
            env_file (str): Имя файла с переменными окружения.
            case_sensitive (bool): Чувствительность к регистру
                                   при загрузке переменных.
            env_file_encoding (str): Кодировка env файла.
        """
        env_file = ".env"
        case_sensitive = True
        env_file_encoding = "utf-8"


settings = Settings()  # type: ignore[call-arg]
