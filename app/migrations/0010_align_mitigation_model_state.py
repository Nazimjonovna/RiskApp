from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0009_mitigation_audit_fields"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="mitigation",
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AlterField(
            model_name="mitigation",
            name="status",
            field=models.CharField(
                choices=[
                    ("NOT_STARTED", "Not Started"),
                    ("IN_PROGRESS", "In Progress"),
                    ("PENDING_RISK_REVIEW", "Pending Risk Review"),
                    ("APPROVED", "Approved"),
                ],
                default="NOT_STARTED",
                max_length=20,
            ),
        ),
    ]
