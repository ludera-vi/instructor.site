"""
WSGI-конфигурация для деплоя на сервере.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "driving_instructor.settings")
application = get_wsgi_application()
