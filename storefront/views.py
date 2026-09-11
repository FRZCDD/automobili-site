from __future__ import annotations

from http import HTTPStatus

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View

from . import crm_client, seo

_LEAD_ERROR_MESSAGES = {
    HTTPStatus.TOO_MANY_REQUESTS: "Слишком много заявок подряд, попробуйте через минуту.",
    HTTPStatus.BAD_REQUEST: "Не получилось отправить заявку — проверьте имя и телефон.",
}
_DEFAULT_LEAD_ERROR_MESSAGE = "Не получилось отправить заявку, попробуйте ещё раз чуть позже."


def _unavailable(request: HttpRequest) -> HttpResponse:
    """CRM не ответила вовремя, или для SITE_SLUG вообще нет сайта в CRM — в обоих
    случаях посетителю нечего показать, кроме вежливой заглушки, а не 500."""
    return render(request, "errors/unavailable.html", status=HTTPStatus.SERVICE_UNAVAILABLE)


class LandingView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        try:
            config = crm_client.get_site_config()
            cars = crm_client.get_cars()
        except (crm_client.CrmUnavailableError, crm_client.CrmClientError):
            return _unavailable(request)
        if config is None:
            return _unavailable(request)
        context = {
            "site": config,
            "cars": cars,
            "new_cars": [car for car in cars if car["is_new"]],
            "used_cars": [car for car in cars if not car["is_new"]],
            "jsonld": seo.build_landing_jsonld(request, config),
        }
        return render(request, "index.html", context)


class CarDetailView(View):
    def get(self, request: HttpRequest, car_slug: str) -> HttpResponse:
        # get_site_config() первым и отдельно: если для SITE_SLUG нет сайта в CRM,
        # это ошибка деплоя, не зависящая от car_slug — нет смысла тратить ещё два
        # запроса к CRM (get_car, get_cars) на страницу, которая всё равно окажется
        # заглушкой недоступности.
        try:
            config = crm_client.get_site_config()
        except (crm_client.CrmUnavailableError, crm_client.CrmClientError):
            return _unavailable(request)
        if config is None:
            return _unavailable(request)

        try:
            car = crm_client.get_car(car_slug)
            cars = crm_client.get_cars()
        except (crm_client.CrmUnavailableError, crm_client.CrmClientError):
            return _unavailable(request)
        if car is None:
            return render(request, "errors/car_not_found.html", status=HTTPStatus.NOT_FOUND)

        car_url = request.build_absolute_uri(reverse("storefront:car_detail", args=[car_slug]))
        context = {
            "site": config,
            "car": car,
            "related_cars": [c for c in cars if c["slug"] != car_slug][:3],
            "seo_title": seo.car_page_title(config, car),
            "seo_description": seo.car_page_description(config, car),
            "car_url": car_url,
            "jsonld": seo.build_car_jsonld(request, config, car, car_url),
        }
        return render(request, "car_detail.html", context)


class LeadSubmitView(View):
    """Приём формы заявки этого сайта: то, что раньше шло прямо в CRM с той же
    страницы, теперь идёт через backend этого сайта — не через прямой fetch из
    браузера на чужой домен. CRM не настраивался на CORS ради этого POST (и не
    должен: обычный form-POST с CSRF-токеном на свой же домен — стандартный,
    отработанный сценарий Django, тогда как cross-origin fetch с браузера потребовал
    бы держать в CRM список разрешённых источников для одной-единственной публичной
    ручки). Здесь же можно и сообщение об ошибке показать по-русски и по делу,
    вместо RFC 9457 Problem Details, рассчитанных на разработчика, а не посетителя.
    """

    def post(self, request: HttpRequest) -> JsonResponse:
        name = request.POST.get("name", "").strip()
        phone = request.POST.get("phone", "").strip()
        if not name or not phone:
            return JsonResponse(
                {"status": "error", "message": _LEAD_ERROR_MESSAGES[HTTPStatus.BAD_REQUEST]},
                status=HTTPStatus.BAD_REQUEST,
            )
        try:
            result = crm_client.submit_lead(
                name=name,
                phone=phone,
                car_name=request.POST.get("car_name", "").strip(),
                utm_source=request.POST.get("utm_source", "").strip(),
                utm_medium=request.POST.get("utm_medium", "").strip(),
                utm_campaign=request.POST.get("utm_campaign", "").strip(),
            )
        except crm_client.CrmUnavailableError:
            return JsonResponse(
                {"status": "error", "message": _DEFAULT_LEAD_ERROR_MESSAGE},
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )
        except crm_client.CrmClientError as exc:
            passthrough_statuses = {HTTPStatus.BAD_REQUEST, HTTPStatus.TOO_MANY_REQUESTS}
            status = exc.status_code if exc.status_code in passthrough_statuses else HTTPStatus.BAD_GATEWAY
            # exc.status_code — plain int (CRM/прокси может вернуть нестандартный код
            # вроде 521-524, как раз в момент сбоя), поэтому не заворачивать в
            # HTTPStatus(...) — тот кидает ValueError на неизвестном коде, и обработчик
            # ошибок CRM сам уронит запрос в 500. HTTPStatus — IntEnum, .get() со
            # значениями-ключами HTTPStatus.X корректно матчит и обычный int.
            message = _LEAD_ERROR_MESSAGES.get(exc.status_code, _DEFAULT_LEAD_ERROR_MESSAGE)
            return JsonResponse({"status": "error", "message": message}, status=status)
        return JsonResponse(
            {"status": "success", "message": result.message, "lead_id": result.lead_id},
            status=HTTPStatus.CREATED,
        )


def robots_txt(request: HttpRequest) -> HttpResponse:
    body = render_to_string("robots.txt", {"sitemap_url": request.build_absolute_uri(reverse("sitemap"))})
    return HttpResponse(body, content_type="text/plain")


def sitemap_xml(request: HttpRequest) -> HttpResponse:
    """Простой ручной sitemap вместо django.contrib.sitemaps: тот рассчитан на
    querysets из своей БД, а список страниц здесь — лендинг плюс карточки авто из
    CRM API. Недоступность CRM не должна ронять sitemap 500-й — отдаём то, что есть
    (хотя бы лендинг), а не падаем."""
    urls = [request.build_absolute_uri(reverse("storefront:landing"))]
    try:
        cars = crm_client.get_cars()
    except (crm_client.CrmUnavailableError, crm_client.CrmClientError):
        cars = []
    urls.extend(request.build_absolute_uri(reverse("storefront:car_detail", args=[car["slug"]])) for car in cars)
    body = render_to_string("sitemap.xml", {"urls": urls})
    return HttpResponse(body, content_type="application/xml")
