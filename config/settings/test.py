from .base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "127.0.0.1", "localhost"]

# Fixed, obviously-fake values so tests never depend on the CRM actually running —
# every test mocks storefront.crm_client itself.
CRM_API_BASE_URL = "http://crm.invalid"
SITE_SLUG = "test-site"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
}

# Тесты не собирают статику (STATIC_ROOT не существует) и её не раздают — без этого
# WhiteNoise на каждый тест печатает предупреждение о недостающей staticfiles/.
MIDDLEWARE = [m for m in MIDDLEWARE if m != "whitenoise.middleware.WhiteNoiseMiddleware"]  # noqa: F405
