FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

# Static fayllarni collect qilish
# Static fayllarni collect qilish
RUN DJANGO_SETTINGS_MODULE=conf.settings python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "conf.wsgi:application", "--bind", "0.0.0.0:8000"]