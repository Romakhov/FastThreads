# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Указываем переменную окружения PYTHONPATH
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Запускаем бота
CMD ["python", "bot.py"]
