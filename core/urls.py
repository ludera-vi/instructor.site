"""
URL-маршруты основного приложения.
"""
from django.urls import path
from . import views

urlpatterns = [
    # ── Публичные страницы ────────────────────────────────────────
    path("",              views.index,           name="index"),
    path("booking/",      views.booking_page,    name="booking"),
    path("booking/success/", views.booking_success, name="booking_success"),
    path("privacy/",      views.privacy,         name="privacy"),

    # ── SEO-файлы (работают в dev; в продакшне отдаются веб-сервером напрямую) ──
    path("robots.txt",    views.robots_txt,      name="robots_txt"),
    path("sitemap.xml",   views.sitemap_xml,     name="sitemap_xml"),

    # ── Самообслуживание клиента ──────────────────────────────────
    path("my-booking/",            views.my_booking_page,       name="my_booking"),
    path("my-booking/find/",       views.find_my_booking,       name="find_booking"),
    path("my-booking/cancel/",     views.cancel_my_booking,     name="cancel_my_booking"),
    path("my-booking/reschedule/", views.reschedule_my_booking, name="reschedule_my_booking"),

    # ── AJAX API: публичный календарь ─────────────────────────────
    path("api/available-dates/", views.available_dates, name="available_dates"),
    path("api/schedule-summary/", views.schedule_summary, name="schedule_summary"),
    path("api/slots/",           views.slots_for_date,  name="slots_for_date"),
    path("api/book/",            views.create_booking,  name="create_booking"),

    # ── Аутентификация ────────────────────────────────────────────
    path("login/",  views.owner_login,  name="login"),
    path("logout/", views.owner_logout, name="logout"),

    # ── Личный кабинет ────────────────────────────────────────────
    path("dashboard/",                                   views.dashboard,             name="dashboard"),
    path("dashboard/day/<str:date_str>/",                views.dashboard_day,         name="dashboard_day"),

    # ── AJAX: операции со слотами ─────────────────────────────────
    path("dashboard/day/<str:date_str>/add-slot/",       views.add_single_slot,       name="add_single_slot"),
    path("dashboard/add-slots/",                         views.add_slots,             name="add_slots"),
    path("dashboard/delete-slot/<int:slot_id>/",         views.delete_slot,           name="delete_slot"),
    path("dashboard/toggle-slot/<int:slot_id>/",         views.toggle_slot,           name="toggle_slot"),

    # ── AJAX: операции с записями ─────────────────────────────────
    path("dashboard/cancel-booking/<int:booking_id>/",   views.cancel_booking,        name="cancel_booking"),
    path("dashboard/manual-booking/<int:slot_id>/",      views.create_manual_booking, name="create_manual_booking"),
    path("dashboard/owner-note/<int:booking_id>/",       views.add_owner_note,        name="add_owner_note"),
    path("dashboard/booking/<int:booking_id>/",          views.booking_detail,        name="booking_detail"),
    path("dashboard/booking/<int:booking_id>/update/",   views.booking_update,        name="booking_update"),
    path("dashboard/booking/<int:booking_id>/delete/",   views.booking_delete,        name="booking_delete"),

    # ── История и все записи ──────────────────────────────────────
    path("dashboard/history/",                               views.booking_history,    name="booking_history"),
    path("dashboard/all/",                                   views.all_bookings,       name="all_bookings"),
    path("dashboard/complete-booking/<int:booking_id>/",     views.complete_booking,   name="complete_booking"),
    path("dashboard/stats/",                                  views.dashboard_stats,    name="dashboard_stats"),
    path("dashboard/owner-reschedule/<int:booking_id>/",     views.owner_reschedule,   name="owner_reschedule"),
    path("dashboard/month/",                             views.dashboard_month,   name="dashboard_month"),

    # ── Управление услугами ───────────────────────────────────────────
    path("dashboard/services/",                          views.services_dashboard, name="services_dashboard"),
    path("dashboard/services/create/",                   views.service_create,     name="service_create"),
    path("dashboard/services/<int:pk>/update/",          views.service_update,     name="service_update"),
    path("dashboard/services/<int:pk>/toggle/",          views.service_toggle,     name="service_toggle"),
    path("dashboard/services/<int:pk>/delete/",          views.service_delete,     name="service_delete"),
    path("dashboard/services/reorder/",                  views.service_reorder,    name="service_reorder"),
]
