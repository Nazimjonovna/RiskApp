FROM python:3.11-slim

# Python settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Work directory
WORKDIR /app

# Requirements
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Project copy
COPY . .

# Port
EXPOSE 8000

# Gunicorn ishga tushirish
CMD ["gunicorn", "conf.wsgi:application", "--bind", "0.0.0.0:8000"]