from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0011_add_performance_indexes"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="risk",
            index=models.Index(fields=["updated_at"], name="risk_updated_at_idx"),
        ),
        migrations.AddIndex(
            model_name="mitigation",
            index=models.Index(fields=["updated_at"], name="mitigation_updated_at_idx"),
        ),
    ]
