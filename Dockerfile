# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем системные зависимости для компиляции пакетов
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Указываем переменную окружения PYTHONPATH
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Запускаем бота
CMD ["python", "bot.py"]
