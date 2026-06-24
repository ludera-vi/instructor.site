"""
Telegram-бот для Ивана Гуничева — инструктора по вождению.

Использование: python manage.py runbot

Авто-уведомления:
  07:00 — сводка на сегодня
  19:00 — напоминание на завтра
  12:00 — follow-up: написать клиенту вчерашнего урока
  12:00 — follow-up: написать клиенту урока 3 дня назад
  каждые 5 мин — напоминание за час до урока

Команды:
  /today      — записи на сегодня
  /tomorrow   — записи на завтра
  /week       — записи на 7 дней
  /bookings   — все активные записи
  /id 42      — карточка записи
  /cancel 42  — отменить запись
  /note 42 текст — заметка к записи
  /stats      — статистика
  /find 9991234567 — поиск по телефону
"""
import logging
import functools
from datetime import date, datetime, time, timedelta
from collections import defaultdict
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand
from core.models import Booking
from asgiref.sync import sync_to_async

from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logger = logging.getLogger(__name__)

TZ    = ZoneInfo(settings.TIME_ZONE)
TOKEN = settings.TELEGRAM_BOT_TOKEN
try:
    CHAT = int(settings.TELEGRAM_CHAT_ID)
except (ValueError, TypeError):
    CHAT = None

DAY_RU       = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
DAY_RU_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

_reminded_ids: set = set()


@sync_to_async
def _get_bookings_for_date(d: date) -> list:
    return list(
        Booking.objects
        .filter(status=Booking.STATUS_ACTIVE, slot__date=d)
        .select_related("slot")
        .order_by("slot__start_time")
    )


@sync_to_async
def _get_bookings_week(start: date) -> list:
    return list(
        Booking.objects
        .filter(
            status=Booking.STATUS_ACTIVE,
            slot__date__gte=start,
            slot__date__lt=start + timedelta(days=7),
        )
        .select_related("slot")
        .order_by("slot__date", "slot__start_time")
    )


@sync_to_async
def _get_all_active_bookings() -> list:
    return list(
        Booking.objects
        .filter(status=Booking.STATUS_ACTIVE)
        .select_related("slot")
        .order_by("slot__date", "slot__start_time")
    )


@sync_to_async
def _get_booking_by_id(pk: int) -> Booking:
    return Booking.objects.select_related("slot").get(pk=pk)


@sync_to_async
def _cancel_booking_by_id(pk: int) -> Booking:
    b = Booking.objects.select_related("slot").get(pk=pk)
    if b.slot:
        b.slot.is_available = True
        b.slot.save(update_fields=["is_available"])
    b.cache_slot_info()
    b.slot   = None
    b.status = Booking.STATUS_CANCELLED
    b.save(update_fields=["slot", "status", "slot_date", "slot_time_str"])
    return b


@sync_to_async
def _set_booking_note(pk: int, note: str) -> Booking:
    b = Booking.objects.get(pk=pk)
    b.owner_note = note
    b.save(update_fields=["owner_note"])
    return b


@sync_to_async
def _get_stats() -> dict:
    today       = date.today()
    week_start  = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    return {
        "upcoming": Booking.objects.filter(
            status=Booking.STATUS_ACTIVE,
            slot__date__gte=today,
        ).count(),
        "week": Booking.objects.filter(
            status__in=[Booking.STATUS_ACTIVE, Booking.STATUS_COMPLETED],
            slot_date__gte=week_start,
            slot_date__lte=today,
        ).count(),
        "month": Booking.objects.filter(
            status__in=[Booking.STATUS_ACTIVE, Booking.STATUS_COMPLETED],
            slot_date__gte=month_start,
            slot_date__lte=today,
        ).count(),
        "total_done": Booking.objects.filter(
            status=Booking.STATUS_COMPLETED,
        ).count(),
    }


@sync_to_async
def _find_by_phone(query: str) -> list:
    return list(
        Booking.objects
        .filter(phone__icontains=query)
        .select_related("slot")
        .order_by("-created_at")[:10]
    )


