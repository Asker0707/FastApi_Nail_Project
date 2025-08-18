# Базовый образ Python
FROM python:3.12.3-slim-bookworm

# Создание системного пользователя
RUN addgroup --system --gid 1000 appuser && \
    adduser --system --uid 1000 --gid 1000 --no-create-home appuser

# Установка зависимостей для сборки и Postgres client
RUN apt-get update && \
    apt-get install -y gcc libpq-dev postgresql-client curl && \
    rm -rf /var/lib/apt/lists/*

# Установка переменных окружения
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app
ENV PATH="/home/appuser/.local/bin:${PATH}"

WORKDIR $APP_HOME

# Копируем pyproject.toml и poetry.lock
COPY pyproject.toml poetry.lock* $APP_HOME/

# Установка Poetry и зависимостей проекта от root
RUN pip install --upgrade pip && \
    pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --only main

# Копируем весь проект в контейнер
COPY . .

# Создаем директории и права для миграций и логов
RUN mkdir -p /app/migrations/versions && \
    chown -R appuser:appuser /app/migrations && \
    chmod -R 775 /app/migrations && \
    touch /app.log && chown appuser:appuser /app.log && chmod 664 /app.log

# Переключаемся на appuser
USER appuser

# Запуск приложения
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "main:app"]
