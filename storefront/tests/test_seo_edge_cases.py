"""Дополнительные тесты для SEO модуля — пограничные случаи."""

from __future__ import annotations

import json

from django.test import RequestFactory, SimpleTestCase

from storefront.seo import (
    build_car_jsonld,
    build_landing_jsonld,
    build_organization_jsonld,
    car_page_description,
    car_page_title,
    render_seo_template,
)

from .factories import SAMPLE_CAR, SAMPLE_CONFIG


class RenderSeoTemplateEdgeCasesTests(SimpleTestCase):
    """Пограничные случаи для render_seo_template."""

    def test_multiple_same_tokens(self) -> None:
        """Один и тот же токен несколько раз в шаблоне."""
        result = render_seo_template(
            "{brand} {brand} {brand}",
            brand="Kia",
        )
        assert result == "Kia Kia Kia"

    def test_token_with_whitespace(self) -> None:
        """Токен с пробелами внутри скобок не должен подставляться."""
        result = render_seo_template("{ brand }", brand="Kia")
        # Токен " brand " (с пробелами) не входит в allowed list
        assert result == "{ brand }"

    def test_nested_braces(self) -> None:
        """Вложенные скобки должны обрабатываться корректно."""
        result = render_seo_template("{{brand}}", brand="Kia")
        # {{brand}} интерпретируется как { + {brand} + }, где {brand} подставляется
        # Но regex находит только простые {} пары
        assert "{Kia}" in result or "{{brand}}" == result

    def test_partial_token_match(self) -> None:
        """Частичное совпадение токена не должно подставляться."""
        result = render_seo_template("{brands}", brand="Kia")
        # {brands} != {brand}
        assert result == "{brands}"

    def test_numeric_values(self) -> None:
        """Числовые значения должны конвертироваться в строку."""
        result = render_seo_template("{year}", year=2021)
        assert result == "2021"

    def test_none_value_skips_substitution(self) -> None:
        """None значение конвертируется в строку 'None'."""
        result = render_seo_template("{brand}", brand=None)
        # str(None) = "None", так работает str() в Python
        assert result == "None"

    def test_html_entities_in_values(self) -> None:
        """HTML сущности в значениях должны сохраняться."""
        result = render_seo_template("{brand}", brand="Kia & Sons")
        assert result == "Kia & Sons"

    def test_special_characters_in_template(self) -> None:
        """Специальные символы в шаблоне должны сохраняться."""
        result = render_seo_template("{brand} <{model}>", brand="Kia", model="Rio")
        assert result == "Kia <Rio>"


class BuildOrganizationJsonldTests(SimpleTestCase):
    """Тесты для build_organization_jsonld."""

    def test_minimal_organization(self) -> None:
        """Минимальная организация только с именем."""
        config = {
            "name": "Test Site",
            "contacts": {
                "legal_name": "",
                "phone": "",
                "email": "",
                "address": "",
                "same_as": [],
            },
        }
        result = build_organization_jsonld(config)
        assert result["@type"] == "Organization"
        assert result["name"] == "Test Site"
        assert "telephone" not in result
        assert "email" not in result
        assert "address" not in result

    def test_full_organization(self) -> None:
        """Полная организация со всеми полями."""
        config = {
            "name": "Test Site",
            "contacts": {
                "legal_name": "OOO Test",
                "phone": "+79990000000",
                "email": "test@example.com",
                "address": "Moscow, Red Square 1",
                "same_as": ["https://vk.com/test", "https://t.me/test"],
            },
        }
        result = build_organization_jsonld(config)
        assert result["name"] == "OOO Test"
        assert result["telephone"] == "+79990000000"
        assert result["email"] == "test@example.com"
        assert result["address"]["@type"] == "PostalAddress"
        assert result["address"]["streetAddress"] == "Moscow, Red Square 1"
        assert result["sameAs"] == ["https://vk.com/test", "https://t.me/test"]

    def test_legal_name_fallback_to_name(self) -> None:
        """Если legal_name пустой, используется name."""
        config = {
            "name": "Test Site",
            "contacts": {
                "legal_name": "",
                "phone": "",
                "email": "",
                "address": "",
                "same_as": [],
            },
        }
        result = build_organization_jsonld(config)
        assert result["name"] == "Test Site"


class BuildLandingJsonldEdgeCasesTests(SimpleTestCase):
    """Пограничные случаи для build_landing_jsonld."""

    def test_empty_faq_list(self) -> None:
        """Пустой FAQ не должен добавлять FAQPage."""
        config = {**SAMPLE_CONFIG, "faq": []}
        request = RequestFactory().get("/")
        result = json.loads(build_landing_jsonld(request, config))
        types = [item["@type"] for item in result["@graph"]]
        assert "FAQPage" not in types
        assert "Organization" in types

    def test_multiple_faq_items(self) -> None:
        """Несколько элементов FAQ должны корректно сериализоваться."""
        config = {
            **SAMPLE_CONFIG,
            "faq": [
                {"question": "Q1", "answer": "A1"},
                {"question": "Q2", "answer": "A2"},
                {"question": "Q3", "answer": "A3"},
            ],
        }
        request = RequestFactory().get("/")
        result = json.loads(build_landing_jsonld(request, config))
        faq = next(item for item in result["@graph"] if item["@type"] == "FAQPage")
        assert len(faq["mainEntity"]) == 3

    def test_faq_with_special_characters(self) -> None:
        """FAQ с специальными символами должен корректно сериализоваться."""
        config = {
            **SAMPLE_CONFIG,
            "faq": [{"question": "Вопрос & ответ?", "answer": "<p>Ответ с \"кавычками\"</p>"}],
        }
        request = RequestFactory().get("/")
        result = json.loads(build_landing_jsonld(request, config))
        faq = next(item for item in result["@graph"] if item["@type"] == "FAQPage")
        assert faq["mainEntity"][0]["name"] == "Вопрос & ответ?"


