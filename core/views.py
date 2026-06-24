"""
Представления (views) для сайта инструктора по вождению.
"""
import json
import logging
import time as time_module
import calendar
import hashlib
from datetime import date, time, timedelta

logger = logging.getLogger(__name__)

from django.contrib.auth import login, logout
from django.views.decorators.cache import never_cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone as tz
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages

from .models import TimeSlot, Booking, Service
from .forms import BookingForm, AddSlotsForm, FindBookingForm, OwnerNoteForm, ManualBookingForm, _clean_phone
from .emails import notify_client_action
from .constants import BLOCK_RADIUS_MINUTES, QUICK_SLOT_TIMES


# ─── Публичные страницы ───────────────────────────────────────────────────────

def index(request):
    """Главная страница лендинга."""
    services = Service.objects.filter(is_active=True).order_by("order", "id")
    return render(request, "core/index.html", {"services": services})


def privacy(request):
    """Политика конфиденциальности."""
    return render(request, "core/privacy.html")


def robots_txt(request):
    """robots.txt — отдаётся Django в dev; в продакшне перехватывается веб-сервером."""
    content = (
        "User-agent: *\n"
        "Allow: /$\n"
        "Disallow: /\n\n"
        "Sitemap: https://ivan-gunichev.ru/sitemap.xml\n"
    )
    return HttpResponse(content, content_type="text/plain")


def sitemap_xml(request):
    """sitemap.xml — отдаётся Django в dev; в продакшне перехватывается веб-сервером."""
    content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://ivan-gunichev.ru/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""
    return HttpResponse(content, content_type="application/xml")


def booking_page(request):
    """Страница онлайн-записи с календарём."""
    form = BookingForm()
    return render(request, "core/booking.html", {"form": form})


def booking_success(request):
    """Страница подтверждения успешной записи."""
    booking_data = request.session.pop("last_booking", None)
    if not booking_data:
        return redirect("booking")
    return render(request, "core/booking_success.html", {"booking": booking_data})


# ─── AJAX API для публичного календаря ───────────────────────────────────────

@require_GET
def available_dates(request):
    """
    Возвращает даты с доступными слотами.
    Если указаны year/month — возвращает месяц (старое поведение).
    Если указан weeks — возвращает N недель вперёд от сегодня (новое поведение для бесшовного календаря).
    GET: ?weeks=6 → {YYYY-MM-DD: count} на 6 недель вперёд
    GET: ?year=X&month=Y → {YYYY-MM-DD: count} для месяца (обратная совместимость)

    Просто читает is_available из БД (слоты уже пересчитаны при открытии страницы переноса).
    """
    # Автоматически закрываем прошедшие слоты
    _auto_close_past_slots()

    today = date.today()

    # Новый режим: weeks=N (бесшовный календарь)
    weeks_param = request.GET.get("weeks")
    if weeks_param:
        try:
            weeks = int(weeks_param)
            weeks = max(1, min(weeks, 12))  # Ограничиваем 1-12 недель
            start_date = today
            end_date = today + timedelta(weeks=weeks)
        except (ValueError, TypeError):
            return JsonResponse({"error": "Некорректный параметр weeks"}, status=400)
    else:
        # Старый режим: year/month (обратная совместимость)
        try:
            year  = int(request.GET.get("year",  today.year))
            month = int(request.GET.get("month", today.month))
        except (ValueError, TypeError):
            return JsonResponse({"error": "Некорректные параметры"}, status=400)

        start_date = max(date(year, month, 1), today)
        _, last_day = calendar.monthrange(year, month)
        end_date = date(year, month, last_day)

    # Получаем все слоты в диапазоне
    all_slots = TimeSlot.objects.filter(
        date__range=(start_date, end_date)
    ).prefetch_related("booking").order_by("date", "start_time")

    # Группируем по датам и считаем свободные слоты
    dates_map = {}
    for slot in all_slots:
        d = slot.date.strftime("%Y-%m-%d")
        # Просто читаем is_available из БД — слоты уже пересчитаны на сервере
        if slot.is_available and not slot.is_booked and not slot.is_past:
            dates_map[d] = dates_map.get(d, 0) + 1

    return JsonResponse(dates_map)


@require_GET
def schedule_summary(request):
    """
    Возвращает сводку по слотам на N недель: свободные, занятые, завершённые, закрытые.
    GET: ?weeks=4 → {YYYY-MM-DD: {free: N, booked: N, completed: N, closed: N}}
    """
    _auto_complete_past_bookings()
    _auto_close_past_slots()

    today = date.today()
    weeks_param = request.GET.get("weeks", "4")

    try:
        weeks = int(weeks_param)
        weeks = max(1, min(weeks, 12))
        start_date = today
        end_date = today + timedelta(weeks=weeks)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Некорректный параметр weeks"}, status=400)

    # Получаем все слоты в диапазоне
    all_slots = TimeSlot.objects.filter(
        date__range=(start_date, end_date)
    ).prefetch_related("booking").order_by("date", "start_time")

    # Группируем по датам
    schedule_map = {}
    for slot in all_slots:
        d = slot.date.strftime("%Y-%m-%d")
        if d not in schedule_map:
            schedule_map[d] = {"free": 0, "booked": 0, "completed": 0, "closed": 0}

        if slot.is_booked:
            if slot.booking.status == Booking.STATUS_COMPLETED:
                schedule_map[d]["completed"] += 1
            else:
                schedule_map[d]["booked"] += 1
        elif not slot.is_available:
            schedule_map[d]["closed"] += 1
        elif not slot.is_past:
            schedule_map[d]["free"] += 1

    return JsonResponse(schedule_map)


