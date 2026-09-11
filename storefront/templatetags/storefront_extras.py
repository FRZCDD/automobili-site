from __future__ import annotations

import re

from django import template

register = template.Library()

_NON_DIAL_RE = re.compile(r"[^\d+]")


@register.filter
def phone_href(phone: str) -> str:
    """``8 800 000-00-00`` → ``880000000-00`` бы отдавал мусор в tel:; здесь только
    цифры и ведущий ``+`` — то, что телефон реально умеет набрать."""
    return _NON_DIAL_RE.sub("", phone or "")


@register.filter
def rub(value: object) -> str:
    """``2000000`` → ``2 000 000`` — CRM отдаёт цену/платёж строкой без разрядов."""
    try:
        number = int(str(value))
    except (TypeError, ValueError):
        return str(value)
    return f"{number:,}".replace(",", " ")
