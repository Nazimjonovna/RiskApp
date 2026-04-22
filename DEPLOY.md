# Deployment (Docker, no CI)

This project is deployed manually via Docker from the repo on the server.

## 1) Подготовка на сервере

1. Установите Docker + Docker Compose plugin.
2. Скопируйте код в нужную папку и зайдите в `backend`.
3. Создайте `.env.production` на основе `.env.example`:

```bash
cp .env.example .env.production
```

4. Отредактируйте `.env.production`:

- DB host/credentials/user/password
- `SECRET_KEY`, `DEBUG=False`
- `RUN_MIGRATIONS=true` for first run or every deployment
- allowed hosts / cors
- `OIDC_*` settings

5. Убедитесь, что внешний network существует:

```bash
docker network create riskapp-network || true
```

## 2) Деплой

```bash
./deploy.sh
```

Скрипт выполняет:

- `docker compose -f docker-compose.prod.yml down --remove-orphans`
- `docker compose -f docker-compose.prod.yml up -d --build`

## 3) Проверка

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f backend
```

Для остановки:

```bash
docker compose -f docker-compose.prod.yml down
```
