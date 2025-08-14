FROM python:3.12.3-slim-bookworm

# Создаем системного пользователя с фиксированным UID
RUN addgroup --system --gid 1000 appuser && \
    adduser --system --uid 1000 --gid 1000 --no-create-home appuser

# Устанавливаем зависимости
RUN apt-get update && \
    apt-get install -y gcc libpq-dev postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# Переменные окружения
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV APP_HOME /app
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Рабочая директория
WORKDIR $APP_HOME

# Создаем папку для миграций с правильными правами
RUN mkdir -p /app/migrations/versions && \
    chown -R appuser:appuser /app/migrations && \
    chmod -R 775 /app/migrations

# Копируем и устанавливаем зависимости
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY --chown=appuser:appuser . .

# Меняем пользователя
RUN touch /app.log && chown appuser:appuser /app.log && chmod 664 /app.log
USER appuser

# Для production
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "main:app"]