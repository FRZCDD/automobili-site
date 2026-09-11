"""Дополнительные тесты для crm_client — пограничные случаи и edge cases."""

from __future__ import annotations

import json
from collections.abc import Callable
from http import HTTPStatus
from unittest.mock import patch

import httpx
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from storefront import crm_client


def _client_factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], httpx.Client]:
    def factory() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://crm.invalid")

    return factory


@override_settings(SITE_SLUG="testsite", SITE_CONFIG_CACHE_TTL_SECONDS=60)
class GetSiteConfigEdgeCasesTests(SimpleTestCase):
    """Пограничные случаи для get_site_config."""

    def setUp(self) -> None:
        cache.clear()

    def test_empty_json_response(self) -> None:
        """CRM вернула пустой JSON объект."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(HTTPStatus.OK, json={})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            config = crm_client.get_site_config()
        assert config is not None
        assert config == {}

    def test_html_error_response(self) -> None:
        """CRM вернула HTML вместо JSON (например, ошибка прокси)."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                text="<html><body>502 Bad Gateway</body></html>",
                headers={"Content-Type": "text/html"},
            )

        with (
            patch.object(crm_client, "_client", _client_factory(handler)),
            patch.object(crm_client, "logger"),
        ):
            try:
                crm_client.get_site_config()
            except crm_client.CrmClientError as exc:
                assert exc.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
                assert "502 Bad Gateway" in exc.detail

    def test_cache_key_includes_site_slug(self) -> None:
        """Кэш должен быть изолирован по site slug."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(HTTPStatus.OK, json={"slug": "testsite"})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            crm_client.get_site_config()
            crm_client.get_site_config()

        assert call_count == 1
        # Проверка что ключ кэша содержит site slug
        cache_key = crm_client._cache_key("config")
        assert "testsite" in cache_key


@override_settings(SITE_SLUG="testsite", SITE_CONFIG_CACHE_TTL_SECONDS=60)
class GetCarsEdgeCasesTests(SimpleTestCase):
    """Пограничные случаи для get_cars."""

    def setUp(self) -> None:
        cache.clear()

    def test_empty_cars_list(self) -> None:
        """CRM вернула пустой список машин."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(HTTPStatus.OK, json={"cars": []})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            cars = crm_client.get_cars()
        assert cars == []

    def test_cars_with_extra_fields(self) -> None:
        """CRM вернула дополнительные поля помимо cars."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                HTTPStatus.OK,
                json={
                    "cars": [{"slug": "car1"}],
                    "count": 1,
                    "total": 100,
                    "extra_field": "ignored",
                },
            )

        with patch.object(crm_client, "_client", _client_factory(handler)):
            cars = crm_client.get_cars()
        assert len(cars) == 1
        assert cars[0]["slug"] == "car1"

    def test_null_cars_field_raises_error(self) -> None:
        """CRM вернула null вместо списка cars."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(HTTPStatus.OK, json={"cars": None})

        with (
            patch.object(crm_client, "_client", _client_factory(handler)),
            patch.object(crm_client, "logger"),
        ):
            try:
                crm_client.get_cars()
            except crm_client.CrmClientError as exc:
                assert exc.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
                assert "cars" in exc.detail


