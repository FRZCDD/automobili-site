from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.urls import include, path

from storefront import views as storefront_views


def health(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok")


urlpatterns = [
    path(settings.HEALTHCHECK_PATH.lstrip("/"), health, name="health"),
    path("robots.txt", storefront_views.robots_txt, name="robots"),
    path("sitemap.xml", storefront_views.sitemap_xml, name="sitemap"),
    path("", include("storefront.urls")),
]
