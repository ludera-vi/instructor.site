# Деплой на Beget VPS — Полная инструкция

> Инструкция написана пошагово для человека без опыта работы с серверами.
> Каждый шаг снабжён комментарием «Что делать если что-то пошло не так».

---

## Что у нас будет в итоге

```
Браузер → Nginx (80/443) → Gunicorn (Django, порт 8000) → PostgreSQL
                               ↓
                         send-email.php (Beget хостинг)
```

---

## ШАГ 0 — Что нужно заранее

- [ ] VPS на Beget (Ubuntu 22.04 — выбирай при заказе)
- [ ] IP-адрес VPS (виден в панели Beget)
- [ ] Домен `ivan-gunichev.ru` должен смотреть на IP VPS (меняется в DNS)
- [ ] SSH-клиент: на Windows — [Putty](https://putty.org/) или **Windows Terminal**,
      на Mac/Linux — встроенный терминал

---

## ШАГ 1 — Подключиться к серверу по SSH

```bash
ssh root@IP_ТВОЕГО_VPS
```

> **Если не подключается:**
> - Проверь, что VPS уже запущен (в панели Beget статус «Работает»)
> - На Windows используй: `ssh root@123.45.67.89` в PowerShell или Putty
> - Пароль вводится вслепую — это нормально, просто набери и нажми Enter

---

## ШАГ 2 — Обновить систему и установить зависимости

```bash
apt update && apt upgrade -y

apt install -y \
    python3 python3-pip python3-venv \
    postgresql postgresql-contrib \
    nginx \
    certbot python3-certbot-nginx \
    git \
    curl \
    ufw
```

> Установка займёт 2–5 минут. Просто жди.
>
> **Если ошибка `E: Could not get lock`:**
> ```bash
> rm /var/lib/dpkg/lock-frontend
> apt update && apt upgrade -y
> ```

---

## ШАГ 3 — Создать пользователя для приложения

Не запускать Django от root — это небезопасно.

```bash
adduser django
# Придумай пароль, остальное можно пропустить (Enter×5)

usermod -aG sudo django
```

Переключись на нового пользователя:

```bash
su - django
```

> После этой команды слева будет `django@...` вместо `root@...`

---

## ШАГ 4 — Настроить базу данных PostgreSQL

```bash
sudo -u postgres psql
```

Внутри консоли PostgreSQL выполни (копируй всё целиком):

```sql
CREATE DATABASE driving_instructor ENCODING 'UTF8';
CREATE USER drivinguser WITH PASSWORD 'ПРИДУМАЙ_НАДЁЖНЫЙ_ПАРОЛЬ';
ALTER ROLE drivinguser SET client_encoding TO 'utf8';
ALTER ROLE drivinguser SET default_transaction_isolation TO 'read committed';
ALTER ROLE drivinguser SET timezone TO 'Europe/Moscow';
GRANT ALL PRIVILEGES ON DATABASE driving_instructor TO drivinguser;
\q
```

> Пароль запомни — он понадобится в `.env` на следующем шаге.
>
> **Если ошибка `role "postgres" does not exist`:**
> ```bash
> sudo systemctl start postgresql
> sudo -u postgres psql
> ```

---

## ШАГ 5 — Загрузить проект на сервер

### 5.1 — Получить GitHub Personal Access Token (нужен один раз)

GitHub не принимает обычный пароль для push — нужен токен.

1. Зайди на https://github.com/settings/tokens
2. Нажми **Generate new token (classic)**
3. Поставь галочку **repo** (полный доступ к репозиториям)
4. Нажми **Generate token**
5. **Скопируй токен сразу** — он показывается только один раз!
   Выглядит примерно так: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxx`

### 5.2 — Запушить проект на GitHub (со своего компьютера)

Репозиторий уже создан и закоммичен. Выполни в терминале на своём компьютере:

```bash
cd /home/vi/IT/public_html/driving_instructor

# Вставь свой токен вместо ТВОЙ_ТОКЕН:
git remote set-url origin https://iagunichev:ТВОЙ_ТОКЕН@github.com/iagunichev/driving-instructor.git

git push -u origin master
```

**Пример с реальным токеном:**
```bash
git remote set-url origin https://iagunichev:ghp_abc123xyz@github.com/iagunichev/driving-instructor.git
git push -u origin master
```

> **Если ошибка `repository not found`** — репозиторий не создан на GitHub.
> Создай его: https://github.com/new → Name: `driving-instructor` → Create repository
> (без галочек README/gitignore — всё уже есть локально)
>
> **Если ошибка `master does not exist`** — ты ещё не делал коммит:
> ```bash
> git add .
> git commit -m "initial deploy"
> git push -u origin master
> ```

### 5.3 — Скачать проект на сервер (на VPS)

```bash
mkdir -p /home/django/site
cd /home/django/site

# Клонируй (токен нужен снова, чтобы сервер мог скачать приватный репозиторий):
git clone https://iagunichev:ТВОЙ_ТОКЕН@github.com/iagunichev/driving-instructor.git .
```

> Точка в конце команды обязательна — клонирует в текущую папку.
>
> **Если ошибка `destination path already exists`:**
> ```bash
> rm -rf /home/django/site/*
> git clone https://iagunichev:ТВОЙ_ТОКЕН@github.com/iagunichev/driving-instructor.git .
> ```

---

## ШАГ 6 — Создать виртуальное окружение и установить пакеты

```bash
cd /home/django/site
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> Должны установиться: Django, gunicorn, psycopg2-binary, python-decouple, Pillow
>
> **Если ошибка `pip: command not found`:**
> ```bash
> apt install python3-pip -y
> ```
>
> **Если ошибка psycopg2:**
> ```bash
> apt install libpq-dev python3-dev -y
> pip install psycopg2-binary
> ```

---

## ШАГ 7 — Создать файл .env на сервере

```bash
nano /home/django/site/.env
```

Вставь содержимое (Ctrl+Shift+V в большинстве терминалов):

```ini
SECRET_KEY=СГЕНЕРИРУЙ_НОВЫЙ_КЛЮЧ
DEBUG=False
ALLOWED_HOSTS=ivan-gunichev.ru,www.ivan-gunichev.ru

DB_NAME=driving_instructor
DB_USER=drivinguser
DB_PASSWORD=ПАРОЛЬ_ИЗ_ШАГА_4
DB_HOST=127.0.0.1
DB_PORT=5432

MAIL_PHP_URL=https://ivan-gunichev.ru/send-email.php
MAIL_PHP_TOKEN=GunichevMail2026xK9p

CSRF_TRUSTED_ORIGINS=https://ivan-gunichev.ru,https://www.ivan-gunichev.ru
```

Сохрани: **Ctrl+O → Enter → Ctrl+X**

**Сгенерировать SECRET_KEY:**
```bash
source venv/bin/activate
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Скопируй вывод и вставь в `.env`.

> **ВАЖНО:** `.env` содержит секреты — никогда не загружай его в Git!

---

## ШАГ 8 — Применить миграции, собрать статику, создать админа

```bash
cd /home/django/site
source venv/bin/activate

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

`createsuperuser` — введи логин и пароль для личного кабинета на сайте.

> **Если ошибка `FATAL: password authentication failed for user "drivinguser"`:**
> Проверь пароль в `.env` — должен совпадать с тем, что задал в ШАГе 4.
>
> **Если ошибка `relation does not exist`:**
> ```bash
> python manage.py migrate --run-syncdb
> ```

---

## ШАГ 9 — Настроить Gunicorn как системный сервис

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

Вставь:

```ini
[Unit]
Description=Gunicorn — Django сайт Иван Гуничев
After=network.target

[Service]
User=django
Group=django
WorkingDirectory=/home/django/site
ExecStart=/home/django/site/venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8000 \
    --access-logfile /home/django/gunicorn-access.log \
    --error-logfile /home/django/gunicorn-error.log \
    driving_instructor.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

Сохрани: **Ctrl+O → Enter → Ctrl+X**

Запусти и включи автозапуск:

```bash
sudo systemctl daemon-reload
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
sudo systemctl status gunicorn
```

Должно быть: `Active: active (running)` зелёным цветом.

> **Если статус `failed`:**
> ```bash
> sudo journalctl -u gunicorn -n 50
> ```
> Посмотри последние 50 строк лога — там будет ошибка.
>
> Часто причина: ошибка в `.env` (лишний пробел, кавычки).

---

## ШАГ 10 — Настроить Nginx

```bash
sudo nano /etc/nginx/sites-available/ivan-gunichev
```

Вставь:

```nginx
server {
    listen 80;
    server_name ivan-gunichev.ru www.ivan-gunichev.ru;

    # Статические файлы — имена содержат MD5-хеш (ManifestStaticFilesStorage),
    # поэтому при изменении файла меняется и имя. Можно кешировать вечно.
    location /static/ {
        alias /home/django/site/staticfiles/;
        expires 365d;
        add_header Cache-Control "public, max-age=31536000, immutable";
        access_log off;
    }

    # Медиафайлы (загружаемые пользователями, без хешей — короткий кеш)
    location /media/ {
        alias /home/django/site/media/;
        expires 7d;
        add_header Cache-Control "public, max-age=604800";
        access_log off;
    }

    # HTML → Gunicorn; браузер каждый раз проверяет актуальность страницы
    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        add_header Cache-Control "no-cache";
    }
}
```

Сохрани: **Ctrl+O → Enter → Ctrl+X**

Активируй и проверь:

```bash
sudo ln -s /etc/nginx/sites-available/ivan-gunichev /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

`nginx -t` должен показать `syntax is ok`.

> **Если ошибка `[emerg] bind() failed`:**
> ```bash
> sudo nginx -t
> # Смотри строку с ошибкой — скорее всего опечатка в конфиге
> ```
>
> **Если порт 80 занят:**
> ```bash
> sudo fuser -k 80/tcp
> sudo systemctl restart nginx
> ```

---

## ШАГ 11 — Настроить DNS (если ещё не сделано)

В панели управления доменом (где куплен домен) измени A-запись:

```
Тип:   A
Хост:  @  (или ivan-gunichev.ru)
Значение: IP_ТВОЕГО_VPS

Тип:   A
Хост:  www
Значение: IP_ТВОЕГО_VPS
```

> DNS обновляется от 5 минут до 48 часов.
> Проверить: https://dnschecker.org — введи ivan-gunichev.ru

---

## ШАГ 12 — Установить SSL-сертификат (HTTPS)

После того как DNS обновился (сайт открывается по http://):

```bash
sudo certbot --nginx -d ivan-gunichev.ru -d www.ivan-gunichev.ru
```

Введи email, согласись с условиями (Y), выбери редирект на HTTPS (2).

Certbot сам обновит Nginx-конфиг.

> **Если ошибка `Connection refused` или `timeout`:**
> - DNS ещё не обновился — подожди и повтори
>
> **Проверить автообновление сертификата:**
> ```bash
> sudo certbot renew --dry-run
> ```

---

## ШАГ 13 — Настроить файрвол

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

---

## ШАГ 14 — Финальная проверка

```bash
# Gunicorn работает?
sudo systemctl status gunicorn

# Nginx работает?
sudo systemctl status nginx

# Django отвечает напрямую?
curl http://127.0.0.1:8000/

# Логи ошибок Gunicorn:
tail -f /home/django/gunicorn-error.log
```

Открой в браузере:
- `https://ivan-gunichev.ru` — главная страница
- `https://ivan-gunichev.ru/dashboard/` — личный кабинет
- `https://ivan-gunichev.ru/booking/` — форма записи

---

## ШАГ 15 — Загрузить send-email.php на Beget хостинг

Это отдельно от VPS! Через FTP или файловый менеджер Beget:
- Загрузить файл: `/home/vi/IT/public_html/send-email.php`
- Куда: `public_html/send-email.php` на Beget хостинге

---

## Как обновлять сайт в будущем

```bash
ssh django@IP_VPS
cd /home/django/site
source venv/bin/activate

git pull

pip install -r requirements.txt        # если менялись зависимости
python manage.py migrate               # если менялись модели

# collectstatic ОБЯЗАТЕЛЕН после любого изменения CSS/JS/изображений.
# ManifestStaticFilesStorage пересчитывает MD5-хеши и обновляет staticfiles.json.
# Старые файлы с хешами остаются рядом — браузеры с кешем получат их сами.
python manage.py collectstatic --noinput

sudo systemctl restart gunicorn
```

---

## Быстрая диагностика проблем

| Проблема | Команда |
|---|---|
| Сайт не открывается | `sudo systemctl status nginx gunicorn` |
| 502 Bad Gateway | `sudo journalctl -u gunicorn -n 30` |
| Статика не грузится | `python manage.py collectstatic` |
| Ошибка БД | Проверь пароль в `.env` и ШАГ 4 |
| Ошибки Django | `tail -f /home/django/gunicorn-error.log` |
| Certbot не работает | DNS ещё не обновился, жди |

---

## Структура файлов на сервере

```
/home/django/
├── site/                   ← проект Django
│   ├── core/
│   ├── driving_instructor/
│   ├── static/             ← исходная статика
│   ├── staticfiles/        ← собранная статика (collectstatic)
│   ├── templates/
│   ├── venv/
│   ├── manage.py
│   ├── requirements.txt
│   └── .env                ← СЕКРЕТЫ (не в Git!)
├── gunicorn-access.log
└── gunicorn-error.log
```
