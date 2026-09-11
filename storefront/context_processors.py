from __future__ import annotations

from typing import Any

from django.http import HttpRequest


def canonical_url(request: HttpRequest) -> dict[str, Any]:
    """``request.build_absolute_uri(request.path)`` — без query string — доступный
    во всех шаблонах как дефолт для ``<link rel="canonical">``/``og:url``. Django
    template language не умеет вызвать метод с аргументом прямо в ``{{ }}``
    (``request.build_absolute_uri`` без скобок и без аргумента отдал бы URL вместе
    с query string, включая utm_-метки — см. templates/base.html), поэтому
    вычисляем здесь, а не в шаблоне. Страница может переопределить его через
    ``{% block canonical %}``/``{% block og %}`` своим собственным URL (так делает
    car_detail.html — там canonical обязан указывать на конкретное авто, не на
    текущий request.path с точки зрения Django, а на адрес, который строит вьюха
    через reverse())."""
    return {"canonical_url": request.build_absolute_uri(request.path)}