@require_GET
def slots_for_date(request):
    """
    Возвращает слоты на конкретную дату.
    GET: date → [{id, time, available, status}, ...]

    Просто читает is_available из БД (слоты уже пересчитаны при открытии страницы переноса).
    """
    # Автоматически закрываем прошедшие слоты
    _auto_close_past_slots()

    date_str = request.GET.get("date")
    if not date_str:
        return JsonResponse({"error": "Параметр date обязателен"}, status=400)

    try:
        selected_date = date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse({"error": "Некорректный формат даты"}, status=400)

    slots = TimeSlot.objects.filter(date=selected_date).prefetch_related("booking")

    result = []
    for slot in slots:
        # Просто читаем is_available из БД — слоты уже пересчитаны на сервере
        is_free = slot.is_available and not slot.is_booked and not slot.is_past

        result.append({
            "id": slot.pk,
            "time": slot.get_time_range(),
            "start": slot.start_time.strftime("%H:%M"),
            "end": slot.end_time.strftime("%H:%M"),
            "available": is_free,
            "status": "free" if is_free else slot.status_class,
        })

    return JsonResponse(result, safe=False)


@require_POST
def create_booking(request):
    """
    AJAX: создать запись.
    Принимает JSON или form-data.
    """
    try:
        if request.content_type and "application/json" in request.content_type:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({"success": False, "error": "Некорректный JSON"}, status=400)
        else:
            data = request.POST

        form = BookingForm(data)

        if not form.is_valid():
            first_error = next(iter(form.errors.values()))[0]
            return JsonResponse({"success": False, "error": first_error}, status=400)

        cd = form.cleaned_data

        with transaction.atomic():
            try:
                slot = TimeSlot.objects.select_for_update().get(
                    pk=cd["slot_id"], is_available=True,
                )
            except TimeSlot.DoesNotExist:
                return JsonResponse(
                    {"success": False, "error": "Слот больше недоступен. Выберите другое время."},
                    status=409,
                )

            if slot.is_booked:
                return JsonResponse(
                    {"success": False, "error": "Этот слот уже занят. Выберите другое время."},
                    status=409,
                )

            booking = Booking.objects.create(
                slot=slot,
                name=cd["name"],
                phone=cd["phone"],
                comment=cd.get("comment", ""),
                service="",
                slot_date=slot.date,
                slot_time_str=slot.get_time_range(),
            )

        request.session["last_booking"] = {
            "name": booking.name,
            "phone": booking.phone,
            "date": slot.date.strftime("%d.%m.%Y"),
            "time": slot.get_time_range(),
            "comment": booking.comment,
        }

        try:
            notify_client_action(booking, "created")
        except Exception:
            pass

        try:
            _recompute_day_availability(slot.date)
        except Exception:
            logger.exception("_recompute_day_availability после create_booking")

        return JsonResponse({
            "success": True,
            "redirect": "/booking/success/",
            "message": "Запись успешно создана!",
        })

    except Exception as exc:
        logger.exception("create_booking: %s", exc)
        return JsonResponse({"success": False, "error": "Внутренняя ошибка сервера. Попробуйте ещё раз."}, status=500)


# ─── Самообслуживание клиента ─────────────────────────────────────────────────

@never_cache
def my_booking_page(request):
    """
    Страница самообслуживания: найти, отменить, перенести запись.
    @never_cache + no-store headers: защита от показа чужих данных из кеша браузера.
    """
    # Результат предыдущего действия (отмена / перенос) — показываем экран успеха
    action_result = request.session.pop("mybooking_result", None)
    if action_result:
        response = render(request, "core/my_booking.html", {"action_result": action_result})
        _set_no_cache_headers(response)
        return response

    # Каждый GET сбрасывает сессию — страница всегда просит ввести номер заново
    request.session.pop("client_bookings", None)
    form = FindBookingForm()
    response = render(request, "core/my_booking.html", {"form": form, "found_bookings": []})
    _set_no_cache_headers(response)
    return response


def _set_no_cache_headers(response):
    """Выставляет HTTP-заголовки запрета кеширования."""
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"]        = "no-cache"
    response["Expires"]       = "0"


@never_cache
@require_POST
def find_my_booking(request):
    """
    POST: ищет запись по номеру телефона.
    Rate-limiting через сессию: не более 8 попыток за 10 минут.
    """
    now = time_module.time()
    lookups = [t for t in request.session.get("booking_lookups", []) if now - t < 600]
    if len(lookups) >= 8:
        messages.error(request, "Слишком много попыток. Подождите немного или позвоните: +7 (905) 560-96-96")
        return redirect("my_booking")

    lookups.append(now)
    request.session["booking_lookups"] = lookups

    form = FindBookingForm(request.POST)
    if not form.is_valid():
        return render(request, "core/my_booking.html", {"form": form, "found_bookings": []})

    phone = form.cleaned_data["phone"]
    bookings = list(
        Booking.objects.filter(phone=phone, slot__date__gte=date.today())
        .select_related("slot")
        .order_by("slot__date", "slot__start_time")
    )

    if not bookings:
        messages.warning(
            request,
            f"Запись для номера {phone} не найдена. "
            "Возможно, занятие уже прошло или запись была отменена.",
        )
        return render(request, "core/my_booking.html", {"form": form, "found_bookings": []})

    request.session["client_bookings"] = {
        "phone": phone,
        "entries": [
            {"booking_id": b.id, "token": _make_booking_token(b.id, phone)}
            for b in bookings
        ],
    }
    # Рендерим напрямую — не делаем redirect, чтобы сессия не сбросилась
    form = FindBookingForm()
    response = render(request, "core/my_booking.html", {
        "form": form,
        "found_bookings": bookings,
    })
    _set_no_cache_headers(response)
    return response


