"""
Уведомления о бронированиях.

Порядок отправки:
  1. Django SMTP (Яндекс) — основной, если EMAIL_HOST_USER задан в .env
  2. PHP-скрипт (MAIL_PHP_URL) — резерв, если SMTP не настроен
  3. Telegram — дополнительно, если задан TELEGRAM_BOT_TOKEN

Вызывать ТОЛЬКО при действиях клиента. При действиях владельца — is_client_action=False.
"""
import json
import logging
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)

_ACTION_CFG = {
    "created":     {"subject": "📅 Клиент записался",       "heading": "Клиент записался",       "color": "#4ECDC4"},
    "rescheduled": {"subject": "🔄 Клиент перенёс запись",  "heading": "Клиент перенёс запись",  "color": "#F7B731"},
    "cancelled":   {"subject": "❌ Клиент отменил запись",  "heading": "Клиент отменил запись",  "color": "#FF6B6B"},
}
_DEFAULT_CFG = {"subject": "📬 Новая запись", "heading": "Уведомление", "color": "#4ECDC4"}


# ── Публичный API ──────────────────────────────────────────────────────────────

def notify_client_action(booking, action: str, is_client_action: bool = True) -> None:
    """
    Уведомляет владельца о действии клиента.
    action: 'created' | 'rescheduled' | 'cancelled'
    """
    if not is_client_action:
        return

    # В dev-режиме (консольный backend) пропускаем внешние каналы
    if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
        logger.debug("Dev mode: email/PHP уведомление пропущено (запись #%s)", booking.pk)
        _send_telegram_notification(booking, action)
        return

    smtp_ok = _notify_via_smtp(booking, action)
    if not smtp_ok:
        _notify_via_php(booking, action)

    _send_telegram_notification(booking, action)


# ── Вспомогательная функция ────────────────────────────────────────────────────

def _get_booking_info(booking) -> dict:
    d = booking.get_display_date
    return {
        "name":    booking.name,
        "phone":   booking.phone,
        "date":    d.strftime("%d.%m.%Y") if d else "—",
        "time":    booking.get_display_time or "—",
        "comment": booking.comment or "",
    }


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── Канал 1: Django SMTP ───────────────────────────────────────────────────────

def _notify_via_smtp(booking, action: str) -> bool:
    """Отправляет письмо через Django SMTP. Возвращает True при успехе."""
    owner_email = getattr(settings, "OWNER_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "")
    smtp_user   = getattr(settings, "EMAIL_HOST_USER", "")
    smtp_pass   = getattr(settings, "EMAIL_HOST_PASSWORD", "")

    if not owner_email or not smtp_user or not smtp_pass:
        logger.warning(
            "SMTP не настроен (user=%r pass_set=%s owner=%r) — используем PHP",
            smtp_user, bool(smtp_pass), owner_email,
        )
        return False

    cfg  = _ACTION_CFG.get(action, _DEFAULT_CFG)
    info = _get_booking_info(booking)
    color   = cfg["color"]
    heading = cfg["heading"]
    subject = f"{cfg['subject']}: {info['name']}"

    # Текстовая версия
    text = f"{heading.upper()}\n{'─'*36}\n\nИмя:     {info['name']}\nТелефон: {info['phone']}\nДата:    {info['date']}\nВремя:   {info['time']}\n"
    if info["comment"]:
        text += f"\nКомментарий:\n   {info['comment']}\n"
    text += f"\n{'─'*36}\nhttps://ivan-gunichev.ru/dashboard/"

    # Блок комментария для HTML
    comment_block = ""
    if info["comment"]:
        comment_block = f"""
        <tr><td style="padding:0 32px 20px;">
          <div style="background:#f5f5f5;border-left:3px solid {color};border-radius:4px;padding:12px 16px;">
            <p style="margin:0 0 4px;font-size:12px;color:#888;text-transform:uppercase;">Комментарий</p>
            <p style="margin:0;font-size:15px;color:#333;">{_esc(info['comment'])}</p>
          </div>
        </td></tr>"""

    def row(label, val):
        return f"""<tr><td style="padding:8px 0;border-bottom:1px solid #eee;">
          <span style="font-size:12px;color:#888;display:block;">{label}</span>
          <span style="font-size:16px;font-weight:600;color:#1a1a1a;">{val or '—'}</span>
        </td></tr>"""

    html = f"""<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:-apple-system,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5;padding:32px 16px;">
<tr><td align="center">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);">
  <tr><td style="background:{color};padding:24px 32px;text-align:center;">
    <h1 style="margin:0;font-size:20px;font-weight:700;color:#fff;">{heading}</h1>
  </td></tr>
  <tr><td style="padding:24px 32px 8px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      {row('Имя',     _esc(info['name']))}
      {row('Телефон', _esc(info['phone']))}
      {row('Дата',    _esc(info['date']))}
      {row('Время',   _esc(info['time']))}
    </table>
  </td></tr>
  {comment_block}
  <tr><td style="padding:20px 32px 28px;text-align:center;">
    <a href="https://ivan-gunichev.ru/dashboard/"
       style="display:inline-block;padding:12px 28px;background:{color};color:#fff;text-decoration:none;border-radius:8px;font-size:15px;font-weight:600;">
      Открыть личный кабинет
    </a>
  </td></tr>
</table>
</td></tr>
</table>
</body></html>"""

    try:
        msg = EmailMultiAlternatives(subject=subject, body=text, from_email=smtp_user, to=[owner_email])
        msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=False)
        logger.info("SMTP (%s) запись #%s — OK", action, booking.pk)
        return True
    except Exception as exc:
        logger.error("Ошибка SMTP (%s) запись #%s: %s → пробуем PHP", action, booking.pk, exc)
        return False


