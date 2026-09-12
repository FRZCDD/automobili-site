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
from html import escape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

from django.http import HttpRequest
from django.urls import reverse

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


def car_page_title(config: dict[str, Any], car: dict[str, Any]) -> str:
    """``<title>``/``og:title`` карточки авто: сначала шаблон из CRM с подставленными
    данными этого авто, если оператор его не заполнил — собственный `meta_title`
    авто из CRM, а если и его нет — короткое «Марка Модель Год». Три уровня
    фолбэка, а не один, потому что оба источника в CRM — необязательные текстовые
    поля админки, оставленные пустыми на только что заведённом сайте/авто не
    должны обернуться пустым ``<title>``."""
    values = car_seo_values(car)
    template = config["seo"]["title_car_template"]
    fallback = car.get("meta_title") or f"{car['brand']} {car['model']} {car['year']}"
    return render_seo_template(template, **values) or fallback


def car_page_description(config: dict[str, Any], car: dict[str, Any]) -> str:
    values = car_seo_values(car)
    template = config["seo"]["description_car_template"]
    return render_seo_template(template, **values) or car.get("meta_description") or ""


_RICH_TEXT_ALLOWED_TAGS = frozenset({"p", "a", "br", "strong", "em", "b", "i", "ul", "ol", "li"})
# script/style — единственные теги, чьё *содержимое* тоже выбрасывается, не только
# сам тег: это не разметка, а код/CSS, и показать его как обычный видимый текст
# было бы такой же утечкой, как оставить его исполняемым.
_RICH_TEXT_DROP_CONTENT_TAGS = frozenset({"script", "style"})
_RICH_TEXT_VOID_TAGS = frozenset({"br"})


def _is_safe_rich_text_href(href: str) -> bool:
    """``javascript:``/``data:`` — обычный способ получить исполнение кода через
    <a href> в HTML, который не идёт через <script>. Разрешены только http(s) и
    настоящие относительные пути: URL вида "//evil.example/x" формально не имеет
    схемы, но имеет netloc — это protocol-relative ссылка на чужой хост, а не
    относительный путь на этом сайте, поэтому тоже отклоняется."""
    try:
        parsed = urlparse(href)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") or (parsed.scheme == "" and not parsed.netloc)


class _RichTextSanitizer(HTMLParser):
    """Allow-list санитайзер HTML для CRM-редактируемого ``site.seo.bottom_text``
    (см. sanitize_rich_text ниже) — только stdlib, без bleach/nh3 (недоступны в этом
    окружении, зависимости не добавляем). HTMLParser не падает на битой/незакрытой
    разметке — это важно именно здесь, потому что вход печатает человек в CRM-админке,
    а не система."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        self._skip_depth = 0  # вложенность внутри <script>/<style>

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _RICH_TEXT_DROP_CONTENT_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth or tag not in _RICH_TEXT_ALLOWED_TAGS:
            return
        if tag == "a":
            href = dict(attrs).get("href")
            # Все остальные атрибуты (в т.ч. href с опасной схемой) отбрасываются
            # молча — тег и его текст остаются, ссылка перестаёт быть кликабельной.
            if href and _is_safe_rich_text_href(href):
                self._out.append(f'<a href="{escape(href, quote=True)}">')
            else:
                self._out.append("<a>")
        else:
            self._out.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in _RICH_TEXT_DROP_CONTENT_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth or tag not in _RICH_TEXT_ALLOWED_TAGS or tag in _RICH_TEXT_VOID_TAGS:
            return
        self._out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._out.append(escape(data))

    def get_html(self) -> str:
        return "".join(self._out)


def sanitize_rich_text(html_text: str) -> str:
    """Санитайзер для CRM-редактируемого rich-текста (``site.seo.bottom_text``,
    легитимный вид — storefront/tests/factories.py), который рендерится в
    templates/index.html через ``|safe``: без этого CRM-текст с <script>/onerror=
    был бы обычным XSS. Allow-list из горстки тегов (см.
    _RICH_TEXT_ALLOWED_TAGS/_RichTextSanitizer) — та же логика, что в
    render_seo_template выше: явный список разрешённого, а не попытка распознать и
    вычистить запрещённое."""
    if not html_text:
        return ""
    parser = _RichTextSanitizer()
    parser.feed(html_text)
    parser.close()
    return parser.get_html()


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


_JSONLD_SCRIPT_ESCAPES = {
    ord("<"): "\\u003C",
    ord(">"): "\\u003E",
    ord("&"): "\\u0026",
}


def _dumps_for_script(value: Any) -> str:
    """json.dumps() не экранирует < > & — без этого CRM-текст (ответ FAQ, описание
    авто, имя контакта и т.д.), содержащий "</script>", разорвал бы
    <script type="application/ld+json"> тег, в который результат попадает через
    {{ jsonld|safe }} (templates/base.html). Те же три символа и то же \\uXXXX
    экранирование, что использует django.utils.html.json_script
    (_json_script_escapes) — здесь просто нет самого фильтра json_script, потому что
    <script> в base.html оформлен не под его вывод."""
    return json.dumps(value, ensure_ascii=False).translate(_JSONLD_SCRIPT_ESCAPES)


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
    return _dumps_for_script({"@context": "https://schema.org", "@graph": graph})


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
    landing_url = request.build_absolute_uri(reverse("storefront:landing"))
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        # Три уровня — ровно то, что показывает видимая хлебная крошка на странице
        # (Главная / Каталог / <авто>, templates/car_detail.html): структурированные
        # данные обязаны совпадать с видимым содержимым (требование Google к rich
        # results), а не молчаливо укорачивать реальную навигацию.
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Главная", "item": landing_url},
            {"@type": "ListItem", "position": 2, "name": "Каталог", "item": f"{landing_url}#catalog"},
            {"@type": "ListItem", "position": 3, "name": f"{car['brand']} {car['model']}", "item": car_url},
        ],
    }
    return _dumps_for_script([organization, product, breadcrumb])
