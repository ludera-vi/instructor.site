# Полная документация сайта ivan-gunichev.ru

## Стек

| Слой | Технология |
|---|---|
| Backend | Django 5.1.4, Python 3.12 |
| БД (продакшн) | PostgreSQL |
| БД (разработка) | SQLite |
| Сервер приложений | Gunicorn (3 воркера) |
| Веб-сервер | Nginx |
| Статика | ManifestStaticFilesStorage (хеши в именах файлов) |
| Почта | Яндекс SMTP → PHP-скрипт (резерв) → Telegram |
| Хостинг | Beget VPS, Ubuntu 22.04 |

---

## Структура файлов проекта

```
/home/django/site/
├── core/                        ← основное приложение
│   ├── models.py                ← модели БД
│   ├── views.py                 ← вся логика страниц и AJAX
│   ├── forms.py                 ← формы (запись, поиск, слоты)
│   ├── emails.py                ← уведомления (SMTP / PHP / Telegram)
│   ├── urls.py                  ← все URL-маршруты
│   └── constants.py             ← BLOCK_RADIUS_MINUTES, QUICK_SLOT_TIMES
├── driving_instructor/
│   ├── settings.py              ← конфигурация Django
│   ├── urls.py                  ← корневой роутер (admin + core)
│   └── wsgi.py
├── templates/
│   ├── base.html                ← базовый шаблон (шапка, подвал, JS, CSS)
│   └── core/
│       ├── index.html           ← главная страница
│       ├── booking.html         ← страница записи
│       ├── booking_success.html ← подтверждение записи
│       ├── my_booking.html      ← самообслуживание клиента
│       ├── reschedule.html      ← перенос записи клиентом
│       ├── dashboard.html       ← личный кабинет (месяц)
│       ├── dashboard_day.html   ← личный кабинет (день)
│       ├── all_bookings.html    ← все записи (таблица)
│       ├── booking_history.html ← история завершённых/отменённых
│       ├── owner_reschedule.html← перенос записи владельцем
│       ├── services_dashboard.html ← управление услугами
│       ├── privacy.html         ← политика конфиденциальности
│       └── registration/login.html ← страница входа
├── static/
│   ├── css/style.css            ← единый CSS сайта
│   ├── js/main.js               ← календарь записи, UI-логика
│   └── images/
│       ├── favicon.svg          ← SVG-иконка (руль, #4ecdc4)
│       ├── favicon.ico          ← ICO-иконка (16/32/48px)
│       ├── og-image.jpg         ← OG-превью для соцсетей
│       ├── hello-hero.jpg       ← фото в hero-секции
│       ├── about-hero.jpg       ← фото в секции "Обо мне"
│       └── ivan-middle.jpg      ← фото в секции "На вашем авто"
├── staticfiles/                 ← генерируется collectstatic (в .gitignore)
├── requirements.txt
├── .env                         ← секреты (в .gitignore)
└── ivan-gunichev.conf           ← nginx конфиг (копируется вручную)
```

---

## Модели базы данных

### Service — Услуга

Управляется из личного кабинета. Отображается на главной странице в секции «Услуги».

| Поле | Тип | Описание |
|---|---|---|
| id | int PK | Автоинкремент |
| emoji | CharField(10) | Эмодзи-иконка, например 🚗 |
| title | CharField(255) | Название услуги |
| description | TextField | Описание (необязательно) |
| price | CharField(100) | Цена строкой, например «3 500 ₽» |
| is_active | BooleanField | Показывать на сайте |
| order | IntegerField | Порядок отображения |

Сортировка: по `order`, затем по `id`.

---

### TimeSlot — Временной слот

Инструктор создаёт слоты через личный кабинет. Клиент выбирает слот при записи.

| Поле | Тип | Описание |
|---|---|---|
| id | int PK | Автоинкремент |
| date | DateField | Дата занятия |
| start_time | TimeField | Начало занятия |
| end_time | TimeField | Конец занятия |
| is_available | BooleanField | Доступен для записи (default: True) |
| is_manually_closed | BooleanField | Закрыт вручную инструктором |
| created_at | DateTimeField | Дата создания (auto) |

Ограничение: `unique_together = [date, start_time]` — нельзя два слота в одно время.

