#!/usr/bin/env python3
"""
Telegram-бот для Ивана Гуничева — инструктора по вождению.

Запускается через Django management command:
    python manage.py runbot

Этот файл — обёртка для обратной совместимости.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "driving_instructor.settings")

from django.core.management import execute_from_command_line

if __name__ == "__main__":
    execute_from_command_line([__file__.replace("bot.py", "manage.py"), "runbot"])
