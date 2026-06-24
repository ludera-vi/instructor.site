"""
Формы для записи, управления расписанием и самообслуживания клиента.
"""
import re
from django import forms
from django.core.exceptions import ValidationError
from .models import Booking, TimeSlot


class BookingForm(forms.Form):
    """Форма онлайн-записи пользователя. Услуга убрана, комментарий обязателен."""

    name = forms.CharField(
        max_length=100,
        label="Имя",
        widget=forms.TextInput(attrs={
            "placeholder": "Ваше имя",
            "autocomplete": "name",
            "class": "form-input",
        }),
    )
    phone = forms.CharField(
        max_length=20,
        label="Телефон",
        widget=forms.TextInput(attrs={
            "placeholder": "+7 (___) ___-__-__",
            "inputmode": "tel",
            "autocomplete": "tel",
            "class": "form-input phone-mask",
            "id": "phone-input",
        }),
    )
    comment = forms.CharField(
        required=True,
        label="Что хотите отработать?",
        widget=forms.Textarea(attrs={
            "placeholder": "Опишите, чего вы хотите достичь на занятии (например: парковка, город, экзамен). Можно добавить комплимент инструктору 😉",
            "rows": 3,
            "class": "form-textarea",
        }),
    )
    slot_id = forms.IntegerField(widget=forms.HiddenInput(), label="")

    consent = forms.BooleanField(
        required=True,
        label="Я согласен(а) на обработку персональных данных",
        error_messages={"required": "Необходимо согласие на обработку персональных данных."},
    )

    def clean_phone(self):
        return _clean_phone(self.cleaned_data["phone"])

    def clean_slot_id(self):
        slot_id = self.cleaned_data["slot_id"]
        try:
            slot = TimeSlot.objects.get(pk=slot_id, is_available=True)
        except TimeSlot.DoesNotExist:
            raise ValidationError("Выбранный слот недоступен. Пожалуйста, выберите другое время.")
        if slot.is_booked:
            raise ValidationError("Этот слот уже занят. Выберите другое время.")
        if slot.is_past:
            raise ValidationError("Нельзя записаться на прошедшее время.")
        return slot_id


class ManualBookingForm(forms.Form):
    """
    Форма для ручного создания записи владельцем
    (клиент позвонил / написал в Telegram).
    """
    name = forms.CharField(
        max_length=100,
        label="Имя клиента",
        widget=forms.TextInput(attrs={
            "placeholder": "Имя",
            "class": "form-input",
            "autocomplete": "off",
        }),
    )
    phone = forms.CharField(
        max_length=20,
        label="Телефон",
        widget=forms.TextInput(attrs={
            "placeholder": "+7 (___) ___-__-__",
            "inputmode": "tel",
            "class": "form-input phone-mask",
            "autocomplete": "off",
        }),
    )
    comment = forms.CharField(
        required=False,
        label="Комментарий",
        widget=forms.Textarea(attrs={
            "placeholder": "Что хочет отработать, особые пожелания...",
            "rows": 2,
            "class": "form-textarea",
        }),
    )

    def clean_phone(self):
        return _clean_phone(self.cleaned_data["phone"])


class FindBookingForm(forms.Form):
    """Форма поиска своей записи клиентом (по номеру телефона)."""

    phone = forms.CharField(
        max_length=20,
        label="Ваш номер телефона",
        widget=forms.TextInput(attrs={
            "placeholder": "+7 (___) ___-__-__",
            "inputmode": "tel",
            "autocomplete": "tel",
            "class": "form-input phone-mask",
            "id": "find-phone-input",
            "autofocus": True,
        }),
    )

    def clean_phone(self):
        return _clean_phone(self.cleaned_data["phone"])


class OwnerNoteForm(forms.Form):
    """Форма для добавления/редактирования заметки инструктора."""

    note = forms.CharField(
        required=False,
        label="Заметка",
        widget=forms.Textarea(attrs={
            "placeholder": "Прогресс ученика, личные наблюдения, план следующего занятия...",
            "rows": 3,
            "class": "form-textarea",
        }),
    )


class AddSlotsForm(forms.Form):
    """Быстрое добавление нескольких слотов (из дашборда)."""

    SLOT_CHOICES = [
        ("06:00-08:00", "06:00 – 08:00"),
        ("08:00-10:00", "08:00 – 10:00"),
        ("10:00-12:00", "10:00 – 12:00"),
        ("12:00-14:00", "12:00 – 14:00"),
        ("14:00-16:00", "14:00 – 16:00"),
        ("16:00-18:00", "16:00 – 18:00"),
        ("18:00-20:00", "18:00 – 20:00"),
        ("19:00-21:00", "19:00 – 21:00"),
    ]

    date = forms.DateField(
        label="Дата",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"}),
    )
    times = forms.MultipleChoiceField(
        choices=SLOT_CHOICES,
        label="Временные слоты",
        widget=forms.CheckboxSelectMultiple(attrs={"class": "slot-checkbox"}),
        required=True,
    )


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _clean_phone(phone: str) -> str:
    """Нормализует и валидирует российский номер телефона."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) != 11 or not digits.startswith("7"):
        raise ValidationError(
            "Введите корректный российский номер телефона (+7 XXX XXX-XX-XX)."
        )
    return f"+7{digits[1:]}"