Сортировка: по `date`, `start_time`.

**Вычисляемые свойства:**

- `is_booked` → True если на слот есть запись (`hasattr(self, "booking")`)
- `is_past` → True если слот прошёл или до него < 15 минут
- `status_display` → «Свободен» / «Занят» / «Закрыт» / «Прошёл»
- `status_class` → CSS-класс: `free` / `booked` / `closed` / `past`
- `get_time_range()` → строка времени начала, например `«09:00»`

---

### Booking — Запись клиента

| Поле | Тип | Описание |
|---|---|---|
| id | int PK | Автоинкремент |
| slot | FK → TimeSlot | OneToOne, SET_NULL при удалении |
| slot_date | DateField (null) | Кеш даты (заполняется при создании) |
| slot_time_str | CharField(20) | Кеш времени, например «09:00» |
| name | CharField(100) | Имя клиента |
| phone | CharField(20) | Телефон в формате `+7XXXXXXXXXX` |
| comment | TextField | Что хочет отработать клиент |
| service | CharField(20) | Тип занятия (choices) |
| owner_note | TextField | Заметки инструктора (только в ЛК) |
| status | CharField(20) | active / completed / cancelled |
| created_at | DateTimeField | Дата создания (auto) |

**Статусы записи:**
- `active` — активная запись
- `completed` — занятие проведено (отмечает инструктор)
- `cancelled` — запись отменена клиентом или инструктором

**Типы занятий (service):**
- `parking` — 🅿️ Парковка без страха и суеты
- `joy` — ✨ Возвращаю радость вождения
- `city` — 🏙️ Город как знакомый маршрут
- `route` — 🛣️ Мой любимый маршрут
- `antistress` — 🧘 Антистресс-вождение
- `mom` — 👨‍👩‍👧 Мама за рулём
- `night` — 🌙 Ночные покатушки
- `maneuver` — 🔄 Маневрирование без паники
- `other` — Другое

**Зависимость slot → booking:**
Слот и запись связаны OneToOne. При отмене записи: `slot = NULL`, слот освобождается. Денормализованные поля `slot_date` и `slot_time_str` хранят дату и время даже после обнуления слота — нужно для истории.

**Блокировка соседних слотов:**
Константа `BLOCK_RADIUS_MINUTES = 90`. Если клиент записан на 10:00, то слоты 08:30–09:45 и 10:15–11:30 автоматически закрываются — чтобы инструктор не получил два занятия подряд без перерыва.

---

## URL-маршруты

### Публичные страницы

| URL | View | Описание |
|---|---|---|
| `/` | `index` | Главная страница лендинга |
| `/booking/` | `booking_page` | Страница онлайн-записи |
| `/booking/success/` | `booking_success` | Подтверждение записи |
| `/privacy/` | `privacy` | Политика конфиденциальности |
| `/robots.txt` | `robots_txt` | SEO-файл |
| `/sitemap.xml` | `sitemap_xml` | Карта сайта |

### Самообслуживание клиента

| URL | View | Описание |
|---|---|---|
| `/my-booking/` | `my_booking_page` | Страница поиска своей записи |
| `/my-booking/find/` | `find_my_booking` | AJAX: найти запись по телефону |
| `/my-booking/cancel/` | `cancel_my_booking` | Отмена записи клиентом |
| `/my-booking/reschedule/` | `reschedule_my_booking` | Перенос записи клиентом |

### AJAX API (публичный календарь)

| URL | Метод | Описание |
|---|---|---|
| `/api/available-dates/` | GET | Список дат с доступными слотами для календаря |
| `/api/schedule-summary/` | GET | Сводка по месяцу (для отрисовки точек на днях) |
| `/api/slots/` | GET `?date=YYYY-MM-DD` | Слоты на конкретную дату |
| `/api/book/` | POST | Создать запись (имя, телефон, слот, комментарий) |

### Аутентификация

| URL | Описание |
|---|---|
| `/login/` | Вход в личный кабинет (стандартный Django AuthenticationForm) |
| `/logout/` | Выход |

### Личный кабинет (требует авторизации)

