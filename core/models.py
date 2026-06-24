"""
Модели для системы онлайн-записи к инструктору по вождению.
"""
from django.db import models
from django.utils import timezone


class Service(models.Model):
    """Услуга инструктора — управляется из личного кабинета."""

    emoji       = models.CharField(max_length=10, blank=True, default="", verbose_name="Эмодзи")
    title       = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    price       = models.CharField(max_length=100, verbose_name="Цена (строка)")
    is_active   = models.BooleanField(default=True, verbose_name="Активна")
    order       = models.IntegerField(default=0, verbose_name="Порядок")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"

    def __str__(self):
        return self.title


class TimeSlot(models.Model):
    """Временной слот для занятия."""

    date = models.DateField(verbose_name="Дата")
    start_time = models.TimeField(verbose_name="Начало")
    end_time = models.TimeField(verbose_name="Конец")
    # Флаг доступности — владелец может вручную закрыть слот
    is_available = models.BooleanField(default=True, verbose_name="Доступен для записи")
    # True = закрыт вручную инструктором; False = доступен или авто-заблокирован системой
    is_manually_closed = models.BooleanField(default=False, verbose_name="Закрыт вручную")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    class Meta:
        ordering = ["date", "start_time"]
        unique_together = ["date", "start_time"]
        verbose_name = "Временной слот"
        verbose_name_plural = "Временные слоты"

    def __str__(self):
        return f"{self.date.strftime('%d.%m.%Y')} {self.start_time.strftime('%H:%M')}–{self.end_time.strftime('%H:%M')}"

    @property
    def is_booked(self):
        """Возвращает True, если на этот слот уже есть запись."""
        return hasattr(self, "booking")

    @property
    def is_past(self):
        """
        Возвращает True, если слот уже прошёл или до него осталось менее 15 минут.
        Например: слот на 10:00 закрывается в 9:45.
        """
        from datetime import timedelta, datetime
        now = timezone.now()

        # Создаём naive datetime и делаем его aware
        naive_dt = datetime.combine(self.date, self.start_time)
        slot_datetime = timezone.make_aware(naive_dt)

        # Закрываем слот за 15 минут до начала
        return slot_datetime - timedelta(minutes=15) <= now

    @property
    def status_display(self):
        """Человекочитаемый статус слота."""
        if self.is_past:
            return "Прошёл"
        if self.is_booked:
            return "Занят"
        if not self.is_available:
            return "Закрыт"
        return "Свободен"

    @property
    def status_class(self):
        """CSS-класс для отображения статуса."""
        if self.is_past:
            return "past"
        if self.is_booked:
            return "booked"
        if not self.is_available:
            return "closed"
        return "free"

    def get_time_range(self):
        """Возвращает строку начала слота '08:00'."""
        return self.start_time.strftime('%H:%M')


class Booking(models.Model):
    """Запись пользователя на занятие."""

    # Статус записи: активна / завершена / отменена
    STATUS_ACTIVE    = 'active'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES   = [
        (STATUS_ACTIVE,    'Активна'),
        (STATUS_COMPLETED, 'Завершена'),
        (STATUS_CANCELLED, 'Отменена'),
    ]

    SERVICES = [
        ("parking", "🅿️ Парковка без страха и суеты"),
        ("joy", "✨ Возвращаю радость вождения"),
        ("city", "🏙️ Город как знакомый маршрут"),
        ("route", "🛣️ Мой любимый маршрут (дом — работа — дом)"),
        ("antistress", "🧘 Антистресс-вождение"),
        ("mom", "👨‍👩‍👧 Мама за рулём"),
        ("night", "🌙 Свидание с городом (ночные покатушки)"),
        ("maneuver", "🔄 Маневрирование без паники"),
        ("other", "Другое"),
    ]

    # Слот: nullable — при отмене обнуляется, слот освобождается для повторной записи
    slot = models.OneToOneField(
        TimeSlot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking",
        verbose_name="Слот",
    )
    # Денормализованные поля даты/времени — заполняются при создании и обнулении слота
    slot_date     = models.DateField(null=True, blank=True, verbose_name="Дата занятия (кэш)")
    slot_time_str = models.CharField(max_length=20, blank=True, verbose_name="Время занятия (кэш)")

    name  = models.CharField(max_length=100, verbose_name="Имя")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    comment = models.TextField(blank=True, verbose_name="Комментарий клиента")
    service = models.CharField(
        max_length=20,
        choices=SERVICES,
        blank=True,
        verbose_name="Услуга",
    )
    # Заметки инструктора — видны только владельцу
    owner_note = models.TextField(blank=True, verbose_name="Заметки инструктора")
    # Статус: активна / завершена (устанавливает инструктор)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        verbose_name="Статус",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")

    class Meta:
        verbose_name = "Запись"
        verbose_name_plural = "Записи"
        ordering = ["slot__date", "slot__start_time"]

    def __str__(self):
        date_str = self.slot_date.strftime("%d.%m.%Y") if self.slot_date else "—"
        return f"{self.name} ({self.phone}) — {date_str} {self.slot_time_str}"

    def get_service_display_emoji(self):
        """Возвращает читаемое название услуги."""
        return dict(self.SERVICES).get(self.service, "Не указано")

    # ── Свойства для безопасного доступа к дате/времени (slot может быть null) ──

    @property
    def get_display_date(self):
        """Возвращает дату занятия (из слота или из кэша)."""
        if self.slot:
            return self.slot.date
        return self.slot_date

    @property
    def get_display_time(self):
        """Возвращает диапазон времени занятия (из слота или из кэша)."""
        if self.slot:
            return self.slot.get_time_range()
        return self.slot_time_str or "—"

    def cache_slot_info(self):
        """Сохраняет дату и время слота в денормализованные поля."""
        if self.slot:
            self.slot_date     = self.slot.date
            self.slot_time_str = self.slot.get_time_range()
