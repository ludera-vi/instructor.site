"""
Команда для автоматической генерации расписания.
Использование: python manage.py generate_slots --days 14
"""
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from core.models import TimeSlot
from core.constants import ALL_DAY_SLOTS as DEFAULT_SLOTS


class Command(BaseCommand):
    help = "Генерирует временные слоты на указанное количество дней вперёд"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=14,
            help="Количество дней для генерации (по умолчанию: 14)",
        )
        parser.add_argument(
            "--skip-weekends",
            action="store_true",
            help="Пропускать выходные (сб, вс)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        skip_weekends = options["skip_weekends"]
        today = date.today()
        created_count = 0
        skipped_count = 0

        for i in range(days):
            current_date = today + timedelta(days=i)

            # Пропускаем выходные, если указан флаг
            if skip_weekends and current_date.weekday() >= 5:
                continue

            for start, end in DEFAULT_SLOTS:
                _, created = TimeSlot.objects.get_or_create(
                    date=current_date,
                    start_time=start,
                    defaults={"end_time": end, "is_available": True},
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Создано: {created_count} слотов. "
                f"Уже существовало: {skipped_count} слотов."
            )
        )