| URL | Описание |
|---|---|
| `/dashboard/` | Обзор: текущий месяц, ближайшие записи, статистика |
| `/dashboard/day/<date>/` | Детальный день: слоты, записи, добавление слотов |
| `/dashboard/month/` | Полный месячный вид |
| `/dashboard/all/` | Все активные записи (таблица) |
| `/dashboard/history/` | История: завершённые и отменённые |
| `/dashboard/stats/` | Статистика |

**Операции со слотами:**

| URL | Описание |
|---|---|
| `/dashboard/add-slots/` | Добавить слоты на дату (несколько сразу) |
| `/dashboard/day/<date>/add-slot/` | Добавить один слот с точным временем |
| `/dashboard/delete-slot/<id>/` | Удалить слот |
| `/dashboard/toggle-slot/<id>/` | Открыть / закрыть слот вручную |

**Операции с записями:**

| URL | Описание |
|---|---|
| `/dashboard/manual-booking/<slot_id>/` | Создать запись вручную (клиент позвонил) |
| `/dashboard/cancel-booking/<id>/` | Отменить запись |
| `/dashboard/complete-booking/<id>/` | Отметить занятие проведённым |
| `/dashboard/owner-reschedule/<id>/` | Перенести запись на другой слот |
| `/dashboard/booking/<id>/` | Детали записи |
| `/dashboard/booking/<id>/update/` | Редактировать запись |
| `/dashboard/booking/<id>/delete/` | Удалить запись из БД |
| `/dashboard/owner-note/<id>/` | Сохранить заметку инструктора |

**Управление услугами:**

| URL | Описание |
|---|---|
| `/dashboard/services/` | Список услуг |
| `/dashboard/services/create/` | Создать услугу |
| `/dashboard/services/<id>/update/` | Редактировать |
| `/dashboard/services/<id>/toggle/` | Включить / выключить |
| `/dashboard/services/<id>/delete/` | Удалить |
| `/dashboard/services/reorder/` | Изменить порядок (drag & drop) |

---

## Формы

| Форма | Поля | Используется |
|---|---|---|
| `BookingForm` | name, phone, comment, slot_id, consent | Онлайн-запись клиентом |
| `ManualBookingForm` | name, phone, comment | Ручная запись инструктором |
| `FindBookingForm` | phone | Поиск своей записи клиентом |
| `OwnerNoteForm` | note | Заметка инструктора к записи |
| `AddSlotsForm` | date, times (множественный выбор) | Добавление слотов из ЛК |

**Валидация телефона (`_clean_phone`):**
- Убирает все нецифровые символы
- Если номер начинается с `8` — заменяет на `7`
- Проверяет: 11 цифр, начинается с `7`
- Результат: `+7XXXXXXXXXX`

---

## Система уведомлений

Уведомления отправляются **только при действиях клиента** (запись, перенос, отмена). При действиях инструктора из ЛК — не отправляются.

**Три канала (в порядке приоритета):**

### 1. Django SMTP (Яндекс.Почта) — основной
- Настройки: `EMAIL_HOST`, `EMAIL_PORT=465`, `EMAIL_USE_SSL=True`
- Отправляет HTML-письмо + текстовую версию
- Если SMTP не настроен или упал — переходит на PHP

### 2. PHP-скрипт — резерв
- `MAIL_PHP_URL` — URL скрипта на Beget хостинге
- `MAIL_PHP_TOKEN` — токен для защиты
- HTTP POST с параметрами: token, action, name, phone, date, time, comment

### 3. Telegram — дополнительно (всегда, если настроен)
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
- Отправляет краткое сообщение с именем, телефоном, датой, временем

**Действия:**
- `created` — 📅 Клиент записался
- `rescheduled` — 🔄 Клиент перенёс запись
- `cancelled` — ❌ Клиент отменил запись

---

## Переменные окружения (.env)