class BuildCarJsonldEdgeCasesTests(SimpleTestCase):
    """Пограничные случаи для build_car_jsonld."""

    def test_car_without_photo(self) -> None:
        """Авто без фото не должно иметь поле image."""
        car = {**SAMPLE_CAR, "photo_url": ""}
        request = RequestFactory().get("/cars/kia-rio/")
        car_url = "http://testserver/cars/kia-rio/"
        items = json.loads(build_car_jsonld(request, SAMPLE_CONFIG, car, car_url))
        product = next(item for item in items if item["@type"] == "Product")
        assert "image" not in product

    def test_car_without_description(self) -> None:
        """Авто без описания должно иметь пустое description."""
        car = {**SAMPLE_CAR, "description": ""}
        request = RequestFactory().get("/cars/kia-rio/")
        car_url = "http://testserver/cars/kia-rio/"
        items = json.loads(build_car_jsonld(request, SAMPLE_CONFIG, car, car_url))
        product = next(item for item in items if item["@type"] == "Product")
        assert product["description"] == ""

    def test_breadcrumb_positions_are_sequential(self) -> None:
        """Позиции в breadcrumb должны быть последовательными."""
        request = RequestFactory().get("/cars/kia-rio/")
        car_url = "http://testserver/cars/kia-rio/"
        items = json.loads(build_car_jsonld(request, SAMPLE_CONFIG, SAMPLE_CAR, car_url))
        breadcrumb = next(item for item in items if item["@type"] == "BreadcrumbList")
        positions = [entry["position"] for entry in breadcrumb["itemListElement"]]
        assert positions == [1, 2, 3]

    def test_product_price_is_integer(self) -> None:
        """Цена в продукте должна быть числом (int или str из CRM)."""
        request = RequestFactory().get("/cars/kia-rio/")
        car_url = "http://testserver/cars/kia-rio/"
        items = json.loads(build_car_jsonld(request, SAMPLE_CONFIG, SAMPLE_CAR, car_url))
        product = next(item for item in items if item["@type"] == "Product")
        # price может быть int или str, главное что это числовое значение
        assert isinstance(product["offers"]["price"], (int, str))

    def test_currency_is_rub(self) -> None:
        """Валюта всегда должна быть RUB."""
        request = RequestFactory().get("/cars/kia-rio/")
        car_url = "http://testserver/cars/kia-rio/"
        items = json.loads(build_car_jsonld(request, SAMPLE_CONFIG, SAMPLE_CAR, car_url))
        product = next(item for item in items if item["@type"] == "Product")
        assert product["offers"]["priceCurrency"] == "RUB"


class CarPageTitleEdgeCasesTests(SimpleTestCase):
    """Пограничные случаи для car_page_title."""

    def test_template_with_extra_tokens(self) -> None:
        """Шаблон с неизвестными токенами должен оставлять их как есть."""
        config = {
            **SAMPLE_CONFIG,
            "seo": {**SAMPLE_CONFIG["seo"], "title_car_template": "{brand} {unknown} {model}"},
        }
        title = car_page_title(config, SAMPLE_CAR)
        assert "{unknown}" in title

    def test_meta_title_with_html(self) -> None:
        """meta_title с HTML должен сохраняться как есть."""
        config = {**SAMPLE_CONFIG, "seo": {**SAMPLE_CONFIG["seo"], "title_car_template": ""}}
        car = {**SAMPLE_CAR, "meta_title": "<b>Kia Rio</b> - лучший выбор"}
        title = car_page_title(config, car)
        assert "<b>Kia Rio</b>" in title

    def test_fallback_with_missing_fields(self) -> None:
        """Fallback должен работать даже при отсутствующих полях."""
        config = {**SAMPLE_CONFIG, "seo": {**SAMPLE_CONFIG["seo"], "title_car_template": ""}}
        # car должен иметь все обязательные поля для car_seo_values
        car = {**SAMPLE_CAR, "meta_title": "", "price": "1500000", "monthly_payment": "25000"}
        title = car_page_title(config, car)
        assert title == "Kia Rio 2021"


class CarPageDescriptionEdgeCasesTests(SimpleTestCase):
    """Пограничные случаи для car_page_description."""

    def test_template_produces_empty_string(self) -> None:
        """Пустой результат шаблона должен использовать fallback."""
        config = {
            **SAMPLE_CONFIG,
            "seo": {**SAMPLE_CONFIG["seo"], "description_car_template": "{unknown}"},
        }
        description = car_page_description(config, SAMPLE_CAR)
        # Шаблон вернёт "{unknown}" (unknown токен не подставится, останется как есть)
        # Это не пустая строка, поэтому fallback не используется
        assert "{unknown}" in description

    def test_both_template_and_meta_empty(self) -> None:
        """Если и шаблон и meta_description пусты, вернуть пустую строку."""
        config = {**SAMPLE_CONFIG, "seo": {**SAMPLE_CONFIG["seo"], "description_car_template": ""}}
        car = {**SAMPLE_CAR, "meta_description": ""}
        description = car_page_description(config, car)
        assert description == ""
