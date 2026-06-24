# Telegram-бот: настройка и деплой

## Что умеет бот

| Команда | Описание |
|---|---|
| /today | Записи на сегодня |
| /tomorrow | Записи на завтра |
| /week | Записи на ближайшие 7 дней |
| /bookings | Все активные записи списком |
| /id 42 | Полная карточка записи #42 |
| Авто в 07:00 | Утренняя сводка на сегодня |
| Авто в 09:00 | Напоминание о записях на завтра |

---

## Шаг 1 — Создать бота в Telegram

1. Открой Telegram, найди **@BotFather**
2. Отправь `/newbot`
3. Введи название бота, например: `Иван Гуничев — расписание`
4. Введи username бота, например: `ivangunichev_schedule_bot`
5. BotFather пришлёт **токен** — сохрани его, выглядит так:
   ```
   7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

---

## Шаг 2 — Узнать свой chat_id

1. Найди в Telegram бота **@userinfobot**
2. Отправь ему `/start`
3. Он пришлёт твой **Id** — это и есть chat_id, например: `123456789`

---

## Шаг 3 — Добавить токен и chat_id в .env

На сервере:

```bash
nano /home/django/site/.env
```

Добавь или обнови строки:

```
TELEGRAM_BOT_TOKEN=7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=123456789
```

Сохрани: Ctrl+O → Enter → Ctrl+X

---

## Шаг 4 — Запушить код и обновить сервер

На своём компьютере:

```bash
cd /home/vi/IT/public_html/driving_instructor
git add bot.py requirements.txt telegram_bot.md
git commit -m "add telegram bot"
git push
```

На сервере:

```bash
cd /home/django/site
source venv/bin/activate
git pull
pip install -r requirements.txt
```

Установка займёт ~30 секунд (скачивается python-telegram-bot).

---

## Шаг 5 — Проверить бота вручную

```bash
cd /home/django/site
source venv/bin/activate
python bot.py
```

Открой Telegram, напиши боту `/start` — должен ответить. Напиши `/today`.

Если всё работает — останови: **Ctrl+C**

---

## Шаг 6 — Создать systemd-сервис

```bash
sudo nano /etc/systemd/system/tgbot.service
```

Вставь:

```
[Unit]
Description=Telegram Bot — Иван Гуничев расписание
After=network.target

[Service]
User=django
Group=django
WorkingDirectory=/home/django/site
ExecStart=/home/django/site/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Сохрани: Ctrl+O → Enter → Ctrl+X

Запусти и включи автозапуск:

```bash
sudo systemctl daemon-reload
sudo systemctl start tgbot
sudo systemctl enable tgbot
sudo systemctl status tgbot
```

Должно быть: `Active: active (running)` зелёным.

---

## Диагностика

```bash
# Статус
sudo systemctl status tgbot

# Логи (последние 50 строк)
sudo journalctl -u tgbot -n 50 --no-pager

# Перезапустить
sudo systemctl restart tgbot
```

---

## Обновление бота после изменений в коде

```bash
# На своём компьютере:
git add bot.py
git commit -m "update bot"
git push

# На сервере:
cd /home/django/site
source venv/bin/activate
git pull
sudo systemctl restart tgbot
```

---

## Полный деплой (git pull + всё сразу)

```bash
cd /home/django/site
source venv/bin/activate
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
sudo systemctl restart tgbot
```
