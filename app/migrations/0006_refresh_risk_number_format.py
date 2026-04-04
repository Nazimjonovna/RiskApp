from django.db import migrations


def _format_code(value, width):
    if not value:
        return "0" * width
    return f"{int(value):0{width}d}"


def refresh_risk_numbers(apps, schema_editor):
    Risk = apps.get_model("app", "Risk")

    for risk in Risk.objects.all().only("id", "category_id", "department_id", "responsible_department_id_id"):
        department_pk = risk.department_id or risk.responsible_department_id_id
        risk_number = "R-{category}-{department}-{sequence}".format(
            category=_format_code(risk.category_id, 2),
            department=_format_code(department_pk, 2),
            sequence=_format_code(risk.id, 3),
        )
        Risk.objects.filter(pk=risk.pk).update(risk_number=risk_number)


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0005_clear_risk_data"),
    ]

    operations = [
        migrations.RunPython(refresh_risk_numbers, migrations.RunPython.noop),
    ]
