"""HTTP-клиент до CRM automobili-zaluppini: единственная точка, где эта витрина
обращается наружу за контентом и посылает лиды.

Три read-эндпоинта (конфиг сайта, список авто, деталь авто) отдают то, что раньше
редактировалось в шаблонах этого репозитория — теперь правится только в
Django-админке CRM («Сайты-источники»). ``POST /api/v1/leads/create/`` — тот же
эндпоинт, что и раньше принимал форму лендинга, теперь вызывается с чужого домена;
он специально сделан в CRM публичным и csrf_exempt ровно для этого сценария.

Ответы config()/cars() кэшируются в локальном кэше Django на
``SITE_CONFIG_CACHE_TTL_SECONDS`` — это не источник истины (им остаётся CRM), а
защита от того, чтобы каждый визит на витрину бил по CRM отдельным запросом; сама
CRM уже кэширует конфиг по версии, так что это кэш поверх кэша, не подмена его.
Деталь авто не кэшируется здесь: страниц много, а на CRM для конфига уже есть
версионная инвалидация — не дублировать её для каждой машины отдельно.

Сетевая ошибка или таймаут не долетает до вьюх как есть — оборачивается в
``CrmUnavailableError``, чтобы вьюха могла показать страницу-заглушку вместо 500.
Ответ CRM с кодом ошибки (не 2xx и не 404 — 404 значит «не найдено», это не сбой)
оборачивается в ``CrmClientError`` с разобранным текстом причины (RFC 9457
Problem Details: поле ``detail``, иначе ``title``, иначе сырой текст).
"""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Final

import httpx
import structlog
from django.conf import settings
from django.core.cache import cache

logger = structlog.get_logger(__name__)

_UNSET: Final = object()


class CrmUnavailableError(Exception):
    """CRM не ответила вовремя или соединение не установилось. Не значит, что данных
    нет — значит, что сейчас нельзя сказать, есть они или нет."""


class CrmClientError(Exception):
    """CRM ответила кодом ошибки (кроме 404 — тот моделируется как ``None``)."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"CRM ответила {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class LeadSubmitResult:
    lead_id: int
    message: str


def _client() -> httpx.Client:
    # Новый клиент на вызов, не общий на процесс: так проще с потокобезопасностью под
    # gunicorn и не нужно думать о жизненном цикле пула соединений между запросами —
    # для частоты обращений этого сайта (посетитель, не поток телеметрии) это дешевле,
    # чем кажется, и надёжнее, чем общий клиент, переживающий воркер.
    return httpx.Client(base_url=settings.CRM_API_BASE_URL, timeout=settings.CRM_API_TIMEOUT_SECONDS)


def _cache_key(name: str) -> str:
    return f"crm:{settings.SITE_SLUG}:{name}"


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:500]
    if isinstance(body, dict):
        detail = body.get("detail") or body.get("title")
        if detail:
            return str(detail)
    return response.text[:500]


def _get(path: str) -> httpx.Response:
    try:
        with _client() as client:
            return client.get(path)
    except httpx.HTTPError as exc:
        logger.warning("crm_request_unreachable", path=path, exc_info=exc)
        raise CrmUnavailableError from exc


def _handle_json_or_404(response: httpx.Response) -> dict[str, Any] | None:
    if response.status_code == HTTPStatus.NOT_FOUND:
        return None
    if response.is_error:
        raise CrmClientError(response.status_code, _error_detail(response))
    return response.json()


def get_site_config() -> dict[str, Any] | None:
    """Конфиг сайта (branding/contacts/seo/calc/faq), или ``None`` если в CRM нет
    ``SourceSite`` с таким slug — это ошибка деплоя (переменная SITE_SLUG указывает
    не туда), а не что-то, что нормально увидит посетитель."""
    key = _cache_key("config")
    cached = cache.get(key, _UNSET)
    if cached is not _UNSET:
        return cached
    config_data = _handle_json_or_404(_get(f"/api/v1/sites/{settings.SITE_SLUG}/config/"))
    cache.set(key, config_data, settings.SITE_CONFIG_CACHE_TTL_SECONDS)
    return config_data


def get_cars() -> list[dict[str, Any]]:
    key = _cache_key("cars")
    cached = cache.get(key, _UNSET)
    if cached is not _UNSET:
        return cached
    payload = _handle_json_or_404(_get(f"/api/v1/sites/{settings.SITE_SLUG}/cars/"))
    cars = payload["cars"] if payload else []
    cache.set(key, cars, settings.SITE_CONFIG_CACHE_TTL_SECONDS)
    return cars


def get_car(car_slug: str) -> dict[str, Any] | None:
    return _handle_json_or_404(_get(f"/api/v1/sites/{settings.SITE_SLUG}/cars/{car_slug}/"))


def submit_lead(
    *,
    name: str,
    phone: str,
    car_name: str = "",
    utm_source: str = "",
    utm_medium: str = "",
    utm_campaign: str = "",
) -> LeadSubmitResult:
    payload = {
        "name": name,
        "phone": phone,
        "car_name": car_name,
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "utm_campaign": utm_campaign,
        "site": settings.SITE_SLUG,
    }
    try:
        with _client() as client:
            response = client.post("/api/v1/leads/create/", json=payload)
    except httpx.HTTPError as exc:
        logger.warning("crm_lead_submit_unreachable", exc_info=exc)
        raise CrmUnavailableError from exc
    if response.is_error:
        raise CrmClientError(response.status_code, _error_detail(response))
    data = response.json()
    return LeadSubmitResult(lead_id=data["lead_id"], message=data.get("message", ""))
