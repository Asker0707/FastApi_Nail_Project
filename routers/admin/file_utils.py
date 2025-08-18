"""
    Утилиты для асинхронной работы с файлами:
    - сохранение загруженных файлов чанками
    - удаление файлов в отдельном потоке
    - создание директорий без блокировки event loop
"""

import os
import asyncio
import aiofiles
from fastapi import UploadFile


CHUNK_SIZE = 1024 * 1024


async def save_upload_file(upload_file: UploadFile, destination: str) -> None:
    """
    Асинхронно сохраняет загруженный файл чанками.

    Args:
        upload_file (UploadFile): Загруженный файл из формы
        destination (str): Путь для сохранения файла
    """
    async with aiofiles.open(destination, "wb") as f:
        while chunk := await upload_file.read(CHUNK_SIZE):
            await f.write(chunk)
    await upload_file.close()


async def create_dir(path: str) -> None:
    """
    Асинхронно создает директорию, если она не существует.

    Args:
        path (str): Путь к директории
    """
    await asyncio.to_thread(os.makedirs, path, exist_ok=True)


async def delete_file_async(path: str) -> None:
    """
    Асинхронно удаляет файл, если он существует.

    Args:
        path (str): Путь к файлу
    """
    if os.path.exists(path):
        await asyncio.to_thread(os.remove, path)
