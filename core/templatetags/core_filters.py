"""Пользовательские template-фильтры."""
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Получить значение из словаря по ключу: {{ dict|get_item:key }}"""
    return dictionary.get(key, {})
