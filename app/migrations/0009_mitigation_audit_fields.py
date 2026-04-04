from django.db import migrations, models


def backfill_mitigation_audit_fields(apps, schema_editor):
    Mitigation = apps.get_model("app", "Mitigation")

    for mitigation in Mitigation.objects.all().order_by("id"):
        created_by = (mitigation.department_director or mitigation.owner or "").strip()
        Mitigation.objects.filter(pk=mitigation.pk).update(
            created_by=created_by,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0008_backfill_business_codes"),
    ]

    operations = [
        migrations.AddField(
            model_name="mitigation",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="mitigation",
            name="completed_by",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="mitigation",
            name="created_by",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.RunPython(backfill_mitigation_audit_fields, migrations.RunPython.noop),
    ]
