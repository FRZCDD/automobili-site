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

    def test_loads_calculator_and_chart_js(self) -> None:
        # Калькулятор есть только на лендинге — Chart.js и calculator.js грузятся
        # через index.html's extra_scripts, не безусловно из base.html (иначе их
        # тянула бы и карточка авто, где калькулятора нет — см. CarDetailViewTests
        # .test_does_not_load_calculator_or_chart_js).
        with (
            patch.object(crm_client, "get_site_config", return_value=SAMPLE_CONFIG),
            patch.object(crm_client, "get_cars", return_value=[SAMPLE_CAR]),
        ):
            response = self.client.get(reverse("storefront:landing"))
        self.assertContains(response, "chart.umd.min.js")
        self.assertContains(response, "calculator.js")

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

    def test_canonical_and_og_url_exclude_query_string(self) -> None:
        # Этот же сайт сам ловит utm_source/utm_medium/utm_campaign
        # (static/js/site.js, в форме заявки есть скрытые поля с тем же именем —
        # поэтому здесь не blanket-проверка "utm_source нет на странице", а именно
        # содержимое canonical/og:url): рекламная ссылка на лендинг с UTM-метками
        # не должна породить формально другой canonical/og:url на себя же.
        with (
            patch.object(crm_client, "get_site_config", return_value=SAMPLE_CONFIG),
            patch.object(crm_client, "get_cars", return_value=[SAMPLE_CAR]),
        ):
            response = self.client.get(reverse("storefront:landing"), {"utm_source": "yandex"})
        self.assertContains(response, '<link rel="canonical" href="http://testserver/" />')
        self.assertContains(response, 'property="og:url" content="http://testserver/"')

    def test_bottom_text_legitimate_link_is_rendered(self) -> None:
        # SAMPLE_CONFIG["seo"]["bottom_text"] (storefront/tests/factories.py) — форма,
        # которую реально присылает CRM: ссылка должна остаться кликабельной после
        # санитизации, не просто "не сломаться".
        with (
            patch.object(crm_client, "get_site_config", return_value=SAMPLE_CONFIG),
            patch.object(crm_client, "get_cars", return_value=[SAMPLE_CAR]),
        ):
            response = self.client.get(reverse("storefront:landing"))
        self.assertContains(response, '<a href="/cars/kia-rio-2021/">Kia Rio</a>')

    def test_bottom_text_script_payload_is_sanitized(self) -> None:
        # {{ site.seo.bottom_text|safe }} в templates/index.html рендерит это поле
        # как есть — без санитизации в LandingView.get() это был бы обычный XSS.
        malicious_config = {
            **SAMPLE_CONFIG,
            "seo": {**SAMPLE_CONFIG["seo"], "bottom_text": "<p>Текст</p><script>alert(1)</script>"},
        }
        with (
            patch.object(crm_client, "get_site_config", return_value=malicious_config),
            patch.object(crm_client, "get_cars", return_value=[SAMPLE_CAR]),
        ):
            response = self.client.get(reverse("storefront:landing"))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "Текст")


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

    def test_unknown_site_slug_skips_car_lookup_entirely(self) -> None:
        # get_site_config() первой и отдельно: если сайта нет в CRM, это не должно
        # тратить ещё два запроса (get_car, get_cars) на страницу, которая всё
        # равно окажется заглушкой недоступности.
        with (
            patch.object(crm_client, "get_site_config", return_value=None),
            patch.object(crm_client, "get_car") as mock_get_car,
            patch.object(crm_client, "get_cars") as mock_get_cars,
        ):
            response = self.client.get(reverse("storefront:car_detail", args=["kia-rio-2021"]))
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        mock_get_car.assert_not_called()
        mock_get_cars.assert_not_called()

    def test_og_tags_are_car_specific_not_landings(self) -> None:
        # Расшаривание ссылки на конкретное авто (частый канал для авто-лидов —
        # WhatsApp/Telegram) обязано показать заголовок и картинку этого авто, не
        # og:title/og:image лендинга (car_detail.html переопределяет {% block og %}).
        with (
            patch.object(crm_client, "get_site_config", return_value=SAMPLE_CONFIG),
            patch.object(crm_client, "get_car", return_value=SAMPLE_CAR),
            patch.object(crm_client, "get_cars", return_value=[SAMPLE_CAR]),
        ):
            response = self.client.get(reverse("storefront:car_detail", args=["kia-rio-2021"]))
        self.assertContains(response, 'property="og:type" content="product"')
        self.assertContains(response, 'property="og:title" content="Kia Rio 2021 в кредит от 4,9% — купить')
        self.assertContains(response, f'property="og:image" content="{SAMPLE_CAR["photo_url"]}"')
        self.assertNotContains(response, SAMPLE_CONFIG["seo"]["title_landing"])

    def test_does_not_load_calculator_or_chart_js(self) -> None:
        with (
            patch.object(crm_client, "get_site_config", return_value=SAMPLE_CONFIG),
            patch.object(crm_client, "get_car", return_value=SAMPLE_CAR),
            patch.object(crm_client, "get_cars", return_value=[SAMPLE_CAR]),
        ):
            response = self.client.get(reverse("storefront:car_detail", args=["kia-rio-2021"]))
        self.assertNotContains(response, "chart.umd.min.js")
        self.assertNotContains(response, "calculator.js")

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
