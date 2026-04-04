from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0006_refresh_risk_number_format"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="code",
            field=models.CharField(blank=True, max_length=6, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="department",
            name="code",
            field=models.CharField(blank=True, max_length=6, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="risk",
            name="risk_number",
            field=models.CharField(blank=True, max_length=24, unique=True),
        ),
    ]