| Переменная | Обязательная | Описание |
|---|---|---|
| `SECRET_KEY` | да | Django secret key |
| `DEBUG` | да | True (dev) / False (prod) |
| `ALLOWED_HOSTS` | да | Через запятую: `ivan-gunichev.ru,www.ivan-gunichev.ru` |
| `DB_NAME` | для PostgreSQL | Если не задан — используется SQLite |
| `DB_USER` | для PostgreSQL | Пользователь БД |
| `DB_PASSWORD` | для PostgreSQL | Пароль БД |
| `DB_HOST` | для PostgreSQL | default: 127.0.0.1 |
| `DB_PORT` | для PostgreSQL | default: 5432 |
| `EMAIL_HOST_USER` | для почты | Яндекс-адрес отправителя |
| `EMAIL_HOST_PASSWORD` | для почты | Пароль приложения Яндекс.Почты |
| `OWNER_EMAIL` | для почты | Email получателя уведомлений |
| `MAIL_PHP_URL` | для резерва | URL send-email.php на хостинге |
| `MAIL_PHP_TOKEN` | для резерва | Токен PHP-скрипта |
| `TELEGRAM_BOT_TOKEN` | для Telegram | Токен бота |
| `TELEGRAM_CHAT_ID` | для Telegram | ID чата/канала |
| `CSRF_TRUSTED_ORIGINS` | prod | `https://ivan-gunichev.ru,https://www.ivan-gunichev.ru` |

---

## Статические файлы и кеш

**Схема работы:**
- `DEBUG=True` (разработка) — файлы отдаются напрямую из `static/`, хешей нет
- `DEBUG=False` (продакшн) — `ManifestStaticFilesStorage` добавляет MD5-хеш в имя файла

**Пример:**
```
static/css/style.css
→ после collectstatic →
staticfiles/css/style.580062ff326b.css
```

**Команда на сервере после каждого деплоя:**
```bash
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
```

**Nginx cache-headers:**
- `/static/*` → `Cache-Control: public, max-age=31536000, immutable` (1 год, вечный кеш)
- `/media/*` → `Cache-Control: public, max-age=604800` (7 дней)
- `/*` (HTML) → `Cache-Control: no-cache` (браузер проверяет при каждом заходе)

---

## Фронтенд: календарь записи (main.js)

Класс `BookingCalendar` — единый для `/booking/` и `/my-booking/reschedule/`.

**Инициализация:**
```javascript
new BookingCalendar()                          // страница записи
new BookingCalendar({ isReschedule: true })   // страница переноса
```

**Работа:**
1. При загрузке — GET `/api/schedule-summary/` → получает месяц с пометками «есть слоты» / «нет»
2. При клике на дату — GET `/api/slots/?date=YYYY-MM-DD` → получает слоты дня
3. При выборе слота — записывает `slot_id` в скрытый input, разблокирует кнопку отправки
4. На мобиле — плавный скролл к слотам после выбора даты, плавный скролл к форме после выбора слота

**Скролл на мобиле (`_scrollTo`):**
Учитывает высоту фиксированной шапки (84px). Использует `getBoundingClientRect().top + window.scrollY - 84`.

---

## Главная страница — секции

| Секция | ID | Описание |
|---|---|---|
| Hero | `#hero` | Заголовок, фото, кнопка записи, счётчики (18 лет / 130+ / 5.0) |
| Что вы получите | `#benefits` | 4 карточки с результатами занятий |
| Почему на вашем авто | `#car` | Фото слева, 3 карточки с преимуществами |
| Философия | `#philosophy` | 3 карточки («можно ошибаться» и т.д.) |
| Обо мне | `#about` | Фото, биография, цитата Ивана |
| Услуги | `#services` | Карточки услуг из БД (Service) |
| Отзывы | `#reviews` | Отзывы клиентов (статичные) |
| FAQ | `#faq` | Частые вопросы, аккордеон |
| CTA | `#cta` | Призыв к действию, кнопка записи |

---

## Деплой: что делать после git pull

```bash
cd /home/django/site
source venv/bin/activate

git pull
pip install -r requirements.txt        # если менялись зависимости
python manage.py migrate               # если менялись модели
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
```

## Диагностика

| Проблема | Команда |
|---|---|
| Сайт не открывается | `sudo systemctl status nginx gunicorn` |
| 500 ошибка | `sudo journalctl -u gunicorn -n 50 --no-pager` |
| Статика не обновилась | `python manage.py collectstatic --noinput` |
| Проблемы с БД | Проверь `.env` и `python manage.py migrate` |
| Nginx не стартует | `sudo nginx -t` |
| Обновить SSL | `sudo certbot renew --dry-run` |
