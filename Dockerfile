# Сборка CSS отдельной стадией: Node нужен только на этапе билда, в рантайм-образ он не
# попадает. Тот же приём и те же пины базовых образов, что в
# automobili-zaluppini/app/Dockerfile — единый визуальный язык платформы держится общим
# тулингом сборки, не только общими цветами в конфиге, а обе CRM-стороны платформы
# заведомо крутятся на одних и тех же проверенных версиях базовых образов.
FROM node:24-alpine@sha256:e67514e5d0f6c46656005e1b693b2ec9d52e80b641307de684d4a015ba7a4eaf AS assets

WORKDIR /assets

COPY package.json package-lock.json tailwind.config.js ./
RUN npm ci --no-audit --no-fund

COPY static/src ./static/src
COPY templates ./templates
RUN npx tailwindcss -i ./static/src/input.css -o ./static/css/tailwind.css --minify

FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

COPY pyproject.toml ./
# Нет requirements.txt/лок-файла: этот репозиторий не собирался через uv локально
# (инструмент недоступен в среде, где он создавался). uv резолвит зависимости из
# [project.dependencies] при каждой сборке — не так воспроизводимо, как лок-файл у
# CRM, но корректно; `uv export -o requirements.txt` можно добавить отдельным PR,
# когда uv будет под рукой у того, кто это делает.
RUN uv pip install --no-cache -r pyproject.toml

COPY . .

FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY --from=builder /app /app
# Свежесобранный CSS кладётся поверх того, что лежит в репозитории: в образ должен
# попасть файл, собранный из текущих шаблонов, а не тот, что кто-то забыл пересобрать.
COPY --from=assets /assets/static/css/tailwind.css /app/static/css/tailwind.css

RUN addgroup --system appgroup && \
    adduser --system --group appuser && \
    mkdir -p /app/staticfiles && \
    chown -R appuser:appgroup /app

USER appuser

# SECRET_KEY здесь только чтобы пройти require_secure_secret() при импорте
# config.settings.production (нужен ей самой для сборки static-манифеста) — ключ
# из рантайма контейнера этот шаг не видит и не использует. Обязан быть длиннее 50
# символов, иначе тот же fail-fast, что защищает прод, роняет саму сборку образа.
RUN SECRET_KEY=build-only-not-used-at-runtime-0000000000000000000 \
    ALLOWED_HOSTS=localhost CSRF_TRUSTED_ORIGINS=https://localhost \
    python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
