from __future__ import annotations

import json

from django.test import RequestFactory, SimpleTestCase

from storefront.seo import (
    build_car_jsonld,
    build_landing_jsonld,
    car_page_description,
    car_page_title,
    render_seo_template,
    sanitize_rich_text,
)

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

    def test_faq_answer_script_breakout_is_escaped(self) -> None:
        # json.dumps() сам по себе не экранирует < > & — без этого CRM-текст с
        # "</script>" разорвал бы <script type="application/ld+json"> тег, в который
        # jsonld попадает через {{ jsonld|safe }} в templates/base.html.
        payload = "</script><script>alert(1)</script>"
        config = {**SAMPLE_CONFIG, "faq": [{"question": "Q", "answer": payload}]}
        request = RequestFactory().get("/")
        raw = build_landing_jsonld(request, config)
        assert "</script>" not in raw
        assert "<script>" not in raw
        graph = json.loads(raw)["@graph"]
        faq_page = next(item for item in graph if item["@type"] == "FAQPage")
        # После json.loads() исходный текст восстанавливается один в один — экранирование
        # меняет только сериализованную форму, не сами данные.
        assert faq_page["mainEntity"][0]["acceptedAnswer"]["text"] == payload


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

    def test_description_script_breakout_is_escaped(self) -> None:
        payload = "</script><script>alert(1)</script>"
        car = {**SAMPLE_CAR, "description": payload}
        request = RequestFactory().get("/cars/kia-rio-2021/")
        car_url = "http://testserver/cars/kia-rio-2021/"
        raw = build_car_jsonld(request, SAMPLE_CONFIG, car, car_url)
        assert "</script>" not in raw
        assert "<script>" not in raw
        items = json.loads(raw)
        product = next(item for item in items if item["@type"] == "Product")
        assert product["description"] == payload

    def test_breadcrumb_has_three_levels_matching_visible_nav(self) -> None:
        # templates/car_detail.html показывает Главная / Каталог / <авто> — структурные
        # данные обязаны совпадать с этим, а не укорачивать реальную навигацию до двух
        # уровней (Google, требования к rich results для BreadcrumbList).
        request = RequestFactory().get("/cars/kia-rio-2021/")
        car_url = "http://testserver/cars/kia-rio-2021/"
        items = json.loads(build_car_jsonld(request, SAMPLE_CONFIG, SAMPLE_CAR, car_url))
        breadcrumb = next(item for item in items if item["@type"] == "BreadcrumbList")
        names = [entry["name"] for entry in breadcrumb["itemListElement"]]
        assert names == ["Главная", "Каталог", "Kia Rio"]
        assert [entry["position"] for entry in breadcrumb["itemListElement"]] == [1, 2, 3]
        assert breadcrumb["itemListElement"][-1]["item"] == car_url


class CarPageTitleTests(SimpleTestCase):
    def test_uses_crm_template_when_present(self) -> None:
        title = car_page_title(SAMPLE_CONFIG, SAMPLE_CAR)
        assert title == "Kia Rio 2021 в кредит от 4,9% — купить | AUTOCREDIT"

    def test_falls_back_to_car_meta_title_when_template_empty(self) -> None:
        config = {**SAMPLE_CONFIG, "seo": {**SAMPLE_CONFIG["seo"], "title_car_template": ""}}
        car = {**SAMPLE_CAR, "meta_title": "Kia Rio — из CRM meta_title"}
        assert car_page_title(config, car) == "Kia Rio — из CRM meta_title"

    def test_falls_back_to_brand_model_year_when_both_empty(self) -> None:
        config = {**SAMPLE_CONFIG, "seo": {**SAMPLE_CONFIG["seo"], "title_car_template": ""}}
        car = {**SAMPLE_CAR, "meta_title": ""}
        assert car_page_title(config, car) == "Kia Rio 2021"


class CarPageDescriptionTests(SimpleTestCase):
    def test_uses_crm_template_when_present(self) -> None:
        description = car_page_description(SAMPLE_CONFIG, SAMPLE_CAR)
        assert description == "Kia Rio, 2021 — 1500000 ₽. В кредит от 25000 ₽/мес."

    def test_falls_back_to_car_meta_description_when_template_empty(self) -> None:
        config = {**SAMPLE_CONFIG, "seo": {**SAMPLE_CONFIG["seo"], "description_car_template": ""}}
        car = {**SAMPLE_CAR, "meta_description": "Из CRM meta_description"}
        assert car_page_description(config, car) == "Из CRM meta_description"

    def test_falls_back_to_empty_string_when_both_empty(self) -> None:
        config = {**SAMPLE_CONFIG, "seo": {**SAMPLE_CONFIG["seo"], "description_car_template": ""}}
        car = {**SAMPLE_CAR, "meta_description": ""}
        assert car_page_description(config, car) == ""


class SanitizeRichTextTests(SimpleTestCase):
    """Allow-list санитайзер CRM-редактируемого ``site.seo.bottom_text``
    (templates/index.html рендерит его через ``|safe``)."""

    def test_empty_input_returns_empty_string(self) -> None:
        assert sanitize_rich_text("") == ""

    def test_legitimate_bottom_text_is_preserved(self) -> None:
        # storefront/tests/factories.py — форма bottom_text, которую реально
        # присылает CRM: параграф с обычной ссылкой на карточку авто этого сайта.
        html_text = SAMPLE_CONFIG["seo"]["bottom_text"]
        assert sanitize_rich_text(html_text) == html_text

    def test_script_tag_and_its_content_are_stripped(self) -> None:
        result = sanitize_rich_text("<p>Текст <script>alert(document.cookie)</script> ещё текст</p>")
        assert "<script" not in result
        assert "alert" not in result
        assert "Текст" in result
        assert "ещё текст" in result

    def test_disallowed_tag_is_stripped_but_its_attributes_cannot_leak_as_text(self) -> None:
        result = sanitize_rich_text('<p>Клик <img src="x" onerror="alert(1)"> тут</p>')
        assert "onerror" not in result
        assert "<img" not in result
        assert "Клик" in result
        assert "тут" in result

    def test_javascript_href_is_dropped_but_tag_and_text_are_kept(self) -> None:
        result = sanitize_rich_text('<a href="javascript:alert(1)">Клик</a>')
        assert "javascript:" not in result
        assert result == "<a>Клик</a>"

    def test_relative_href_is_kept(self) -> None:
        result = sanitize_rich_text('<a href="/cars/kia-rio-2021/">Kia Rio</a>')
        assert result == '<a href="/cars/kia-rio-2021/">Kia Rio</a>'
