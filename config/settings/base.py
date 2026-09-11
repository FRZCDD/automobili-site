"""Настройки, общие для всех окружений.

Этот сайт — тонкий рендерер: своей базы данных у него нет, весь контент (брендинг,
калькулятор, SEO, FAQ, каталог авто) приходит из CRM automobili-zaluppini по HTTP
(``storefront.crm_client``), а заявки уходят туда же в ``POST /api/v1/leads/create/``.
Поэтому в INSTALLED_APPS/MIDDLEWARE нет ни ``contrib.auth``, ни ``contrib.sessions``,
ни ``contrib.admin`` — они тянут за собой миграции и таблицы, которых здесь нет и не
будет. CSRF работает и без сессий (Django по умолчанию хранит токен в cookie, не в
сессии) — это единственная защита, которая здесь нужна: у сайта одна form-POST ручка
(приём лида), и она обязана быть защищена от подделки с чужого сайта.
"""

from pathlib import Path

import structlog
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY", default="django-insecure-local-development-key-12345")

ALLOWED_HOSTS: list[str] = config("ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv())
CSRF_TRUSTED_ORIGINS: list[str] = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TIME_ZONE = "Europe/Moscow"
USE_TZ = True
LANGUAGE_CODE = "ru-ru"

HEALTHCHECK_PATH = "/health/"

# --- CRM integration ---
# Единственный источник контента и единственная цель для лидов. См. storefront/crm_client.py.
CRM_API_BASE_URL = config("CRM_API_BASE_URL", default="http://127.0.0.1:8000")
SITE_SLUG = config("SITE_SLUG", default="autocredit")
CRM_API_TIMEOUT_SECONDS = config("CRM_API_TIMEOUT_SECONDS", default=5, cast=float)
SITE_CONFIG_CACHE_TTL_SECONDS = config("SITE_CONFIG_CACHE_TTL_SECONDS", default=60, cast=int)

# --- Installed applications ---
# django.contrib.staticfiles — единственное реально используемое приложение Django
# из "стандартного набора"; contenttypes идёт следом, потому что нужен ей самой.
DJANGO_APPS: list[str] = [
    "django.contrib.staticfiles",
    "django.contrib.contenttypes",
]

LOCAL_APPS: list[str] = [
    "storefront",
]

INSTALLED_APPS: list[str] = DJANGO_APPS + LOCAL_APPS

# --- Middleware ---
# Ни SessionMiddleware, ни AuthenticationMiddleware: нет ни сессий, ни пользователей.
# CsrfViewMiddleware работает поверх cookie, сессии ему не нужны.
MIDDLEWARE: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "storefront.context_processors.canonical_url",
            ],
        },
    },
]

# --- No database ---
# django.db.backends.dummy — Django's own placeholder for "no database configured".
# The app boots and the test runner works; any accidental ORM call fails loudly
# instead of silently reaching for a Postgres that doesn't exist here.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.dummy",
    },
}

# --- Cache ---
# Локальный, per-process кэш ответов CRM (см. storefront/crm_client.py) — не источник
# истины, просто защита от запроса к CRM на каждый визит. LocMem осознанно: у сайта нет
# ни Redis, ни БД, а короткий TTL (SITE_CONFIG_CACHE_TTL_SECONDS) делает несогласованность
# между воркерами прод-сервера незначительной.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
}

# --- Static files ---
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Logging ---
LOG_LEVEL = config("LOG_LEVEL", default="INFO")
LOG_FORMAT = config("LOG_FORMAT", default="console")

_shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]

structlog.configure(
    processors=[
        *_shared_processors,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": (
                structlog.processors.JSONRenderer() if LOG_FORMAT == "json" else structlog.dev.ConsoleRenderer()
            ),
            "foreign_pre_chain": _shared_processors,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
}
