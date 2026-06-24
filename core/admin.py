"""
Регистрация моделей в стандартной Django admin-панели.
"""
from django.contrib import admin
from .models import TimeSlot, Booking, Service


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ("date", "start_time", "end_time", "is_available", "is_booked_display", "created_at")
    list_filter = ("date", "is_available")
    ordering = ("date", "start_time")
    date_hierarchy = "date"

    def is_booked_display(self, obj):
        return "✅ Занят" if obj.is_booked else "🟢 Свободен"
    is_booked_display.short_description = "Статус"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "slot", "service", "created_at")
    list_filter = ("slot__date", "service")
    search_fields = ("name", "phone")
    ordering = ("slot__date", "slot__start_time")
    readonly_fields = ("created_at",)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("title", "emoji", "price", "is_active", "order")
    list_editable = ("is_active", "order")
    list_display_links = ("title",)
    list_filter = ("is_active",)
    ordering = ("order",)

# Настройка заголовков Django admin
admin.site.site_header = "Иван Гуничев — Управление"
admin.site.site_title = "Инструктор по вождению"
admin.site.index_title = "Панель управления"
