# Сайт инструктора по вождению — Иван Гуничев

Современный сайт с системой онлайн-записи, построенный на Django 5.

---

## Стек технологий

- **Backend**: Python 3.11+ / Django 5.1
- **База данных**: SQLite (разработка) / PostgreSQL (продакшн)
- **Frontend**: Vanilla JS + CSS (glassmorphism, mobile-first)
- **Email**: SMTP (Яндекс.Почта)
- **Деплой**: WSGI (Gunicorn + Nginx)

---

## Быстрый старт (локальная разработка)

### 1. Создать и активировать виртуальное окружение

```bash
cd driving_instructor
python3 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
```

### 2. Установить зависимости

```bash
pip install -r requirements.txt
```

### 3. Настроить переменные окружения

```bash
cp .env.example .env
```

Откройте `.env` и заполните:
- `SECRET_KEY` — сгенерируйте командой:
  ```bash
  python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
  ```
- `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` — данные Яндекс.Почты
- `OWNER_EMAIL` — email для получения уведомлений о записях

### 4. Применить миграции

```bash
python manage.py migrate
```

### 5. Создать суперпользователя (владельца)

```bash
python manage.py createsuperuser
```

Введите логин и пароль. Именно эти данные нужны для входа в личный кабинет.

### 6. (Опционально) Сгенерировать тестовые слоты

```bash
# Создаёт слоты на ближайшие 14 дней
python manage.py generate_slots --days 14

# Только рабочие дни
python manage.py generate_slots --days 30 --skip-weekends
```

### 7. Запустить сервер разработки

```bash
python manage.py runserver
```

Сайт доступен по адресу: http://127.0.0.1:8000

---

## Основные URL-адреса

| URL | Описание |
|-----|----------|
| `/` | Главная страница (лендинг) |
| `/booking/` | Страница онлайн-записи с календарём |
| `/booking/success/` | Подтверждение записи |
| `/login/` | Вход в личный кабинет (скрытая ссылка в footer) |
| `/dashboard/` | Личный кабинет владельца (требует авторизации) |
| `/admin/` | Стандартная Django-admin панель |

---

## Структура проекта

```
driving_instructor/
├── driving_instructor/     # Настройки проекта
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                   # Основное приложение
│   ├── models.py           # Модели: TimeSlot, Booking
│   ├── views.py            # Представления
│   ├── urls.py             # URL-маршруты
│   ├── forms.py            # Формы
│   ├── admin.py            # Регистрация в admin
│   ├── emails.py           # Email/Telegram уведомления
│   └── management/commands/
│       └── generate_slots.py   # Команда генерации слотов
├── templates/              # HTML-шаблоны
│   ├── base.html           # Базовый шаблон
│   ├── core/
│   │   ├── index.html      # Главная страница
│   │   ├── booking.html    # Онлайн-запись
│   │   ├── booking_success.html
│   │   └── dashboard.html  # Личный кабинет
│   └── registration/
│       └── login.html      # Страница входа
├── static/
│   ├── css/style.css       # Основные стили
│   ├── js/main.js          # JavaScript
│   └── images/             # Статические изображения
├── .env.example            # Пример конфигурации
├── requirements.txt
└── manage.py
```

---

## Личный кабинет владельца

Вход через скрытую ссылку в футере: **«Служебный доступ»**
URL: `/login/`

### Функции кабинета:
- 📊 Статистика (всего записей, сегодня, предстоящих)
- 📅 Добавление временных слотов (выбор даты + чекбоксы времени)
- 🔒 Открыть/закрыть слот без удаления
- 🗑️ Удаление слота (только незанятые)
- ❌ Отмена записи (слот освобождается)
- 📋 Таблица предстоящих записей с контактами
- 🗓️ Расписание на ближайшие 7 дней

---

## Уведомления

### Email (обязательно)
При каждой новой записи владелец получает письмо с:
- Именем и телефоном ученика
- Датой и временем занятия
- Выбранной услугой
- Комментарием (если есть)

Настройка в `.env`:
```env
EMAIL_HOST=smtp.yandex.ru
EMAIL_PORT=465
EMAIL_USE_SSL=True
EMAIL_HOST_USER=ваш@yandex.ru
EMAIL_HOST_PASSWORD=пароль-приложения
OWNER_EMAIL=получатель@example.com
```

> ⚠️ Для Яндекс.Почты используйте **пароль приложения**, не основной пароль аккаунта.
> Создать: Яндекс ID → Безопасность → Пароли приложений

### Telegram Bot (опционально)
Добавьте в `.env`:
```env
TELEGRAM_BOT_TOKEN=123456:ABC-xxxxx
TELEGRAM_CHAT_ID=ваш_chat_id
```

Создание бота: [@BotFather](https://t.me/BotFather)
Получить chat_id: [@userinfobot](https://t.me/userinfobot)

---

## Деплой на продакшн (Ubuntu + Nginx + Gunicorn)

### 1. Настройте `.env`
```env
DEBUG=False
ALLOWED_HOSTS=ivan-gunichev.ru,www.ivan-gunichev.ru
SECRET_KEY=сгенерированный-ключ
```

### 2. Соберите статику
```bash
python manage.py collectstatic --noinput
```

### 3. Настройте Gunicorn
```bash
pip install gunicorn
gunicorn driving_instructor.wsgi:application --bind 0.0.0.0:8000
```

### 4. Настройте Nginx
```nginx
server {
    listen 80;
    server_name ivan-gunichev.ru www.ivan-gunichev.ru;

    location /static/ {
        alias /path/to/driving_instructor/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Добавление реальных фото

Замените placeholder-изображения в шаблонах:

В `templates/core/index.html` найдите строки с `images.unsplash.com` и замените на:
```html
src="{% static 'images/ivan-hero.jpg' %}"
src="{% static 'images/ivan-about.jpg' %}"
```

Разместите файлы `ivan-hero.jpg` и `ivan-about.jpg` в папке `static/images/`.
    
---

## SEO

Сайт содержит:
- ✅ Оптимизированные title/description для каждой страницы
- ✅ Schema.org JSON-LD (LocalBusiness с рейтингом, офертами услуг)
- ✅ Open Graph мета-теги
- ✅ Canonical URL
- ✅ Robots.txt и Sitemap (нужно добавить в nginx)
- ✅ Скрытые SEO-ключевые слова в visually-hidden блоках
- ✅ Семантическая HTML-разметка (article, section, blockquote)