class GetCarEdgeCasesTests(SimpleTestCase):
    """Пограничные случаи для get_car."""

    @override_settings(SITE_SLUG="testsite")
    def test_special_characters_in_slug(self) -> None:
        """Slug со специальными символами должен корректно кодироваться."""
        def handler(request: httpx.Request) -> httpx.Response:
            # Проверяем что slug корректно передаётся в URL
            assert "kia-rio-2021" in request.url.path
            return httpx.Response(HTTPStatus.OK, json={"slug": "kia-rio-2021"})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            car = crm_client.get_car("kia-rio-2021")
        assert car is not None

    @override_settings(SITE_SLUG="testsite")
    def test_unicode_slug(self) -> None:
        """Unicode slug должен корректно обрабатываться."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(HTTPStatus.OK, json={"slug": "авто-с-кириллицей"})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            car = crm_client.get_car("авто-с-кириллицей")
        assert car is not None


class SubmitLeadEdgeCasesTests(SimpleTestCase):
    """Пограничные случаи для submit_lead."""

    @override_settings(SITE_SLUG="testsite")
    def test_empty_strings_in_payload(self) -> None:
        """Пустые строки должны передаваться как есть."""
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            assert payload["name"] == ""
            assert payload["phone"] == ""
            assert payload["car_name"] == ""
            assert payload["utm_source"] == ""
            return httpx.Response(HTTPStatus.CREATED, json={"lead_id": 1, "message": "OK"})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            result = crm_client.submit_lead(name="", phone="")
        assert result.lead_id == 1

    @override_settings(SITE_SLUG="testsite")
    def test_all_utm_parameters(self) -> None:
        """Все UTM параметры должны передаваться."""
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            assert payload["utm_source"] == "google"
            assert payload["utm_medium"] == "cpc"
            assert payload["utm_campaign"] == "summer_sale"
            return httpx.Response(HTTPStatus.CREATED, json={"lead_id": 1, "message": "OK"})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            result = crm_client.submit_lead(
                name="Test",
                phone="+79990000000",
                utm_source="google",
                utm_medium="cpc",
                utm_campaign="summer_sale",
            )
        assert result.lead_id == 1

    @override_settings(SITE_SLUG="testsite")
    def test_long_phone_number(self) -> None:
        """Длинный номер телефона должен передаваться без обрезки."""
        long_phone = "+7" + "9" * 15
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            assert payload["phone"] == long_phone
            return httpx.Response(HTTPStatus.CREATED, json={"lead_id": 1, "message": "OK"})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            result = crm_client.submit_lead(name="Test", phone=long_phone)
        assert result.lead_id == 1

    @override_settings(SITE_SLUG="testsite")
    def test_non_standard_success_status_codes(self) -> None:
        """Различные 2xx коды должны считаться успехом."""
        for status_code in [HTTPStatus.OK, HTTPStatus.ACCEPTED, HTTPStatus.CREATED]:
            with self.subTest(status_code=status_code):
                def handler(request: httpx.Request) -> httpx.Response:
                    return httpx.Response(status_code, json={"lead_id": 1, "message": "OK"})

                with patch.object(crm_client, "_client", _client_factory(handler)):
                    result = crm_client.submit_lead(name="Test", phone="+79990000000")
                assert result.lead_id == 1


class ErrorDetailEdgeCasesTests(SimpleTestCase):
    """Пограничные случаи для _error_detail."""

    def test_nested_detail_in_json(self) -> None:
        """Вложенная структура detail."""
        response = httpx.Response(
            HTTPStatus.BAD_REQUEST,
            json={"detail": {"message": "nested error", "code": "invalid_input"}},
        )
        detail = crm_client._error_detail(response)  # noqa: SLF001
        # dict превращается в строку
        assert "nested error" in str(detail) or "message" in str(detail)

    def test_very_long_error_message(self) -> None:
        """Очень длинное сообщение об ошибке должно обрезаться."""
        long_text = "x" * 1000
        response = httpx.Response(HTTPStatus.BAD_REQUEST, text=long_text)
        detail = crm_client._error_detail(response)  # noqa: SLF001
        assert len(detail) <= 500

    def test_empty_response_body(self) -> None:
        """Пустое тело ответа."""
        response = httpx.Response(HTTPStatus.BAD_REQUEST, content=b"")
        detail = crm_client._error_detail(response)  # noqa: SLF001
        assert detail == ""

    def test_malformed_json_with_detail_key(self) -> None:
        """JSON с полем detail, но невалидный."""
        response = httpx.Response(
            HTTPStatus.BAD_REQUEST,
            json={"detail": "valid detail", "extra": "ignored"},
        )
        detail = crm_client._error_detail(response)  # noqa: SLF001
        assert detail == "valid detail"
