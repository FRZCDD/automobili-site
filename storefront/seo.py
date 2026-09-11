"""SEO: безопасная подстановка в шаблон заголовка/описания карточки авто (эти
шаблоны редактируются в CRM-админке — ``seo_title_car_template`` /
``seo_description_car_template`` на ``SourceSite``) и сборка JSON-LD.

CRM отдаёт сырой текст шаблона (``{brand} {model} {year} {price} {monthly}``), а не
готовую строку: подставлять данные конкретного авто может только тот, у кого есть
и шаблон, и авто одновременно — то есть эта витрина, не CRM. Подстановка через
``str.format`` здесь была бы тем же самым примитивом раскрытия данных, что и в
одноимённом методе CRM (``SourceSite.render_car_seo``): строка редактируется в
админке человеком, а не системой, поэтому её нельзя выполнять как формат-строку.
Вместо этого — точечная замена только пяти разрешённых токенов через regex.
"""

from __future__ import annotations

import json
import re
from typing import Any

from django.http import HttpRequest

_TOKEN_RE = re.compile(r"\{([^{}]*)\}")
_ALLOWED_TOKENS = frozenset({"brand", "model", "year", "price", "monthly"})


def render_seo_template(template: str, **values: object) -> str:
    """Подставляет ``{brand}``, ``{model}``, ``{year}``, ``{price}``, ``{monthly}`` в
    шаблон. Любой другой токен (неизвестный, с атрибутом/индексом вроде
    ``{brand.__class__}``, битый) возвращается как есть — ровно то же поведение, что
    у CRM для случая, когда шаблон не прошёл собственную валидацию."""
    if not template:
        return ""

    def _substitute(match: re.Match[str]) -> str:
        token = match.group(1)
        if token in _ALLOWED_TOKENS and token in values:
            return str(values[token])
        return match.group(0)

    return _TOKEN_RE.sub(_substitute, template)


def car_seo_values(car: dict[str, Any]) -> dict[str, object]:
    return {
        "brand": car["brand"],
        "model": car["model"],
        "year": car["year"],
        "price": car["price"],
        "monthly": car["monthly_payment"],
    }


def build_organization_jsonld(config: dict[str, Any]) -> dict[str, Any]:
    contacts = config["contacts"]
    data: dict[str, Any] = {
        "@type": "Organization",
        "name": contacts["legal_name"] or config["name"],
    }
    if contacts["phone"]:
        data["telephone"] = contacts["phone"]
    if contacts["email"]:
        data["email"] = contacts["email"]
    if contacts["address"]:
        data["address"] = {"@type": "PostalAddress", "streetAddress": contacts["address"]}
    if contacts["same_as"]:
        data["sameAs"] = contacts["same_as"]
    return data


def build_landing_jsonld(request: HttpRequest, config: dict[str, Any]) -> str:
    graph: list[dict[str, Any]] = [build_organization_jsonld(config)]
    faq = config.get("faq") or []
    if faq:
        graph.append(
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": item["question"],
                        "acceptedAnswer": {"@type": "Answer", "text": item["answer"]},
                    }
                    for item in faq
                ],
            },
        )
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)


def build_car_jsonld(request: HttpRequest, config: dict[str, Any], car: dict[str, Any], car_url: str) -> str:
    # car["url"] из CRM намеренно не используется — он указывает на CRM, не на эту
    # витрину (см. отчёт по ветке feat/public-site-apis, находка M6); канонический
    # адрес карточки на этом сайте строит вызывающая вьюха через reverse(). Organization
    # включена и здесь: по спецификации SEO-слоя (Task 1) она обязана быть на каждой
    # странице, не только на лендинге — там же FAQPage и Product+Offer+BreadcrumbList
    # разведены по типам страниц ровно так, как задумано.
    organization = {"@context": "https://schema.org", **build_organization_jsonld(config)}
    product = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": f"{car['brand']} {car['model']} {car['year']}",
        "description": car.get("description") or "",
        "offers": {
            "@type": "Offer",
            "url": car_url,
            "price": car["price"],
            "priceCurrency": "RUB",
            "availability": "https://schema.org/InStock",
        },
    }
    if car.get("photo_url"):
        product["image"] = car["photo_url"]
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Главная", "item": request.build_absolute_uri("/")},
            {"@type": "ListItem", "position": 2, "name": f"{car['brand']} {car['model']}", "item": car_url},
        ],
    }
    return json.dumps([organization, product, breadcrumb], ensure_ascii=False)
