# GitLab CI/CD (Backend)

Файл пайплайна: `.gitlab-ci.yml`

## Что делает пайплайн

1. `test` — поднимает PostgreSQL service, делает `migrate` и запускает Django-тесты.
2. `docker` — собирает и публикует Docker-образ в `$CI_REGISTRY_IMAGE` через `kaniko` (без `docker:dind`).
3. `deploy` — по SSH обновляет контейнер backend на сервере.

## Обязательные GitLab Variables

Добавьте в `Settings -> CI/CD -> Variables`:

- `SSH_PRIVATE_KEY_B64` (masked + protected, base64 от приватного ключа)
- `STAGING_DEPLOY_HOST`
- `STAGING_DEPLOY_USER`
- `STAGING_BACKEND_ENV_FILE` (абсолютный путь к `.env` на staging, например `/opt/rms/backend/.env`)
- `PROD_DEPLOY_HOST`
- `PROD_DEPLOY_USER`
- `PROD_BACKEND_ENV_FILE` (абсолютный путь к `.env` на production)

Опционально для корпоративной сети без доступа к Docker Hub:

- `POSTGRES_IMAGE` (например `registry.company.local/ci/postgres:16-alpine`)

## Логика по веткам

- `develop`: test + docker + авто-деплой на staging.
- default branch (`main`): test + docker + ручной деплой на production.

## Требования на сервере

- Пользователь деплоя должен уметь выполнять Docker-команды.
- Сервер должен иметь доступ к GitLab Registry для `docker pull`.
- Файл, указанный в `*_BACKEND_ENV_FILE`, должен существовать на сервере.
- Runner для `backend:test` должен поддерживать GitLab `services` (обычно Docker executor).

`SSH_PRIVATE_KEY` тоже поддерживается (legacy), но для GitLab masked-переменных удобнее использовать `SSH_PRIVATE_KEY_B64`.