# ── Канал 2: PHP (резерв) ────────────────────────────────────────────────────

def _notify_via_php(booking, action: str) -> None:
    """HTTP POST к send-email.php (резерв когда SMTP не настроен)."""
    url = getattr(settings, "MAIL_PHP_URL", "")
    if not url:
        logger.warning("MAIL_PHP_URL не задан — уведомление не отправлено")
        return

    token = getattr(settings, "MAIL_PHP_TOKEN", "")
    info  = _get_booking_info(booking)

    try:
        data = urllib.parse.urlencode({
            "token": token, "action": action,
            "name":  info["name"],  "phone":   info["phone"],
            "date":  info["date"],  "time":    info["time"],
            "comment": info["comment"],
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            logger.info("PHP mail (%s) #%s — HTTP %s: %s", action, booking.pk, resp.status, body[:120])
    except Exception as exc:
        logger.error("Ошибка PHP mail (%s) запись #%s: %s", action, booking.pk, exc)


# ── Канал 3: Telegram (опционально) ──────────────────────────────────────────

_DAY_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

_ACTION_ICON = {
    "created":     "🟢",
    "rescheduled": "🔄",
    "cancelled":   "🔴",
}


def _send_telegram_notification(booking, action: str) -> None:
    token   = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID",   "")
    if not token or not chat_id:
        return

    info = _get_booking_info(booking)
    cfg  = _ACTION_CFG.get(action, _DEFAULT_CFG)
    icon = _ACTION_ICON.get(action, "📬")

    try:
        from datetime import datetime
        d = datetime.strptime(info["date"], "%d.%m.%Y").date()
        dow = _DAY_RU[d.weekday()]
        date_line = f"📅 {dow}, {_esc(info['date'])}   ⏰ <b>{_esc(info['time'])}</b>"
    except Exception:
        date_line = f"📅 {_esc(info['date'])}   ⏰ <b>{_esc(info['time'])}</b>"

    lines = [
        f"{icon} <b>{cfg['heading']}</b>",
        "─" * 22,
        f"👤 <b>{_esc(info['name'])}</b>",
        f"📞 <code>{_esc(info['phone'])}</code>",
        date_line,
    ]
    if info["comment"]:
        lines += ["", f"💬 <i>{_esc(info['comment'])}</i>"]
    lines += ["", f"<a href=\"https://ivan-gunichev.ru/dashboard/\">🔗 Открыть кабинет</a>"]
    text = "\n".join(lines)

    reply_markup = None
    if action in ("created", "rescheduled"):
        reply_markup = json.dumps({
            "inline_keyboard": [
                [
                    {"text": "✅ Принято",        "callback_data": f"ack:{booking.pk}"},
                    {"text": "❌ Отменить запись", "callback_data": f"cancel:{booking.pk}"},
                ],
            ]
        })

    try:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        data = urllib.parse.urlencode(payload).encode("utf-8")
        urllib.request.urlopen(
            urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data),
            timeout=5,
        )
        logger.info("Telegram (%s) запись #%s — OK", action, booking.pk)
    except Exception as exc:
        logger.error("Ошибка Telegram (%s) запись #%s: %s", action, booking.pk, exc)
