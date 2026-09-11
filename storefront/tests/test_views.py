from __future__ import annotations

from http import HTTPStatus
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase
from django.urls import reverse

from storefront import crm_client

from .factories import SAMPLE_CAR, SAMPLE_CONFIG


class LandingViewTests(SimpleTestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_renders_landing_with_hero_and_car(self) -> None:
        with (
            patch.object(crm_client, "get_site_config", return_value=SAMPLE_CONFIG),
            patch.object(crm_client, "get_cars", return_value=[SAMPLE_CAR]),
        ):
            response = self.client.get(reverse("storefront:landing"))
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, SAMPLE_CONFIG["branding"]["hero_title"])
        self.assertContains(response, "Kia")
        self.assertContains(response, "Rio")

    def test_crm_unreachable_renders_unavailable_page(self) -> None:
        with (
            patch.object(crm_client, "get_site_config", side_effect=crm_client.CrmUnavailableError),
            patch.object(crm_client, "get_cars", return_value=[]),
        ):
            response = self.client.get(reverse("storefront:landing"))
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE

    def test_unknown_site_slug_renders_unavailable_page(self) -> None:
        # get_site_config() возвращает None, когда для SITE_SLUG нет SourceSite в
        # CRM — это ошибка деплоя (не туда указывает переменная окружения), не то,
        # что нормально увидит посетитель, поэтому тоже страница-заглушка, не 404.
        with (
            patch.object(crm_client, "get_site_config", return_value=None),
            patch.object(crm_client, "get_cars", return_value=[]),
        ):
            response = self.client.get(reverse("storefront:landing"))
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE

    def test_organization_and_faq_jsonld_present(self) -> None:
        with (
            patch.object(crm_client, "get_site_config", return_value=SAMPLE_CONFIG),
            patch.object(crm_client, "get_cars", return_value=[SAMPLE_CAR]),
        ):
            response = self.client.get(reverse("storefront:landing"))
        self.assertContains(response, '"@type": "Organization"')
        self.assertContains(response, '"@type": "FAQPage"')


class CarDetailViewTests(SimpleTestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_renders_car_detail_with_templated_seo_title(self) -> None:
        with (
            patch.object(crm_client, "get_site_config", return_value=SAMPLE_CONFIG),
            patch.object(crm_client, "get_car", return_value=SAMPLE_CAR),
            patch.object(crm_client, "get_cars", return_value=[SAMPLE_CAR]),
        ):
            response = self.client.get(reverse("storefront:car_detail", args=["kia-rio-2021"]))
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "<h1")
        self.assertContains(response, "Kia Rio 2021")
        # Заголовок собран из seo.title_car_template конфига с реальными данными
        # авто, не взят как есть (шаблон содержит {brand} {model} {year}).
        self.assertContains(response, "<title>Kia Rio 2021 в кредит от 4,9% — купить | AUTOCREDIT</title>")

    def test_unknown_car_slug_returns_404(self) -> None:
        with (
            patch.object(crm_client, "get_site_config", return_value=SAMPLE_CONFIG),
            patch.object(crm_client, "get_car", return_value=None),
            patch.object(crm_client, "get_cars", return_value=[]),
        ):
            response = self.client.get(reverse("storefront:car_detail", args=["ghost"]))
        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_crm_unreachable_renders_unavailable_page(self) -> None:
        with (
            patch.object(crm_client, "get_site_config", return_value=SAMPLE_CONFIG),
            patch.object(crm_client, "get_car", side_effect=crm_client.CrmUnavailableError),
            patch.object(crm_client, "get_cars", return_value=[SAMPLE_CAR]),
        ):
            response = self.client.get(reverse("storefront:car_detail", args=["kia-rio-2021"]))
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE

    def test_does_not_link_to_crms_own_car_url(self) -> None:
        # SAMPLE_CAR["url"] пойнтит на CRM (http://crm.invalid/cars/...) — вьюха не
        # должна протащить его в разметку страницы; canonical и breadcrumb обязаны
        # указывать на этот сайт, не на CRM (см. отчёт по ветке feat/public-site-apis,
        # находка M6, которую эта вёрстка обходит на своей стороне).
        with (
            patch.object(crm_client, "get_site_config", return_value=SAMPLE_CONFIG),
            patch.object(crm_client, "get_car", return_value=SAMPLE_CAR),
            patch.object(crm_client, "get_cars", return_value=[SAMPLE_CAR]),
        ):
            response = self.client.get(reverse("storefront:car_detail", args=["kia-rio-2021"]))
        self.assertNotContains(response, SAMPLE_CAR["url"])