@require_POST
def cancel_my_booking(request):
    """Отмена записи клиентом (через сессию)."""
    if not request.session.get("client_bookings"):
        messages.error(request, "Сессия истекла. Введите номер телефона снова.")
        return redirect("my_booking")

    try:
        booking_id = int(request.POST.get("booking_id", 0))
    except (ValueError, TypeError):
        messages.error(request, "Некорректный запрос.")
        return redirect("my_booking")

    booking = _get_session_booking_by_id(request, booking_id)
    if not booking:
        messages.error(request, "Ошибка безопасности. Попробуйте снова.")
        return redirect("my_booking")

    # Сохраняем дату/время до обнуления слота
    booking.cache_slot_info()
    slot_date_obj = booking.slot.date if booking.slot else None
    slot_date = booking.slot_date.strftime("%d.%m.%Y") if booking.slot_date else "—"
    slot_time = booking.slot_time_str or "—"

    # Освобождаем слот
    if booking.slot:
        booking.slot.is_available = True
        booking.slot.save(update_fields=["is_available"])

    # Обнуляем FK, ставим статус cancelled — данные в БД остаются навсегда
    booking.slot   = None
    booking.status = Booking.STATUS_CANCELLED
    booking.save(update_fields=["slot", "status", "slot_date", "slot_time_str"])
    request.session.pop("client_bookings", None)

    # Клиентское действие — уведомляем владельца
    try:
        notify_client_action(booking, "cancelled")
    except Exception:
        pass

    if slot_date_obj:
        try:
            _recompute_day_availability(slot_date_obj)
        except Exception:
            logger.exception("_recompute_day_availability после cancel_my_booking")

    request.session["mybooking_result"] = {
        "action": "cancelled",
        "title": "Запись отменена",
        "message": f"Занятие {slot_date} в {slot_time} успешно отменено.",
    }
    return redirect("my_booking")


def reschedule_my_booking(request):
    """
    GET: показывает календарь для выбора нового слота.
    POST: сохраняет перенос.
    """
    if not request.session.get("client_bookings"):
        messages.error(request, "Сессия истекла. Введите номер телефона снова.")
        return redirect("my_booking")

    try:
        booking_id = int(
            request.GET.get("booking_id") or request.POST.get("booking_id") or 0
        )
    except (ValueError, TypeError):
        messages.error(request, "Некорректный запрос.")
        return redirect("my_booking")

    logger.info(f"reschedule_my_booking: booking_id={booking_id}, method={request.method}")

    booking = _get_session_booking_by_id(request, booking_id)
    if not booking:
        logger.warning(f"reschedule_my_booking: booking #{booking_id} не найдена в сессии")
        messages.error(request, "Ошибка безопасности. Попробуйте снова.")
        return redirect("my_booking")

    if request.method == "POST":
        slot_id = request.POST.get("slot_id")
        if not slot_id:
            messages.error(request, "Выберите новое время.")
            return render(request, "core/reschedule.html", {"booking": booking})

        try:
            new_slot = TimeSlot.objects.get(pk=int(slot_id), is_available=True)
        except (TimeSlot.DoesNotExist, ValueError):
            messages.error(request, "Выбранный слот недоступен.")
            return render(request, "core/reschedule.html", {"booking": booking})

        if new_slot.is_booked:
            messages.error(request, "Этот слот уже занят.")
            return render(request, "core/reschedule.html", {"booking": booking})

        old_slot_date = booking.slot.date if booking.slot else None
        old_date  = booking.slot.date.strftime("%d.%m.%Y")
        old_time  = booking.slot.get_time_range()
        new_date  = new_slot.date.strftime("%d.%m.%Y")
        new_time  = new_slot.get_time_range()

        booking.slot = new_slot
        booking.cache_slot_info()
        booking.save(update_fields=["slot", "slot_date", "slot_time_str"])
        request.session.pop("client_bookings", None)

        # Клиентское действие — уведомляем владельца
        try:
            notify_client_action(booking, "rescheduled")
        except Exception:
            pass

        try:
            if old_slot_date:
                _recompute_day_availability(old_slot_date)
            _recompute_day_availability(new_slot.date)
        except Exception:
            logger.exception("_recompute_day_availability после reschedule_my_booking")

        request.session["mybooking_result"] = {
            "action": "rescheduled",
            "title": "Занятие перенесено",
            "message": f"С {old_date} {old_time} → {new_date} {new_time}.",
        }
        return redirect("my_booking")

    # GET запрос — РАЗБЛОКИРУЕМ СЛОТЫ В БД для этой записи
    if booking.slot:
        logger.info(f"Разблокировка слотов для записи #{booking.pk}, дата {booking.slot.date}")
        try:
            _recompute_day_availability(booking.slot.date, exclude_booking_id=booking.pk)
        except Exception:
            logger.exception("_recompute_day_availability при открытии reschedule")

    return render(request, "core/reschedule.html", {"booking": booking})


def _get_session_bookings(request):
    """Вспомогательная: возвращает все записи из сессии (список)."""
    session_data = request.session.get("client_bookings")
    if not session_data:
        return []
    phone = session_data.get("phone", "")
    result = []
    for entry in session_data.get("entries", []):
        bid = entry.get("booking_id")
        if not bid:
            continue
        expected = _make_booking_token(bid, phone)
        if entry.get("token") != expected:
            continue
        try:
            result.append(Booking.objects.select_related("slot").get(pk=bid))
        except Booking.DoesNotExist:
            pass
    if not result:
        request.session.pop("client_bookings", None)
    return result


def _get_session_booking_by_id(request, booking_id):
    """Вспомогательная: возвращает конкретную запись из сессии по ID."""
    session_data = request.session.get("client_bookings")
    if not session_data:
        return None
    phone = session_data.get("phone", "")
    for entry in session_data.get("entries", []):
        if entry.get("booking_id") == booking_id:
            expected = _make_booking_token(booking_id, phone)
            if entry.get("token") != expected:
                return None
            try:
                return Booking.objects.select_related("slot").get(pk=booking_id)
            except Booking.DoesNotExist:
                return None
    return None