@sync_to_async
def _get_upcoming_in_window(low: time, high: time) -> list:
    return list(
        Booking.objects
        .filter(
            status=Booking.STATUS_ACTIVE,
            slot__date=date.today(),
            slot__start_time__gte=low,
            slot__start_time__lte=high,
        )
        .select_related("slot")
    )


@sync_to_async
def _get_bookings_for_past_date(d: date) -> list:
    return list(
        Booking.objects
        .filter(
            status__in=[Booking.STATUS_ACTIVE, Booking.STATUS_COMPLETED],
            slot_date=d,
        )
        .select_related("slot")
        .order_by("slot__start_time")
    )


def owner_only(func):
    @functools.wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id != CHAT:
            return
        return await func(update, ctx)
    return wrapper


def booking_card(b: Booking, compact: bool = False) -> str:
    d        = b.get_display_date
    date_str = d.strftime("%d.%m.%Y") if d else "—"
    time_str = b.get_display_time or "—"
    dow      = DAY_RU[d.weekday()] if d else ""

    if compact:
        line = f"⏰ <b>{time_str}</b>  —  {b.name}   <code>{b.phone}</code>"
        if b.comment:
            short = b.comment[:70] + ("…" if len(b.comment) > 70 else "")
            line += f"\n   💬 <i>{short}</i>"
        return line

    lines = [
        f"<b>📋 Запись #{b.id}</b>",
        f"📅 {dow}, {date_str}   ⏰ {time_str}",
        f"👤 {b.name}",
        f"📞 <code>{b.phone}</code>",
    ]
    if b.comment:
        lines.append(f"💬 {b.comment}")
    if b.owner_note:
        lines.append(f"📝 <i>{b.owner_note}</i>")
    return "\n".join(lines)


def day_digest(bookings: list, header: str, compact: bool = True) -> str:
    if not bookings:
        return f"{header}\n\nЗаписей нет."
    lines = [header, ""]
    for b in bookings:
        lines.append(booking_card(b, compact=compact))
    n = len(bookings)
    lines.append(f"\n<i>Итого: {n} {'запись' if n == 1 else 'записи' if n < 5 else 'записей'}</i>")
    return "\n".join(lines)


def week_digest(bookings: list) -> list[str]:
    if not bookings:
        return ["На ближайшие 7 дней записей нет."]

    by_date: dict = defaultdict(list)
    for b in bookings:
        by_date[b.slot.date].append(b)

    messages, current = [], []
    total = sum(len(v) for v in by_date.values())
    current.append(f"📆 <b>Расписание на 7 дней</b>\n<i>Записей: {total}</i>")

    for d in sorted(by_date):
        dow         = DAY_RU[d.weekday()]
        date_header = f"\n{'─' * 20}\n🗓 <b>{dow}, {d.strftime('%d.%m.%Y')}</b>"
        day_lines   = [date_header]

        for b in by_date[d]:
            t    = b.get_display_time or "—"
            card = [f"\n⏰ <b>{t}</b>", f"👤 {b.name}", f"📞 <code>{b.phone}</code>"]
            if b.comment:
                card.append(f"💬 <i>{b.comment}</i>")
            day_lines.append("\n".join(card))

        block = "\n".join(day_lines)
        if len("\n".join(current)) + len(block) > 3800:
            messages.append("\n".join(current))
            current = [block]
        else:
            current.append(block)

    if current:
        messages.append("\n".join(current))
    return messages


async def cmd_mychatid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Твой chat_id: <code>{update.effective_chat.id}</code>",
        parse_mode=ParseMode.HTML,
    )


