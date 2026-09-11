# automobili-site — эталонная публичная витрина

Тонкий Django-рендерер одного публичного сайта платформы `automobili-zaluppini`.
У него **нет своей базы данных** и **нет собственного контента**: брендинг, слоган,
логотип, параметры кредитного калькулятора, SEO-тексты, FAQ и каталог автомобилей —
всё это правится в Django-админке CRM (`automobili-zaluppini`, раздел «Сайты-источники»)
и приходит на эту витрину по HTTP при каждом запросе. Заявки с формы уходят обратно в
CRM, в общий пул лидов.

Это эталон архитектуры «CRM + N независимых сайтов-витрин»: у платформы будет ~10
таких сайтов, каждый — отдельный репозиторий и отдельный деплой с одним и тем же
кодом, но своим набором переменных окружения (`SITE_SLUG` + свой домен).

## Архитектура

```
Посетитель → этот сайт (Django, без БД) → CRM automobili-zaluppini (read/write API)
                                              │
                                              └─ Django-админка CRM: тут всё редактируется
```

- `GET /api/v1/sites/<SITE_SLUG>/config/` — брендинг, контакты, SEO-шаблоны, параметры
  калькулятора, FAQ.
- `GET /api/v1/sites/<SITE_SLUG>/cars/` и `.../cars/<slug>/` — каталог и карточка авто.
- `POST /api/v1/leads/create/` — приём заявки (эту витрину идентифицирует поле `site`).

Всё это — `storefront/crm_client.py`, единственная точка интеграции. Ответы
`config`/`cars` кэшируются локально на `SITE_CONFIG_CACHE_TTL_SECONDS` (по умолчанию
60 с) — это не источник истины, просто защита CRM от запроса на каждый визит.

Заявка идёт не напрямую из браузера в CRM, а через свой backend
(`POST /leads/submit/` → `storefront.crm_client.submit_lead` → CRM): так не нужен
CORS на CRM ради одной публичной ручки, а сайт может показать посетителю понятную
ошибку по-русски вместо RFC 9457 Problem Details, рассчитанных на разработчика.

## Быстрый старт (локально)

Нужны: Python 3.12, [uv](https://docs.astral.sh/uv/), Node 18+ (только для сборки
CSS), запущенная локально CRM (`automobili-zaluppini`) с сидированным сайтом
`autocredit` (миграция `0025_seed_default_site` в CRM создаёт его автоматически).

```bash
cp .env.example .env
# в .env — CRM_API_BASE_URL на адрес локальной CRM, SITE_SLUG=autocredit

task assets:build   # соберёт static/css/tailwind.css (нужен один раз и после правки шаблонов)
uv run python manage.py runserver
```

Без `uv` — тот же результат через одноразовый контейнер:

```bash
docker run --rm -v "$(pwd):/app" -w /app -p 8000:8000 \
  -e CRM_API_BASE_URL=http://host.docker.internal:8000 -e SITE_SLUG=autocredit \
  ghcr.io/astral-sh/uv:python3.12-bookworm \
  bash -c "uv pip install --system -r pyproject.toml && python manage.py runserver 0.0.0.0:8000"
```

## Тесты

Своей базы данных нет — тесты (`SimpleTestCase`) не поднимают БД вообще, каждый мок
`storefront.crm_client`, так что ни один тест не требует запущенной CRM:

```bash
task test
# или: uv run python manage.py test storefront
```

## Как завести второй сайт на этом же коде

1. Создать `SourceSite` в админке CRM (свой slug, брендинг, калькулятор, SEO, FAQ).
2. Задеплоить этот же образ с `SITE_SLUG=<новый-slug>` и своим доменом в
   `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`.

Кода менять не нужно — весь контент приходит из CRM по slug.

## Структура

- `config/` — настройки Django (`base.py` общий, `development.py`/`production.py`/`test.py`).
  Без `contrib.auth`/`sessions`/`admin` — они не нужны тонкому рендереру.
- `storefront/` — единственное приложение: `crm_client.py` (HTTP-клиент CRM),
  `seo.py` (JSON-LD, безопасная подстановка в SEO-шаблоны карточки авто), `views.py`,
  `urls.py`, `templatetags/`.
- `templates/` — `base.html` + `index.html` (лендинг) + `car_detail.html` (карточка
  авто) + `partials/` (шапка, подвал, калькулятор, модалка заявки, карточка витрины,
  FAQ) + `robots.txt`/`sitemap.xml`.
- `static/js/site.js` — модалка заявки, маска телефона (IMask), калькулятор (Chart.js).
  Ванильный JS, без сборки.
- `static/src/input.css` + `tailwind.config.js` — исходник Tailwind (те же кастомные
  цвета `darkbg`/`cardbg`, что у CRM); собранный `static/css/tailwind.css` в
  репозитории не хранится, его делает `task assets:build` / build-стадия Dockerfile.

## Деплой

`Dockerfile` — три стадии: сборка Tailwind (Node), установка зависимостей (`uv`),
финальный слим-образ с `gunicorn`. Обязательные переменные окружения — `.env.example`.

Нет `requirements.txt`/лок-файла: репозиторий собирался в среде без `uv` под рукой,
поэтому зависимости резолвятся из `pyproject.toml` при каждой сборке образа. Когда
`uv` будет доступен, стоит зафиксировать лок-файл (`uv export -o requirements.txt`,
как это сделано в `automobili-zaluppini/app`) отдельным PR — это не меняет поведение,
только делает сборки воспроизводимыми.
