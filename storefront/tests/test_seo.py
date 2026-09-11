from __future__ import annotations

import json

from django.test import RequestFactory, SimpleTestCase

from storefront.seo import build_car_jsonld, build_landing_jsonld, render_seo_template

from .factories import SAMPLE_CAR, SAMPLE_CONFIG


class RenderSeoTemplateTests(SimpleTestCase):
    """Подстановка идёт через regex-замену пяти известных токенов, не через
    str.format — та же защита от инъекции формат-строкой, которую CRM применяет в
    SourceSite.clean() (allowlist плейсхолдеров), только здесь она нужна на этапе
    рендера, а не только валидации, потому что рендерит именно эта сторона."""

    def test_substitutes_all_known_tokens(self) -> None:
        result = render_seo_template(
            "{brand} {model} {year} — {price} ₽, от {monthly} ₽/мес",
            brand="Kia",
            model="Rio",
            year=2021,
            price="1500000",
            monthly="25000",
        )
        assert result == "Kia Rio 2021 — 1500000 ₽, от 25000 ₽/мес"

    def test_unknown_token_is_left_literal(self) -> None:
        assert render_seo_template("{brand} {mystery}", brand="Kia") == "Kia {mystery}"

    def test_attribute_access_token_is_not_evaluated(self) -> None:
        # Ровно тот примитив раскрытия данных через str.format, которого здесь нет:
        # токен с точкой не входит в allowlist и возвращается как есть, а не
        # обходит атрибуты переданного значения.
        result = render_seo_template("{brand.__class__}", brand="Kia")
        assert result == "{brand.__class__}"

    def test_empty_template_returns_empty_string(self) -> None:
        assert render_seo_template("", brand="Kia") == ""


class BuildLandingJsonldTests(SimpleTestCase):
    def test_includes_organization_and_faq(self) -> None:
        request = RequestFactory().get("/")
        graph = json.loads(build_landing_jsonld(request, SAMPLE_CONFIG))["@graph"]
        types = [item["@type"] for item in graph]
        assert "Organization" in types
        assert "FAQPage" in types

    def test_omits_faq_page_when_no_faq_items(self) -> None:
        request = RequestFactory().get("/")
        config_without_faq = {**SAMPLE_CONFIG, "faq": []}
        graph = json.loads(build_landing_jsonld(request, config_without_faq))["@graph"]
        types = [item["@type"] for item in graph]
        assert "FAQPage" not in types


class BuildCarJsonldTests(SimpleTestCase):
    def test_includes_organization_product_and_breadcrumb(self) -> None:
        request = RequestFactory().get("/cars/kia-rio-2021/")
        car_url = "http://testserver/cars/kia-rio-2021/"
        items = json.loads(build_car_jsonld(request, SAMPLE_CONFIG, SAMPLE_CAR, car_url))
        types = [item["@type"] for item in items]
        assert types == ["Organization", "Product", "BreadcrumbList"]

    def test_product_offer_uses_this_sites_url_not_crms(self) -> None:
        request = RequestFactory().get("/cars/kia-rio-2021/")
        car_url = "http://testserver/cars/kia-rio-2021/"
        items = json.loads(build_car_jsonld(request, SAMPLE_CONFIG, SAMPLE_CAR, car_url))
        product = next(item for item in items if item["@type"] == "Product")
        assert product["offers"]["url"] == car_url
        assert product["offers"]["url"] != SAMPLE_CAR["url"]
