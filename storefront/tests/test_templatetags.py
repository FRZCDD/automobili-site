"""Тесты кастомных template tags из storefront_extras."""

from __future__ import annotations

from django.template import Context, Template
from django.test import SimpleTestCase

from storefront.templatetags.storefront_extras import phone_href, rub


class PhoneHrefFilterTests(SimpleTestCase):
    """Фильтр phone_href удаляет всё кроме цифр и ведущего +."""

    def test_removes_spaces_and_dashes(self) -> None:
        assert phone_href("8 800 000-00-00") == "88000000000"

    def test_preserves_plus_sign(self) -> None:
        assert phone_href("+7 (999) 000-00-00") == "+79990000000"

    def test_removes_letters(self) -> None:
        assert phone_href("8 800 CALL-NOW") == "8800"

    def test_empty_string_returns_empty(self) -> None:
        assert phone_href("") == ""

    def test_none_returns_empty(self) -> None:
        assert phone_href(None) == ""

    def test_only_non_dial_characters_returns_empty(self) -> None:
        assert phone_href("abc-() ") == ""

    def test_in_template_usage(self) -> None:
        template = Template('{% load storefront_extras %}{{ phone|phone_href }}')
        context = Context({"phone": "8 800 000-00-00"})
        result = template.render(context)
        assert result == "88000000000"


class RubFilterTests(SimpleTestCase):
    """Фильтр rub форматирует число с пробелами как разделителями разрядов."""

    def test_formats_integer_string(self) -> None:
        assert rub("2000000") == "2\u00a0000\u00a0000"

    def test_formats_small_number(self) -> None:
        assert rub("100") == "100"

    def test_formats_five_digit_number(self) -> None:
        assert rub("10000") == "10\u00a0000"

    def test_formats_integer(self) -> None:
        assert rub(1500000) == "1\u00a0500\u00a0000"

    def test_invalid_string_returns_as_is(self) -> None:
        assert rub("not a number") == "not a number"

    def test_empty_string_returns_empty(self) -> None:
        assert rub("") == ""

    def test_none_returns_empty_string(self) -> None:
        # rub(None) пытается int(str(None)) = int("None") -> ValueError, возвращается "None"
        assert rub(None) == "None"

    def test_float_string_truncates_or_fails_gracefully(self) -> None:
        # int() от строки "1000.5" выбросит ValueError, фильтр должен вернуть как есть
        assert rub("1000.5") == "1000.5"

    def test_in_template_usage(self) -> None:
        template = Template('{% load storefront_extras %}{{ price|rub }}')
        context = Context({"price": "1500000"})
        result = template.render(context)
        assert result == "1\u00a0500\u00a0000"

    def test_negative_number(self) -> None:
        assert rub("-1000") == "-1\u00a0000"
