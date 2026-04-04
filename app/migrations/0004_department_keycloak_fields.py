from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0003_sync_legacy_workflow_schema"),
    ]

    operations = [
        migrations.AddField(
            model_name="department",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="department",
            name="keycloak_group_id",
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="department",
            name="keycloak_path",
            field=models.CharField(blank=True, max_length=500, null=True, unique=True),
        ),
    ]