def _make_booking_token(booking_id, phone):
    """Генерирует токен для верификации клиента без пароля."""
    from django.conf import settings
    raw = f"{booking_id}:{phone}:{settings.SECRET_KEY[:16]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def _recompute_day_availability(target_date, exclude_booking_id=None):
    """
    Пересчитывает доступность слотов дня после любого изменения записи.
    Если запись стоит на T, блокируются слоты в окне (T−90мин, T) и (T, T+90мин).
    Граничные значения не блокируются — т.е. слот ровно за 1:30 до/после остаётся открытым.

    exclude_booking_id: ID записи, которую нужно игнорировать при расчёте блокировок.
                        Используется при переносе, чтобы старая позиция не блокировала соседние слоты.
    """
    logger.info(f"_recompute_day_availability: дата={target_date}, exclude_booking_id={exclude_booking_id}")

    slots = list(TimeSlot.objects.filter(date=target_date).prefetch_related("booking"))
    logger.info(f"Всего слотов на {target_date}: {len(slots)}")

    booked_starts = [
        s.start_time.hour * 60 + s.start_time.minute
        for s in slots
        if s.is_booked and (exclude_booking_id is None or s.booking.pk != exclude_booking_id)
    ]
    logger.info(f"Занятые слоты (минуты от полуночи): {booked_starts}")

    to_update = []
    for slot in slots:
        if slot.is_booked or slot.is_manually_closed:
            continue
        sm = slot.start_time.hour * 60 + slot.start_time.minute
        blocked = any(
            (T - BLOCK_RADIUS_MINUTES < sm < T) or (T < sm < T + BLOCK_RADIUS_MINUTES)
            for T in booked_starts
        )
        new_avail = not blocked
        if slot.is_available != new_avail:
            logger.info(f"Слот {slot.start_time} ({sm}мин): было available={slot.is_available}, станет {new_avail}")
            slot.is_available = new_avail
            to_update.append(slot)

    logger.info(f"Слотов к обновлению: {len(to_update)}")
    if to_update:
        TimeSlot.objects.bulk_update(to_update, ["is_available"])
        logger.info(f"bulk_update выполнен для {len(to_update)} слотов")

        # Проверка: читаем из БД что реально сохранилось
        updated_slots = TimeSlot.objects.filter(
            date=target_date,
            pk__in=[s.pk for s in to_update]
        ).values_list('start_time', 'is_available')
        logger.info(f"Проверка БД после update: {list(updated_slots)}")


# ─── Аутентификация ───────────────────────────────────────────────────────────

def owner_login(request):
    """Скрытая страница входа для владельца."""
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("dashboard")
    return render(request, "registration/login.html", {"form": form})


def owner_logout(request):
    """Выход из кабинета."""
    logout(request)
    return redirect("/")


# ─── Авто-завершение прошедших записей ───────────────────────────────────────

def _auto_complete_past_bookings() -> int:
    """
    Автоматически переводит активные записи в статус 'завершено',
    если время слота + BLOCK_RADIUS_MINUTES (1.5ч) уже прошло.
    Например: запись на 10:00-11:30 завершается в 13:00.
    Вызывается при открытии дашборда.
    """
    from datetime import datetime as _dt, timedelta as _td

    now = tz.now()

    bookings = list(
        Booking.objects.filter(
            status=Booking.STATUS_ACTIVE,
            slot__isnull=False,
        ).select_related("slot")
    )

    completed = []
    for booking in bookings:
        slot = booking.slot
        if not slot:
            continue

        # Создаём aware datetime для времени завершения (начало + 1.5ч)
        slot_start_naive = _dt.combine(slot.date, slot.start_time)
        slot_start_aware = tz.make_aware(slot_start_naive)
        completion_dt = slot_start_aware + _td(minutes=BLOCK_RADIUS_MINUTES)

        # Проверяем, прошло ли время завершения
        if completion_dt <= now:
            booking.cache_slot_info()
            booking.status = Booking.STATUS_COMPLETED
            completed.append(booking)
            logger.info(f"Автозавершение записи #{booking.id}: {booking.name}, слот {slot.date} {slot.start_time}")

    if completed:
        Booking.objects.bulk_update(completed, ["status", "slot_date", "slot_time_str"])

    return len(completed)


def _auto_close_past_slots() -> int:
    """
    Автоматически закрывает пустые слоты, которые уже прошли или до которых осталось менее 15 минут.
    Например: слот на 10:00 закрывается в 9:45.
    Вызывается при открытии дашборда.
    """
    from datetime import datetime as _dt, timedelta as _td

    now = tz.now()
    today = now.date()

    # Берём все открытые незанятые слоты на сегодня и вчера
    yesterday = today - _td(days=1)
    slots = list(
        TimeSlot.objects.filter(
            date__gte=yesterday,
            date__lte=today,
            is_available=True,
            booking__isnull=True,  # Только пустые слоты
        )
    )

    to_close = []
    for slot in slots:
        # Используем свойство is_past, которое уже учитывает 15-минутный буфер
        if slot.is_past:
            slot.is_available = False
            to_close.append(slot)

    if to_close:
        TimeSlot.objects.bulk_update(to_close, ["is_available"])
        logger.info(f"Автоматически закрыто {len(to_close)} прошедших слотов")

    return len(to_close)


# ─── Личный кабинет: главная ─────────────────────────────────────────────────