@owner_only
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 <b>Привет, Иван!</b>\n\n"
        "<b>Просмотр расписания:</b>\n"
        "/today      — записи на сегодня\n"
        "/tomorrow   — записи на завтра\n"
        "/week       — записи на 7 дней\n"
        "/bookings   — все активные записи\n"
        "/id 42      — карточка записи #42\n\n"
        "<b>Управление:</b>\n"
        "/cancel 42           — отменить запись\n"
        "/note 42 текст  — заметка к записи\n\n"
        "<b>Аналитика:</b>\n"
        "/stats              — статистика уроков\n"
        "/find 9991234567 — поиск клиента\n\n"
        "<i>Авто: 07:00 — сводка, 19:00 — завтра, за час — напоминание\n"
        "12:00 — follow-up вчерашним и 3-дневным клиентам</i>",
        parse_mode=ParseMode.HTML,
    )


@owner_only
async def cmd_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    today    = date.today()
    bookings = await _get_bookings_for_date(today)
    text     = day_digest(bookings, f"📅 <b>Сегодня — {DAY_RU[today.weekday()]}, {today.strftime('%d.%m.%Y')}</b>")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


@owner_only
async def cmd_tomorrow(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tomorrow = date.today() + timedelta(days=1)
    bookings = await _get_bookings_for_date(tomorrow)
    text     = day_digest(bookings, f"📅 <b>Завтра — {DAY_RU[tomorrow.weekday()]}, {tomorrow.strftime('%d.%m.%Y')}</b>")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


@owner_only
async def cmd_week(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    bookings = await _get_bookings_week(date.today())
    for msg in week_digest(bookings):
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


@owner_only
async def cmd_bookings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    bookings = await _get_all_active_bookings()
    if not bookings:
        await update.message.reply_text("Активных записей нет.")
        return
    lines = [f"📋 <b>Все активные записи ({len(bookings)})</b>\n"]
    for b in bookings:
        d   = b.get_display_date
        ds  = d.strftime("%d.%m") if d else "—"
        dow = DAY_RU_SHORT[d.weekday()] if d else ""
        lines.append(
            f"<code>#{b.id}</code>  {ds} {dow}  {b.get_display_time or '—'}"
            f"  —  <b>{b.name}</b>  <code>{b.phone}</code>"
        )
    lines.append("\n<i>/id &lt;номер&gt; — полная карточка</i>")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@owner_only
async def cmd_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Укажи номер записи: /id 42")
        return
    try:
        b = await _get_booking_by_id(int(ctx.args[0]))
        await update.message.reply_text(booking_card(b, compact=False), parse_mode=ParseMode.HTML)
    except (ValueError, Booking.DoesNotExist):
        await update.message.reply_text("Запись не найдена.")


@owner_only
async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Укажи номер: /cancel 42")
        return
    try:
        b = await _cancel_booking_by_id(int(ctx.args[0]))
        d = b.get_display_date
        await update.message.reply_text(
            f"✅ Запись <b>#{b.id}</b> отменена\n"
            f"👤 {b.name}  📅 {d.strftime('%d.%m.%Y') if d else '—'}  ⏰ {b.get_display_time}",
            parse_mode=ParseMode.HTML,
        )
    except (ValueError, Booking.DoesNotExist):
        await update.message.reply_text("Запись не найдена или уже отменена.")


@owner_only
async def cmd_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text("Пример: /note 42 перезвонить перед уроком")
        return
    try:
        pk   = int(ctx.args[0])
        note = " ".join(ctx.args[1:])
        await _set_booking_note(pk, note)
        await update.message.reply_text(f"📝 Заметка сохранена для записи #{pk}.")
    except (ValueError, Booking.DoesNotExist):
        await update.message.reply_text("Запись не найдена.")


@owner_only
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = await _get_stats()
    await update.message.reply_text(
        f"📊 <b>Статистика</b>\n\n"
        f"🔜 Предстоит:          <b>{s['upcoming']}</b> записей\n"
        f"📅 Эта неделя:        <b>{s['week']}</b> уроков\n"
        f"📅 Этот месяц:        <b>{s['month']}</b> уроков\n"
        f"✅ Всего завершено: <b>{s['total_done']}</b>",
        parse_mode=ParseMode.HTML,
    )


@owner_only
async def cmd_find(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Пример: /find 9991234567")
        return
    bookings = await _find_by_phone(ctx.args[0])
    if not bookings:
        await update.message.reply_text("Ничего не найдено.")
        return
    lines = [f"🔍 <b>Результаты поиска ({len(bookings)})</b>\n"]
    for b in bookings:
        d    = b.get_display_date
        ds   = d.strftime("%d.%m.%Y") if d else "—"
        icon = {"active": "🟢", "completed": "☑️", "cancelled": "🔴"}.get(b.status, "❔")
        lines.append(
            f"{icon} <code>#{b.id}</code>  {ds}  {b.get_display_time or '—'}\n"
            f"   👤 {b.name}  📞 <code>{b.phone}</code>"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not CHAT or query.from_user.id != CHAT:
        return

    parts = query.data.split(":", 1)
    if len(parts) != 2:
        return
    action, pk_str = parts

    try:
        pk = int(pk_str)
    except ValueError:
        return

    if action == "ack":
        await query.edit_message_reply_markup(reply_markup=None)

    elif action == "cancel":
        try:
            b = await _cancel_booking_by_id(pk)
            original = query.message.text or ""
            await query.edit_message_text(
                original + f"\n\n<i>❌ Отменено</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=None,
            )
        except Booking.DoesNotExist:
            await query.answer("Запись не найдена или уже отменена.", show_alert=True)


async def job_morning(ctx: ContextTypes.DEFAULT_TYPE):
    today    = date.today()
    bookings = await _get_bookings_for_date(today)
    text     = day_digest(
        bookings,
        f"☀️ <b>Доброе утро, Иван!</b>\n"
        f"<b>Сегодня — {DAY_RU[today.weekday()]}, {today.strftime('%d.%m.%Y')}</b>",
    )
    await ctx.bot.send_message(chat_id=CHAT, text=text, parse_mode=ParseMode.HTML)


async def job_tomorrow_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    tomorrow = date.today() + timedelta(days=1)
    bookings = await _get_bookings_for_date(tomorrow)
    if not bookings:
        return
    text = day_digest(
        bookings,
        f"🔔 <b>Завтра — {DAY_RU[tomorrow.weekday()]}, {tomorrow.strftime('%d.%m.%Y')}</b>",
    )
    await ctx.bot.send_message(chat_id=CHAT, text=text, parse_mode=ParseMode.HTML)


async def job_check_reminders(ctx: ContextTypes.DEFAULT_TYPE):
    """Каждые 5 мин: уведомление за ~1 час до урока."""
    now  = datetime.now(tz=TZ)
    low  = (now + timedelta(minutes=55)).time()
    high = (now + timedelta(minutes=65)).time()

    if low > high:
        return

    bookings = await _get_upcoming_in_window(low, high)
    for b in bookings:
        if b.id in _reminded_ids:
            continue
        _reminded_ids.add(b.id)

        phone_url = "".join(c for c in b.phone if c in "+0123456789")
        keyboard  = InlineKeyboardMarkup([[
            InlineKeyboardButton("📞 Позвонить", url=f"tel:{phone_url}"),
        ]])
        text = (
            f"⏰ <b>Через час урок!</b>\n\n"
            f"👤 <b>{b.name}</b>\n"
            f"📞 <code>{b.phone}</code>\n"
            f"⏱ {b.get_display_time}"
        )
        await ctx.bot.send_message(chat_id=CHAT, text=text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def job_followup_day1(ctx: ContextTypes.DEFAULT_TYPE):
    """12:00 — напоминание об уроке вчерашнего дня."""
    yesterday = date.today() - timedelta(days=1)
    bookings  = await _get_bookings_for_past_date(yesterday)
    if not bookings:
        return
    lines = [
        f"💬 <b>Вчера прошли занятия — стоит написать клиентам!</b>\n"
        f"<i>({yesterday.strftime('%d.%m.%Y')}, {DAY_RU[yesterday.weekday()]})</i>\n"
    ]
    for b in bookings:
        lines.append(
            f"👤 <b>{b.name}</b>  📞 <code>{b.phone}</code>"
            f"  ⏰ {b.get_display_time or '—'}\n"
            f"   → Поинтересуйся, как прошло занятие 😊"
        )
    await ctx.bot.send_message(chat_id=CHAT, text="\n".join(lines), parse_mode=ParseMode.HTML)


async def job_followup_day3(ctx: ContextTypes.DEFAULT_TYPE):
    """12:00 — напоминание об уроке 3 дня назад."""
    three_days_ago = date.today() - timedelta(days=3)
    bookings       = await _get_bookings_for_past_date(three_days_ago)
    if not bookings:
        return
    lines = [
        f"🔔 <b>3 дня назад были занятия — можно узнать об успехах!</b>\n"
        f"<i>({three_days_ago.strftime('%d.%m.%Y')}, {DAY_RU[three_days_ago.weekday()]})</i>\n"
    ]
    for b in bookings:
        lines.append(
            f"👤 <b>{b.name}</b>  📞 <code>{b.phone}</code>"
            f"  ⏰ {b.get_display_time or '—'}\n"
            f"   → Как дела с вождением? Закрепился ли материал? 🚗"
        )
    await ctx.bot.send_message(chat_id=CHAT, text="\n".join(lines), parse_mode=ParseMode.HTML)


async def set_bot_commands(app: Application):
    await app.bot.set_my_commands([
        BotCommand("today",    "Записи на сегодня"),
        BotCommand("tomorrow", "Записи на завтра"),
        BotCommand("week",     "Расписание на 7 дней"),
        BotCommand("bookings", "Все активные записи"),
        BotCommand("id",       "Карточка записи: /id 42"),
        BotCommand("cancel",   "Отменить запись: /cancel 42"),
        BotCommand("note",     "Заметка: /note 42 текст"),
        BotCommand("stats",    "Статистика уроков"),
        BotCommand("find",     "Поиск клиента: /find телефон"),
    ])


class Command(BaseCommand):
    help = "Запускает Telegram-бота для уведомлений и управления записями"

    def handle(self, *args, **options):
        logging.basicConfig(
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            level=logging.INFO,
        )

        if not TOKEN:
            self.stderr.write(self.style.ERROR("TELEGRAM_BOT_TOKEN не задан в .env"))
            return
        if not CHAT:
            self.stderr.write(self.style.ERROR("TELEGRAM_CHAT_ID не задан в .env"))
            return

        app = (
            Application.builder()
            .token(TOKEN)
            .post_init(set_bot_commands)
            .build()
        )

        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(CommandHandler("mychatid",  cmd_mychatid))
        app.add_handler(CommandHandler("start",     cmd_start))
        app.add_handler(CommandHandler("today",     cmd_today))
        app.add_handler(CommandHandler("tomorrow",  cmd_tomorrow))
        app.add_handler(CommandHandler("week",      cmd_week))
        app.add_handler(CommandHandler("bookings",  cmd_bookings))
        app.add_handler(CommandHandler("id",        cmd_id))
        app.add_handler(CommandHandler("cancel",    cmd_cancel))
        app.add_handler(CommandHandler("note",      cmd_note))
        app.add_handler(CommandHandler("stats",     cmd_stats))
        app.add_handler(CommandHandler("find",      cmd_find))

        jq = app.job_queue
        jq.run_daily(job_morning,           time=time(7,  0, tzinfo=TZ))
        jq.run_daily(job_tomorrow_reminder, time=time(19, 0, tzinfo=TZ))
        jq.run_daily(job_followup_day1,     time=time(12, 0, tzinfo=TZ))
        jq.run_daily(job_followup_day3,     time=time(12, 0, tzinfo=TZ))
        jq.run_repeating(job_check_reminders, interval=300, first=10)

        logger.info("Бот запущен")
        app.run_polling(drop_pending_updates=True)
