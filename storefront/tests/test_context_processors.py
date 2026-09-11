"""Тесты context processors."""

from __future__ import annotations

from django.test import RequestFactory, SimpleTestCase

from storefront.context_processors import canonical_url


class CanonicalUrlTests(SimpleTestCase):
    """Context processor canonical_url вычисляет URL без query string."""

    def test_returns_absolute_url_without_query_string(self) -> None:
        factory = RequestFactory()
        request = factory.get("/cars/kia-rio/")
        result = canonical_url(request)
        assert result == {"canonical_url": "http://testserver/cars/kia-rio/"}

    def test_strips_utm_parameters(self) -> None:
        factory = RequestFactory()
        request = factory.get("/?utm_source=yandex&utm_medium=cpc")
        result = canonical_url(request)
        assert result == {"canonical_url": "http://testserver/"}

    def test_root_path(self) -> None:
        factory = RequestFactory()
        request = factory.get("/")
        result = canonical_url(request)
        assert result == {"canonical_url": "http://testserver/"}

    def test_nested_path(self) -> None:
        factory = RequestFactory()
        request = factory.get("/some/deeply/nested/path/")
        result = canonical_url(request)
        assert result == {"canonical_url": "http://testserver/some/deeply/nested/path/"}

    def test_path_without_trailing_slash(self) -> None:
        factory = RequestFactory()
        request = factory.get("/no-trailing-slash")
        result = canonical_url(request)
        assert result == {"canonical_url": "http://testserver/no-trailing-slash"}