@login_required
def dashboard(request):
    """Главная страница кабинета: 14-дневный сеточный календарь."""
    _auto_complete_past_bookings()
    _auto_close_past_slots()
    today = date.today()
    days_ahead = 30  # Синхронизировано с горизонтом клиента
    schedule_dates = [today + timedelta(days=i) for i in range(days_ahead)]

    all_slots = (
        TimeSlot.objects.filter(date__in=schedule_dates)
        .prefetch_related("booking")
        .order_by("date", "start_time")
    )

    schedule = {}
    for d in schedule_dates:
        schedule[d] = {"free": 0, "booked": 0, "completed": 0, "closed": 0, "slots": []}
    for slot in all_slots:
        day = schedule[slot.date]
        day["slots"].append(slot)
        if slot.is_booked:
            if slot.booking.status == Booking.STATUS_COMPLETED:
                day["completed"] += 1
            else:
                day["booked"] += 1
        elif not slot.is_available:
            day["closed"] += 1
        else:
            day["free"] += 1

    # Только активные будущие записи (отменённые и завершённые не показываем)
    upcoming_bookings = (
        Booking.objects.filter(slot__date__gte=today, status=Booking.STATUS_ACTIVE)
        .select_related("slot")
        .order_by("slot__date", "slot__start_time")[:10]
    )

    # Статистика за последние 30 дней
    thirty_days_ago = today - timedelta(days=30)
    stats_30d = {
        "active":    Booking.objects.filter(status=Booking.STATUS_ACTIVE, slot__date__gte=today).count(),
        "completed": Booking.objects.filter(
            status=Booking.STATUS_COMPLETED, slot_date__gte=thirty_days_ago
        ).count(),
        "cancelled": Booking.objects.filter(
            status=Booking.STATUS_CANCELLED, slot_date__gte=thirty_days_ago
        ).count(),
    }

    context = {
        "schedule":        schedule,
        "schedule_dates":  schedule_dates,
        "today":           today,
        "upcoming_bookings": upcoming_bookings,
        "total_bookings":  Booking.objects.count(),
        "stats_30d":       stats_30d,
    }
    return render(request, "core/dashboard.html", context)


# ─── Управление конкретным днём ───────────────────────────────────────────────

@login_required
def dashboard_day(request, date_str):
    """Страница управления конкретным днём расписания."""
    _auto_complete_past_bookings()
    _auto_close_past_slots()

    try:
        selected_date = date.fromisoformat(date_str)
    except ValueError:
        return redirect("dashboard")

    existing_slots = list(
        TimeSlot.objects.filter(date=selected_date)
        .prefetch_related("booking")
        .order_by("start_time")
    )

    # Показываем все слоты, но фильтруем по статусу записи
    filtered_slots = []
    for slot in existing_slots:
        if not slot.is_booked:
            # Свободный или закрытый слот — показываем
            filtered_slots.append(slot)
        else:
            # Занятый слот — показываем если запись активна или завершена
            if slot.booking.status in [Booking.STATUS_ACTIVE, Booking.STATUS_COMPLETED]:
                filtered_slots.append(slot)
    # Кнопка быстрого добавления отключена только для открытых или занятых слотов.
    # Закрытые/авто-заблокированные слоты НЕ блокируют кнопку — их можно перетогглить.
    active_start = {
        s.start_time.strftime('%H:%M')
        for s in filtered_slots
        if s.is_booked or s.is_available
    }
    quick_times = [
        {"time_str": t.strftime('%H:%M'), "exists": t.strftime('%H:%M') in active_start}
        for t in QUICK_SLOT_TIMES
    ]

    context = {
        "selected_date": selected_date,
        "today": date.today(),
        "slots": filtered_slots,
        "is_past": selected_date < date.today(),
        "prev_date": (selected_date - timedelta(days=1)).isoformat(),
        "next_date": (selected_date + timedelta(days=1)).isoformat(),
        "manual_form": ManualBookingForm(),
        "quick_times": quick_times,
        "date_str": selected_date.isoformat(),
    }
    return render(request, "core/dashboard_day.html", context)


# ─── AJAX: операции со слотами (без перезагрузки страницы) ───────────────────

@login_required
@require_POST
def add_single_slot(request, date_str):
    """
    AJAX: добавляет один слот. Всегда возвращает JSON.
    """
    try:
        selected_date = date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse({"success": False, "error": "Некорректная дата"}, status=400)

    start_str = request.POST.get("start_time", "").strip()
    try:
        h, m = map(int, start_str.split(":"))
        start = time(h, m)
    except (ValueError, AttributeError):
        return JsonResponse({"success": False, "error": "Некорректный формат времени"}, status=400)

    from datetime import datetime as _dt, timedelta as _td
    end_dt = _dt.combine(selected_date, start) + _td(minutes=BLOCK_RADIUS_MINUTES)
    end = end_dt.time()

    slot, created = TimeSlot.objects.get_or_create(
        date=selected_date,
        start_time=start,
        defaults={"end_time": end, "is_available": True},
    )

    if not created and slot.is_booked:
        return JsonResponse({"success": False, "error": "Слот уже занят записью."}, status=409)

    if not created and not slot.is_available:
        # Повторное открытие закрытого/авто-заблокированного слота
        slot.end_time = end
        slot.is_available = True
        slot.is_manually_closed = False
        slot.save(update_fields=["end_time", "is_available", "is_manually_closed"])
        created = True  # для сообщения "Слот добавлен"

    # Пересчёт: новый слот может попасть в буфер существующей записи
    try:
        _recompute_day_availability(selected_date)
    except Exception:
        logger.exception("_recompute_day_availability после add_single_slot")

    slot.refresh_from_db()

    return JsonResponse({
        "success": True,
        "created": created,
        "slot_id": slot.pk,
        "start_time": start.strftime('%H:%M'),
        "time_range": slot.get_time_range(),
        "is_available": slot.is_available,
        "is_manually_closed": slot.is_manually_closed,
        "message": "Слот добавлен" if created else "Слот уже существует",
    })


@login_required
@require_POST
def add_slots(request):
    """Быстрое добавление нескольких слотов (из дашборда, AJAX или форма)."""
    form = AddSlotsForm(request.POST)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if not form.is_valid():
        if is_ajax:
            return JsonResponse({"success": False, "error": "Ошибка в форме"}, status=400)
        messages.error(request, "Ошибка в форме.")
        return redirect("dashboard")

    selected_date = form.cleaned_data["date"]
    times = form.cleaned_data["times"]
    added = 0

    for time_range in times:
        start_str, end_str = time_range.split("-")
        start = time(*map(int, start_str.split(":")))
        end   = time(*map(int, end_str.split(":")))
        _, created = TimeSlot.objects.get_or_create(
            date=selected_date,
            start_time=start,
            defaults={"end_time": end, "is_available": True},
        )
        if created:
            added += 1

    if is_ajax:
        return JsonResponse({
            "success": True,
            "added": added,
            "date": selected_date.strftime("%d.%m.%Y"),
        })

    if added:
        messages.success(request, f"Добавлено {added} слот(ов) на {selected_date.strftime('%d.%m.%Y')}.")
    else:
        messages.info(request, "Все выбранные слоты уже существуют.")
    return redirect("dashboard")


