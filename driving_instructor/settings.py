
from pathlib import Path
from decouple import config, Csv

# Базовая директория проекта
BASE_DIR = Path(__file__).resolve().parent.parent

# ── Безопасность ──────────────────────────────────────────────────────────────
SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-me-in-production")
DEBUG      = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

# ── Приложения ────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "driving_instructor.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "driving_instructor.wsgi.application"

# ── База данных ───────────────────────────────────────────────────────────────
# Если DB_NAME задан в .env — используем PostgreSQL (продакшен).
# Иначе — SQLite (разработка, не требует настройки).
_DB_NAME = config("DB_NAME", default="")

if _DB_NAME:
    # ── PostgreSQL (продакшен) ──
    DATABASES = {
        "default": {
            "ENGINE":   "django.db.backends.postgresql",
            "NAME":     config("DB_NAME"),
            "USER":     config("DB_USER",     default=""),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST":     config("DB_HOST",     default="127.0.0.1"),
            "PORT":     config("DB_PORT",     default="5432"),
            "OPTIONS": {
                "client_encoding": "UTF8",
            },
        }
    }
else:
    # ── SQLite (разработка) ──
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME":   BASE_DIR / "db.sqlite3",
        }
    }

# ── Валидация паролей ─────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Локализация ───────────────────────────────────────────────────────────────
LANGUAGE_CODE = "ru-ru"
TIME_ZONE     = "Europe/Samara"
USE_I18N      = True
USE_TZ        = True

# ── Статические и медиафайлы ──────────────────────────────────────────────────
STATIC_URL        = "/static/"
STATIC_ROOT       = BASE_DIR / "staticfiles"
STATICFILES_DIRS  = [BASE_DIR / "static"]
MEDIA_URL         = "/media/"
MEDIA_ROOT        = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Редиректы ─────────────────────────────────────────────────────────────────
LOGIN_URL          = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

# ── Email (SMTP через Яндекс) ─────────────────────────────────────────────────
# Для работы нужен ПАРОЛЬ ПРИЛОЖЕНИЯ из Яндекс.Почты (не пароль аккаунта).
# Получить: mail.yandex.ru → Настройки → Безопасность → Пароли приложений → Почта
EMAIL_BACKEND       = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST          = config("EMAIL_HOST",          default="smtp.yandex.ru")
EMAIL_PORT          = config("EMAIL_PORT",          default=465, cast=int)
EMAIL_USE_SSL       = config("EMAIL_USE_SSL",       default=True,  cast=bool)
EMAIL_USE_TLS       = config("EMAIL_USE_TLS",       default=False, cast=bool)
EMAIL_HOST_USER     = config("EMAIL_HOST_USER",     default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
OWNER_EMAIL         = config("OWNER_EMAIL",         default="")
DEFAULT_FROM_EMAIL  = config("EMAIL_HOST_USER",     default="")

# Если пароль не задан — письма в консоль (только при DEBUG=True)
if DEBUG and not EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ── Telegram Bot (опционально) ────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = config("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_CHAT_ID   = config("TELEGRAM_CHAT_ID",   default="")

# ── PHP mail-обработчик (интеграция с существующим скриптом на хостинге) ──────
# Уведомления отправляются ТОЛЬКО при действиях клиента (create / reschedule / cancel).
# Для владельца (из дашборда) уведомления не отправляются.
# URL: абсолютный адрес send-email.php или send-email-smtp.php на вашем хостинге.
# Token: должен совпадать с $SECRET_TOKEN внутри PHP-скрипта.
MAIL_PHP_URL   = config("MAIL_PHP_URL",   default="")
MAIL_PHP_TOKEN = config("MAIL_PHP_TOKEN", default="DJANGO_MAIL_TOKEN_REPLACE_ME")

# ── Продакшн-безопасность (применяется только при DEBUG=False) ───────────────
if not DEBUG:
    # Статика с хешами в именах файлов — вечный кеш безопасен, т.к. при
    # изменении файла меняется его имя. Генерируется через collectstatic.
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
        },
    }

    # HTTPS
    SECURE_SSL_REDIRECT            = True
    SECURE_PROXY_SSL_HEADER        = ("HTTP_X_FORWARDED_PROTO", "https")
    # HSTS — 1 год; включать ТОЛЬКО после проверки HTTPS на сервере
    SECURE_HSTS_SECONDS            = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD            = True
    # Cookies
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE    = True
    # Заголовки безопасности
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    # Доверенные origins для CSRF (форма с другого поддомена или CDN)
    CSRF_TRUSTED_ORIGINS = config(
        "CSRF_TRUSTED_ORIGINS",
        default="https://ivan-gunichev.ru,https://www.ivan-gunichev.ru",
        cast=Csv(),
    )

# ── Логирование (вывод в stderr → systemd/journald) ───────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        # Наши логи — INFO и выше видны в journalctl
        "core": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
