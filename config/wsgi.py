"""WSGI config for automobili-site. Served by gunicorn in production (see Dockerfile)."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

application = get_wsgi_application()
