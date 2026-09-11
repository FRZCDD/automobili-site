"""Тесты для views: robots.txt и sitemap.xml."""

from __future__ import annotations

from http import HTTPStatus
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from storefront import crm_client

from .factories import SAMPLE_CAR, SAMPLE_CONFIG


class RobotsTxtTests(SimpleTestCase):
    """Тесты страницы robots.txt."""

    def test_returns_200(self) -> None:
        response = self.client.get("/robots.txt")
        assert response.status_code == HTTPStatus.OK

    def test_content_type_is_text_plain(self) -> None:
        response = self.client.get("/robots.txt")
        assert response["Content-Type"] == "text/plain"

    def test_contains_sitemap_url(self) -> None:
        response = self.client.get("/robots.txt")
        assert "Sitemap: http://testserver/sitemap.xml" in response.content.decode()

    def test_contains_user_agent_directive(self) -> None:
        response = self.client.get("/robots.txt")
        assert "User-agent" in response.content.decode()


class SitemapXmlTests(SimpleTestCase):
    """Тесты страницы sitemap.xml."""

    def test_returns_200(self) -> None:
        response = self.client.get("/sitemap.xml")
        assert response.status_code == HTTPStatus.OK

    def test_content_type_is_application_xml(self) -> None:
        response = self.client.get("/sitemap.xml")
        assert response["Content-Type"] == "application/xml"

    def test_contains_landing_url(self) -> None:
        response = self.client.get("/sitemap.xml")
        content = response.content.decode()
        assert "<loc>http://testserver/</loc>" in content

    @patch.object(crm_client, "get_cars", return_value=[SAMPLE_CAR])
    @patch.object(crm_client, "get_site_config", return_value=SAMPLE_CONFIG)
    def test_contains_car_urls_when_cars_available(
        self, mock_get_config: patch, mock_get_cars: patch
    ) -> None:
        response = self.client.get("/sitemap.xml")
        content = response.content.decode()
        assert "<loc>http://testserver/cars/kia-rio-2021/</loc>" in content

    @patch.object(crm_client, "get_cars", side_effect=crm_client.CrmUnavailableError)
    def test_returns_landing_only_when_crm_unavailable(
        self, mock_get_cars: patch
    ) -> None:
        """CRM недоступна — sitemap не должен падать 500, отдаём хотя бы лендинг."""
        response = self.client.get("/sitemap.xml")
        assert response.status_code == HTTPStatus.OK
        content = response.content.decode()
        assert "<loc>http://testserver/</loc>" in content
        assert "kia-rio" not in content

    @patch.object(crm_client, "get_cars", side_effect=crm_client.CrmClientError(500, "boom"))
    def test_returns_landing_only_when_crm_returns_error(
        self, mock_get_cars: patch
    ) -> None:
        """CRM вернула ошибку — sitemap не должен падать 500."""
        response = self.client.get("/sitemap.xml")
        assert response.status_code == HTTPStatus.OK
        content = response.content.decode()
        assert "<loc>http://testserver/</loc>" in content
        assert "kia-rio" not in content

    @patch.object(crm_client, "get_cars", return_value=[])
    def test_empty_cars_list_returns_landing_only(
        self, mock_get_cars: patch
    ) -> None:
        """Список авто пуст — sitemap содержит только лендинг."""
        response = self.client.get("/sitemap.xml")
        content = response.content.decode()
        assert "<loc>http://testserver/</loc>" in content
        # Убедимся, что нет других loc кроме лендинга
        locs = [line.strip() for line in content.split("\n") if "<loc>" in line]
        assert len(locs) == 1

    @patch.object(crm_client, "get_cars", return_value=[SAMPLE_CAR])
    @patch.object(crm_client, "get_site_config", return_value=SAMPLE_CONFIG)
    def test_sitemap_is_valid_xml(
        self, mock_get_config: patch, mock_get_cars: patch
    ) -> None:
        """Проверка что sitemap — валидный XML с правильной структурой."""
        response = self.client.get("/sitemap.xml")
        content = response.content.decode()
        assert '<?xml version="1.0"' in content
        assert "<urlset" in content
        assert "</urlset>" in content
        assert content.strip().endswith("</urlset>")
