from django.db import migrations, models


def set_manually_closed(apps, schema_editor):
    """Старые закрытые слоты без записи → is_manually_closed = True."""
    TimeSlot = apps.get_model('core', 'TimeSlot')
    Booking  = apps.get_model('core', 'Booking')
    booked_slot_ids = set(
        Booking.objects.filter(slot__isnull=False).values_list('slot_id', flat=True)
    )
    TimeSlot.objects.filter(
        is_available=False
    ).exclude(
        id__in=booked_slot_ids
    ).update(is_manually_closed=True)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_add_service_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='timeslot',
            name='is_manually_closed',
            field=models.BooleanField(default=False, verbose_name='Закрыт вручную'),
        ),
        migrations.RunPython(set_manually_closed, migrations.RunPython.noop),
    ]