@login_required
@require_POST
def delete_slot(request, slot_id):
    """AJAX: удаляет слот (только незанятый)."""
    slot = get_object_or_404(TimeSlot, pk=slot_id)
    if slot.is_booked:
        return JsonResponse({"success": False, "error": "Нельзя удалить занятый слот."}, status=400)
    slot.delete()
    return JsonResponse({"success": True})


@login_required
@require_POST
def toggle_slot(request, slot_id):
    """AJAX: переключает доступность слота."""
    slot = get_object_or_404(TimeSlot, pk=slot_id)
    if slot.is_booked:
        return JsonResponse({"success": False, "error": "Нельзя закрыть занятый слот."}, status=400)
    if slot.is_past:
        return JsonResponse({"success": False, "error": "Прошедший слот нельзя изменить."}, status=400)
    slot.is_available = not slot.is_available
    # Закрытый вручную — не трогать авто-блокировкой; открытый вручную — отдать системе
    slot.is_manually_closed = not slot.is_available
    slot.save(update_fields=["is_available", "is_manually_closed"])
    return JsonResponse({"success": True, "is_available": slot.is_available})


@login_required
@require_POST
def cancel_booking(request, booking_id):
    """
    AJAX: владелец отменяет запись.
    Запись НЕ удаляется — статус меняется на 'cancelled'.
    Слот освобождается для повторной записи.
    """
    try:
        booking = get_object_or_404(Booking, pk=booking_id)
        name = booking.name

        booking.cache_slot_info()
        slot_date_obj = booking.slot.date if booking.slot else None
        slot_str = f"{booking.slot_date.strftime('%d.%m.%Y')} {booking.slot_time_str}" if booking.slot_date else "—"

        if booking.slot:
            booking.slot.is_available = True
            booking.slot.save(update_fields=["is_available"])

        booking.slot   = None
        booking.status = Booking.STATUS_CANCELLED
        booking.save(update_fields=["slot", "status", "slot_date", "slot_time_str"])

        if slot_date_obj:
            try:
                _recompute_day_availability(slot_date_obj)
            except Exception:
                logger.exception("_recompute_day_availability после cancel_booking")

        return JsonResponse({
            "success": True,
            "message": f"Запись {name} на {slot_str} отменена.",
        })
    except Exception as exc:
        logger.exception("cancel_booking #%s: %s", booking_id, exc)
        return JsonResponse({"success": False, "error": "Внутренняя ошибка сервера."}, status=500)


@login_required
@require_POST
def create_manual_booking(request, slot_id):
    """
    AJAX: владелец создаёт запись вручную (клиент позвонил / написал).
    Возвращает JSON с данными созданной записи.
    """
    slot = get_object_or_404(TimeSlot, pk=slot_id)

    if slot.is_booked:
        return JsonResponse({"success": False, "error": "Этот слот уже занят."}, status=409)
    if not slot.is_available:
        return JsonResponse({"success": False, "error": "Этот слот закрыт."}, status=409)

    form = ManualBookingForm(request.POST)
    if not form.is_valid():
        first_error = next(iter(form.errors.values()))[0]
        return JsonResponse({"success": False, "error": first_error}, status=400)

    cd = form.cleaned_data
    booking = Booking.objects.create(
        slot=slot,
        name=cd["name"],
        phone=cd["phone"],
        comment=cd.get("comment", ""),
        service="",
        slot_date=slot.date,
        slot_time_str=slot.get_time_range(),
    )

    # Создание владельцем — уведомления НЕ отправляем

    try:
        _recompute_day_availability(slot.date)
    except Exception:
        logger.exception("_recompute_day_availability после create_manual_booking")

    return JsonResponse({
        "success": True,
        "booking_id": booking.pk,
        "name": booking.name,
        "phone": booking.phone,
        "comment": booking.comment,
        "time_range": slot.get_time_range(),
        "message": f"Запись для {booking.name} создана.",
    })


@login_required
@require_GET
def booking_detail(request, booking_id):
    """AJAX: возвращает данные записи для модала."""
    try:
        booking = get_object_or_404(Booking, pk=booking_id)
        d = booking.get_display_date
        return JsonResponse({
            "id":         booking.pk,
            "name":       booking.name,
            "phone":      booking.phone,
            "date":       d.strftime("%d.%m.%Y") if d else "—",
            "date_long":  d.strftime("%d %B %Y") if d else "—",
            "time":       booking.get_display_time,
            "comment":    booking.comment,
            "owner_note": booking.owner_note,
            "status":     booking.status,
            "is_past":    (d < date.today()) if d else True,
        })
    except Exception as exc:
        logger.exception("booking_detail #%s: %s", booking_id, exc)
        return JsonResponse({"success": False, "error": "Внутренняя ошибка сервера."}, status=500)


@login_required
@require_POST
def booking_update(request, booking_id):
    """AJAX: обновляет имя, телефон и заметку инструктора."""
    try:
        booking = get_object_or_404(Booking, pk=booking_id)
        from django.core.exceptions import ValidationError as DjangoValidationError
        name  = request.POST.get("name",  "").strip()[:100]
        phone = request.POST.get("phone", "").strip()
        owner_note = request.POST.get("owner_note", "").strip()
        if not name or not phone:
            return JsonResponse({"success": False, "error": "Имя и телефон обязательны"}, status=400)
        try:
            phone = _clean_phone(phone)
        except DjangoValidationError as e:
            return JsonResponse({"success": False, "error": e.message}, status=400)
        booking.name       = name
        booking.phone      = phone
        booking.owner_note = owner_note
        booking.save(update_fields=["name", "phone", "owner_note"])
        return JsonResponse({
            "success":    True,
            "name":       booking.name,
            "phone":      booking.phone,
            "owner_note": booking.owner_note,
        })
    except Exception as exc:
        logger.exception("booking_update #%s: %s", booking_id, exc)
        return JsonResponse({"success": False, "error": "Внутренняя ошибка сервера."}, status=500)


