"""Fail-fast guard for secrets read from the environment in production.

This site has no database and no authentication, so the blast radius of a weak
secret is smaller than in the CRM — but SECRET_KEY still signs the CSRF cookie
that protects the one state-changing endpoint this site has (the lead form). A
default or too-short value there is silent until someone forges a submission.
"""

from django.core.exceptions import ImproperlyConfigured

# Обе строки вида "django-insecure-..." (config/settings/base.py, development.py) уже
# покрыты проверкой ниже startswith("django-insecure-") — держать их здесь вторым
# элементом того же множества было недостижимым дублированием.
_INSECURE_DEFAULTS = frozenset({""})


def require_secure_secret(name: str, value: str, *, min_len: int = 32) -> None:
    if value in _INSECURE_DEFAULTS or value.startswith("django-insecure-"):
        msg = f"{name} is unset or uses the development default — set a real secret in production."
        raise ImproperlyConfigured(msg)
    if len(value) < min_len:
        msg = f"{name} must be at least {min_len} characters in production, got {len(value)}."
        raise ImproperlyConfigured(msg)
