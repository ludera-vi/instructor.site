"""
Главный файл маршрутизации URL.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView

urlpatterns = [
    # favicon.ico — Яндекс и браузеры обращаются к корню /favicon.ico
    path("favicon.ico", RedirectView.as_view(url="/static/favicon.ico", permanent=True)),
    # Стандартная Django-admin панель (отдельно от кабинета владельца)
    path("admin/", admin.site.urls),
    # Все маршруты основного приложения
    path("", include("core.urls")),
]

# В режиме разработки — обслуживаем медиафайлы напрямую
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