@login_required
@require_POST
def booking_delete(request, booking_id):
    """AJAX: полное удаление записи из БД (освобождает слот)."""
    try:
        booking = get_object_or_404(Booking, pk=booking_id)
        slot_date_obj = booking.slot.date if booking.slot else None
        if booking.slot:
            booking.slot.is_available = True
            booking.slot.save(update_fields=["is_available"])
        booking.delete()
        if slot_date_obj:
            try:
                _recompute_day_availability(slot_date_obj)
            except Exception:
                logger.exception("_recompute_day_availability после booking_delete")
        return JsonResponse({"success": True})
    except Exception as exc:
        logger.exception("booking_delete #%s: %s", booking_id, exc)
        return JsonResponse({"success": False, "error": "Внутренняя ошибка сервера."}, status=500)


@login_required
@require_GET
def dashboard_stats(request):
    """AJAX: текущие счётчики для дашборда (обновляются без перезагрузки)."""
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    return JsonResponse({
        "total":     Booking.objects.count(),
        "active":    Booking.objects.filter(status=Booking.STATUS_ACTIVE, slot__date__gte=today).count(),
        "completed": Booking.objects.filter(status=Booking.STATUS_COMPLETED, slot_date__gte=thirty_days_ago).count(),
        "cancelled": Booking.objects.filter(status=Booking.STATUS_CANCELLED, slot_date__gte=thirty_days_ago).count(),
    })


@login_required
@require_POST
def complete_booking(request, booking_id):
    """AJAX: помечает запись как завершённую."""
    try:
        booking = get_object_or_404(Booking, pk=booking_id)
        booking.cache_slot_info()
        booking.status = Booking.STATUS_COMPLETED
        booking.save(update_fields=["status", "slot_date", "slot_time_str"])
        return JsonResponse({"success": True, "status": "completed"})
    except Exception as exc:
        logger.exception("complete_booking #%s: %s", booking_id, exc)
        return JsonResponse({"success": False, "error": "Внутренняя ошибка сервера."}, status=500)


@login_required
def owner_reschedule(request, booking_id):
    """
    Владелец переносит активную запись или восстанавливает отменённую,
    назначая новый слот через тот же calendar-интерфейс.
    """
    booking = get_object_or_404(
        Booking, pk=booking_id,
        status__in=[Booking.STATUS_ACTIVE, Booking.STATUS_CANCELLED],
    )

    if request.method == "POST":
        slot_id = request.POST.get("slot_id")
        try:
            new_slot = TimeSlot.objects.get(pk=int(slot_id), is_available=True)
        except (TimeSlot.DoesNotExist, ValueError):
            messages.error(request, "Выбранный слот недоступен.")
            return render(request, "core/owner_reschedule.html", {"booking": booking})

        if new_slot.is_booked:
            messages.error(request, "Этот слот уже занят.")
            return render(request, "core/owner_reschedule.html", {"booking": booking})

        # Освобождаем старый слот если был
        old_slot_date = booking.slot.date if booking.slot else None
        if booking.slot:
            booking.slot.is_available = True
            booking.slot.save(update_fields=["is_available"])

        booking.slot = new_slot
        booking.cache_slot_info()
        booking.status = Booking.STATUS_ACTIVE
        booking.save(update_fields=["slot", "status", "slot_date", "slot_time_str"])

        try:
            if old_slot_date:
                _recompute_day_availability(old_slot_date)
            _recompute_day_availability(new_slot.date)
        except Exception:
            logger.exception("_recompute_day_availability после owner_reschedule")

        messages.success(request, f"Запись {booking.name} перенесена на {new_slot}.")
        return redirect("all_bookings")

    # GET запрос — РАЗБЛОКИРУЕМ СЛОТЫ В БД для этой записи
    if booking.slot:
        logger.info(f"Разблокировка слотов для записи #{booking.pk}, дата {booking.slot.date}")
        try:
            _recompute_day_availability(booking.slot.date, exclude_booking_id=booking.pk)
        except Exception:
            logger.exception("_recompute_day_availability при открытии owner_reschedule")

    return render(request, "core/owner_reschedule.html", {"booking": booking})


@login_required
def all_bookings(request):
    """
    Раздел «Все записи» — полный список с поиском
    по имени, телефону, комментарию и дате.
    """
    q = request.GET.get("q", "").strip()
    q_filter = _build_search_filter(q) if q else Q()

    today_date = date.today()
    qs = (
        Booking.objects.filter(q_filter)
        .select_related("slot")
        .order_by("-slot_date", "-slot__start_time")
    )[:200]

    # Помечаем каждую запись флагом is_active_flag для шаблона
    bookings = list(qs)
    for b in bookings:
        d = b.get_display_date
        b.is_active_flag = (
            d is not None
            and d >= today_date
            and b.status == Booking.STATUS_ACTIVE
        )

    context = {
        "bookings": bookings,
        "q": q,
        "total": Booking.objects.count(),
        "today": today_date,
    }
    return render(request, "core/all_bookings.html", context)


@login_required
@require_POST
def add_owner_note(request, booking_id):
    """AJAX: сохраняет заметку инструктора к ученику."""
    booking = get_object_or_404(Booking, pk=booking_id)
    form = OwnerNoteForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"success": False, "error": "Ошибка формы"}, status=400)
    booking.owner_note = form.cleaned_data["note"]
    booking.save(update_fields=["owner_note"])
    return JsonResponse({"success": True, "note": booking.owner_note})


# ─── Вспомогательные функции поиска ──────────────────────────────────────────

