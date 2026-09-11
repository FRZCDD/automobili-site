"""storefront.crm_client — единственная точка интеграции с CRM. Настоящий httpx-клиент
подменяется на MockTransport: ни один тест не должен требовать поднятой CRM."""

from __future__ import annotations

import json
from collections.abc import Callable
from http import HTTPStatus
from unittest.mock import patch

import httpx
import pytest
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from storefront import crm_client


def _client_factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], httpx.Client]:
    def factory() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://crm.invalid")

    return factory


@override_settings(SITE_SLUG="autocredit", SITE_CONFIG_CACHE_TTL_SECONDS=60)
class GetSiteConfigTests(SimpleTestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_returns_parsed_config_on_200(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/sites/autocredit/config/"
            return httpx.Response(HTTPStatus.OK, json={"slug": "autocredit", "name": "AUTOCREDIT"})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            config = crm_client.get_site_config()
        assert config is not None
        assert config["slug"] == "autocredit"

    def test_returns_none_on_404(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(HTTPStatus.NOT_FOUND, json={"detail": "not found"})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            assert crm_client.get_site_config() is None

    def test_result_is_cached_across_calls(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(HTTPStatus.OK, json={"slug": "autocredit"})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            crm_client.get_site_config()
            crm_client.get_site_config()
        assert call_count == 1

    def test_connection_error_raises_unavailable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        with (
            patch.object(crm_client, "_client", _client_factory(handler)),
            pytest.raises(crm_client.CrmUnavailableError),
        ):
            crm_client.get_site_config()

    def test_server_error_raises_client_error_with_detail(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(HTTPStatus.INTERNAL_SERVER_ERROR, json={"detail": "boom"})

        with (
            patch.object(crm_client, "_client", _client_factory(handler)),
            pytest.raises(crm_client.CrmClientError) as ctx,
        ):
            crm_client.get_site_config()
        assert ctx.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert ctx.value.detail == "boom"


@override_settings(SITE_SLUG="autocredit", SITE_CONFIG_CACHE_TTL_SECONDS=60)
class GetCarsTests(SimpleTestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_extracts_cars_list_from_payload(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(HTTPStatus.OK, json={"site": "autocredit", "count": 1, "cars": [{"slug": "kia-rio"}]})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            cars = crm_client.get_cars()
        assert cars == [{"slug": "kia-rio"}]

    def test_unknown_site_returns_empty_list(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(HTTPStatus.NOT_FOUND, json={"detail": "not found"})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            assert crm_client.get_cars() == []


@override_settings(SITE_SLUG="autocredit")
class GetCarTests(SimpleTestCase):
    def test_returns_car_payload(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/sites/autocredit/cars/kia-rio-2021/"
            return httpx.Response(HTTPStatus.OK, json={"slug": "kia-rio-2021"})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            car = crm_client.get_car("kia-rio-2021")
        assert car is not None
        assert car["slug"] == "kia-rio-2021"

    def test_returns_none_when_car_missing(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(HTTPStatus.NOT_FOUND, json={"detail": "not found"})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            assert crm_client.get_car("ghost") is None

    def test_not_cached_between_calls(self) -> None:
        # Деталь авто не кэшируется локально (см. crm_client.get_car) — каждый вызов
        # обязан дойти до транспорта, иначе это регрессия к устаревшим данным.
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(HTTPStatus.OK, json={"slug": "kia-rio-2021"})

        with patch.object(crm_client, "_client", _client_factory(handler)):
            crm_client.get_car("kia-rio-2021")
            crm_client.get_car("kia-rio-2021")
        assert call_count == 2  # noqa: PLR2004


@override_settings(SITE_SLUG="autocredit")
class SubmitLeadTests(SimpleTestCase):
    def test_success_returns_lead_id_and_message(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/leads/create/"
            sent = json.loads(request.content)
            assert sent["site"] == "autocredit"
            assert sent["name"] == "Иван"
            return httpx.Response(
                HTTPStatus.CREATED,
                json={"status": "success", "message": "Заявка принята", "lead_id": 42, "region_iso": "RU-MOW"},
            )

        with patch.object(crm_client, "_client", _client_factory(handler)):
            result = crm_client.submit_lead(name="Иван", phone="+79990000000")
        assert result.lead_id == 42  # noqa: PLR2004
        assert result.message == "Заявка принята"

    def test_rate_limited_raises_client_error_with_status(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(HTTPStatus.TOO_MANY_REQUESTS, json={"detail": "Слишком много заявок"})

        with (
            patch.object(crm_client, "_client", _client_factory(handler)),
            pytest.raises(crm_client.CrmClientError) as ctx,
        ):
            crm_client.submit_lead(name="Иван", phone="+79990000000")
        assert ctx.value.status_code == HTTPStatus.TOO_MANY_REQUESTS

    def test_timeout_raises_unavailable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out", request=request)

        with (
            patch.object(crm_client, "_client", _client_factory(handler)),
            pytest.raises(crm_client.CrmUnavailableError),
        ):
                crm_client.submit_lead(name="Иван", phone="+79990000000")


class ErrorDetailTests(SimpleTestCase):
    def test_prefers_detail_field(self) -> None:
        response = httpx.Response(HTTPStatus.BAD_REQUEST, json={"detail": "плохой запрос", "title": "Bad Request"})
        assert crm_client._error_detail(response) == "плохой запрос"  # noqa: SLF001

    def test_falls_back_to_title(self) -> None:
        response = httpx.Response(HTTPStatus.BAD_REQUEST, json={"title": "Bad Request"})
        assert crm_client._error_detail(response) == "Bad Request"  # noqa: SLF001

    def test_falls_back_to_raw_text_on_non_json_body(self) -> None:
        response = httpx.Response(HTTPStatus.BAD_GATEWAY, text="<html>502</html>")
        assert crm_client._error_detail(response) == "<html>502</html>"  # noqa: SLF001
