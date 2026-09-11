"""Общие фикстуры для тестов вьюх/SEO — форма ровно та, что отдаёт CRM API
(``SiteConfigResponse`` / ``CarDetailResponse`` в apps/catalog/schemas.py CRM)."""

from __future__ import annotations

from typing import Any

SAMPLE_CONFIG: dict[str, Any] = {
    "slug": "autocredit",
    "name": "AUTOCREDIT",
    "domain": "",
    "is_active": True,
    "branding": {
        "logo_text_primary": "AUTO",
        "logo_text_secondary": "CREDIT",
        "logo_accent": "primary",
        "logo_image_url": "",
        "favicon_url": "",
        "brand_color": "",
        "price_color": "",
        "hero_title": "Автокредит от 4,9% — оформление онлайн за 5 минут",
        "slogan": "Оставьте заявку по 2 документам, без первоначального взноса и без КАСКО.",
    },
    "contacts": {
        "legal_name": "ООО «АВТОКРЕДИТ»",
        "phone": "8 800 000-00-00",
        "phone_hours": "Ежедневно 9:00–21:00",
        "email": "",
        "address": "г. Москва, ул. Примерная, д. 1",
        "inn": "",
        "ogrn": "",
        "privacy_policy_url": "",
        "same_as": [],
    },
    "seo": {
        "title_landing": "Автокредит от 4,9% — заявка онлайн за 5 минут | AUTOCREDIT",
        "description_landing": "Автокредит без первоначального взноса и без КАСКО, по двум документам.",
        "title_showcase": "Автомобили в кредит — витрина, ставка от 4,9% | AUTOCREDIT",
        "description_showcase": "Витрина автомобилей в кредит.",
        "title_car_template": "{brand} {model} {year} в кредит от 4,9% — купить | AUTOCREDIT",
        "description_car_template": "{brand} {model}, {year} — {price} ₽. В кредит от {monthly} ₽/мес.",
        "og_image_url": "",
        "bottom_text": '<p>Автокредит оформляется онлайн. <a href="/cars/kia-rio-2021/">Kia Rio</a> в наличии.</p>',
    },
    "calc": {
        "annual_rate": "4.90",
        "price": {"min": 500000, "max": 8000000, "step": 50000, "default": 2000000},
        "down_pct": {"min": 0, "max": 80, "step": 5, "default": 0},
        "term": {"min": 6, "max": 96, "step": 6, "default": 60},
    },
    "faq": [
        {"question": "Как оформить автокредит без первоначального взноса?", "answer": "Оставьте заявку онлайн."},
    ],
}

SAMPLE_CAR: dict[str, Any] = {
    "slug": "kia-rio-2021",
    "brand": "Kia",
    "model": "Rio",
    "year": 2021,
    "mileage": 0,
    "is_new": True,
    "engine_volume": "1.6",
    "engine_power": 123,
    "transmission": "AT",
    "transmission_display": "Автомат",
    "engine_type": "petrol",
    "engine_type_display": "Бензин",
    "price": "1500000",
    "monthly_payment": "25000",
    "min_down_payment": "0",
    "is_featured": False,
    "photo_url": "http://crm.invalid/media/kia.jpg",
    "url": "http://crm.invalid/cars/kia-rio-2021/",
    "description": "Отличный городской седан.",
    "meta_title": "",
    "meta_description": "",
}