def _build_search_filter(q: str) -> "Q":
    """
    Строим Q-фильтр для поиска по имени, телефону, комментарию и дате.
    Поддерживает русские форматы дат: ДД.ММ.ГГГГ, ДД.ММ
    icontains работает без учёта регистра (ILIKE в PostgreSQL).
    """
    import re

    text_filter = (
        Q(name__icontains=q)
        | Q(phone__icontains=q)
        | Q(comment__icontains=q)
        | Q(owner_note__icontains=q)
    )

    # Пытаемся распознать дату формата ДД.ММ.ГГГГ или ДД.ММ
    date_filter = Q()
    m = re.match(r"^(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{4}))?$", q.strip())
    if m:
        try:
            day, month = int(m.group(1)), int(m.group(2))
            year = int(m.group(3)) if m.group(3) else None
            date_filter = Q(slot__date__day=day, slot__date__month=month)
            if year:
                date_filter &= Q(slot__date__year=year)
        except (ValueError, TypeError):
            pass

    return text_filter | date_filter


# ─── История занятий ──────────────────────────────────────────────────────────

@login_required
def booking_history(request):
    """
    История прошедших занятий.
    Поиск по имени ИЛИ телефону (регистронезависимо, один параметр q).
    """
    today = date.today()

    q = request.GET.get("q", "").strip()
    q_filter = _build_search_filter(q) if q else Q()

    # ── Активные: есть слот, дата >= сегодня, статус active
    active_qs = (
        Booking.objects.filter(slot__date__gte=today, status=Booking.STATUS_ACTIVE)
        .filter(q_filter)
        .select_related("slot")
        .order_by("slot__date", "slot__start_time")
    )

    # ── История за 30 дней: completed/cancelled + прошедшие активные
    thirty_days_ago = today - timedelta(days=30)
    date_window = Q(slot_date__gte=thirty_days_ago) | Q(slot__date__gte=thirty_days_ago)
    past_qs = (
        Booking.objects.filter(
            Q(status__in=[Booking.STATUS_COMPLETED, Booking.STATUS_CANCELLED])
            | Q(slot__date__lt=today, status=Booking.STATUS_ACTIVE)
        )
        .filter(date_window)
        .filter(q_filter)
        .select_related("slot")
        .distinct()
        .order_by("-slot_date", "-slot__start_time")
    )

    active_bookings = list(active_qs[:50])
    past_bookings   = list(past_qs[:150])

    context = {
        "active_bookings": active_bookings,
        "past_bookings":   past_bookings,
        "active_count":    len(active_bookings),
        "past_count":      len(past_bookings),
        "total":           len(active_bookings) + len(past_bookings),
        "q":    q,
        "today": today,
    }
    return render(request, "core/booking_history.html", context)


@login_required
@require_GET
def dashboard_month(request):
    """AJAX: слоты на месяц для виджета дашборда."""
    today = date.today()
    try:
        year  = int(request.GET.get("year",  today.year))
        month = int(request.GET.get("month", today.month))
    except (ValueError, TypeError):
        return JsonResponse({"error": "Некорректные параметры"}, status=400)

    slots = TimeSlot.objects.filter(
        date__year=year, date__month=month,
    ).prefetch_related("booking").order_by("date", "start_time")

    result = {}
    for slot in slots:
        d = slot.date.strftime("%Y-%m-%d")
        if d not in result:
            result[d] = []
        result[d].append({
            "id": slot.pk,
            "time": slot.get_time_range(),
            "status": slot.status_class,
            "is_booked": slot.is_booked,
            "booking_name": slot.booking.name if slot.is_booked else None,
        })

    return JsonResponse(result)


# ─── Управление услугами (AJAX) ───────────────────────────────────────────────

@login_required
def services_dashboard(request):
    """Страница управления услугами в личном кабинете."""
    services = Service.objects.order_by("order", "id")
    return render(request, "core/services_dashboard.html", {"services": services})


@login_required
def service_create(request):
    """AJAX POST: создать услугу."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректный JSON"}, status=400)
    service = Service.objects.create(
        emoji=data.get("emoji", "").strip()[:10],
        title=data.get("title", "").strip()[:255],
        description=data.get("description", "").strip(),
        price=data.get("price", "").strip()[:100],
        is_active=bool(data.get("is_active", True)),
        order=int(data.get("order", 0)),
    )
    return JsonResponse({"success": True, "id": service.pk, "service": _service_to_dict(service)})


@login_required
def service_update(request, pk):
    """AJAX POST: обновить услугу."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    service = get_object_or_404(Service, pk=pk)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректный JSON"}, status=400)
    service.emoji       = data.get("emoji", service.emoji).strip()[:10]
    service.title       = data.get("title", service.title).strip()[:255]
    service.description = data.get("description", service.description).strip()
    service.price       = data.get("price", service.price).strip()[:100]
    service.is_active   = bool(data.get("is_active", service.is_active))
    service.order       = int(data.get("order", service.order))
    service.save()
    return JsonResponse({"success": True, "service": _service_to_dict(service)})


@login_required
def service_toggle(request, pk):
    """AJAX POST: переключить активность услуги."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    service = get_object_or_404(Service, pk=pk)
    service.is_active = not service.is_active
    service.save(update_fields=["is_active"])
    return JsonResponse({"success": True, "is_active": service.is_active})


@login_required
def service_delete(request, pk):
    """AJAX POST: удалить услугу."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    service = get_object_or_404(Service, pk=pk)
    service.delete()
    return JsonResponse({"success": True})


@login_required
def service_reorder(request):
    """AJAX POST: сохранить новый порядок услуг.
    Тело: {"order": [id1, id2, id3, ...]}
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректный JSON"}, status=400)
    order = data.get("order", [])
    for idx, service_id in enumerate(order):
        Service.objects.filter(pk=service_id).update(order=idx)
    return JsonResponse({"success": True})


def _service_to_dict(service):
    return {
        "id":          service.pk,
        "emoji":       service.emoji,
        "title":       service.title,
        "description": service.description,
        "price":       service.price,
        "is_active":   service.is_active,
        "order":       service.order,
    }
