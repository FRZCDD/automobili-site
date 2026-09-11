from __future__ import annotations

from http import HTTPStatus
from unittest.mock import patch

from django.test import Client, SimpleTestCase
from django.urls import reverse

from storefront import crm_client


class LeadSubmitViewTests(SimpleTestCase):
    def setUp(self) -> None:
        self.url = reverse("storefront:lead_submit")

    def test_missing_name_returns_400_without_calling_crm(self) -> None:
        with patch.object(crm_client, "submit_lead") as mock_submit:
            response = self.client.post(self.url, {"phone": "+79990000000"})
        assert response.status_code == HTTPStatus.BAD_REQUEST
        mock_submit.assert_not_called()

    def test_missing_phone_returns_400(self) -> None:
        response = self.client.post(self.url, {"name": "Иван"})
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_successful_submit_forwards_fields_and_site_from_settings(self) -> None:
        result = crm_client.LeadSubmitResult(lead_id=42, message="Заявка принята")
        with patch.object(crm_client, "submit_lead", return_value=result) as mock_submit:
            response = self.client.post(
                self.url,
                {"name": "Иван", "phone": "+79990000000", "car_name": "Kia Rio 2021", "utm_source": "yandex"},
            )
        assert response.status_code == HTTPStatus.CREATED
        assert response.json() == {"status": "success", "message": "Заявка принята", "lead_id": 42}
        mock_submit.assert_called_once_with(
            name="Иван",
            phone="+79990000000",
            car_name="Kia Rio 2021",
            utm_source="yandex",
            utm_medium="",
            utm_campaign="",
        )

    def test_crm_unreachable_returns_503_with_friendly_message(self) -> None:
        with patch.object(crm_client, "submit_lead", side_effect=crm_client.CrmUnavailableError):
            response = self.client.post(self.url, {"name": "Иван", "phone": "+79990000000"})
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert response.json()["status"] == "error"

    def test_crm_rate_limit_passes_through_as_429(self) -> None:
        error = crm_client.CrmClientError(HTTPStatus.TOO_MANY_REQUESTS, "rate limited")
        with patch.object(crm_client, "submit_lead", side_effect=error):
            response = self.client.post(self.url, {"name": "Иван", "phone": "+79990000000"})
        assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS

    def test_crm_validation_error_passes_through_as_400(self) -> None:
        error = crm_client.CrmClientError(HTTPStatus.BAD_REQUEST, "invalid phone")
        with patch.object(crm_client, "submit_lead", side_effect=error):
            response = self.client.post(self.url, {"name": "Иван", "phone": "+79990000000"})
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_crm_server_error_becomes_502_not_leaked_as_is(self) -> None:
        # 500 у CRM не должен превращаться в 500 у сайта — это ответ апстрима, не
        # ошибка этого сайта; 502 Bad Gateway точнее описывает произошедшее.
        error = crm_client.CrmClientError(HTTPStatus.INTERNAL_SERVER_ERROR, "boom")
        with patch.object(crm_client, "submit_lead", side_effect=error):
            response = self.client.post(self.url, {"name": "Иван", "phone": "+79990000000"})
        assert response.status_code == HTTPStatus.BAD_GATEWAY

    def test_csrf_is_enforced(self) -> None:
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(self.url, {"name": "Иван", "phone": "+79990000000"})
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_get_not_allowed(self) -> None:
        response = self.client.get(self.url)
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
