from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0012_add_update_timestamps_indexes"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="risk",
            index=models.Index(fields=["department", "updated_at"], name="risk_dept_updated_idx"),
        ),
        migrations.AddIndex(
            model_name="risk",
            index=models.Index(fields=["responsible_department_id", "updated_at"], name="risk_respdept_upd_idx"),
        ),
        migrations.AddIndex(
            model_name="risk",
            index=models.Index(fields=["status", "updated_at"], name="risk_status_updated_idx"),
        ),
        migrations.AddIndex(
            model_name="riskdecition",
            index=models.Index(fields=["risk", "decided_at"], name="decition_risk_decided_idx"),
        ),
        migrations.AddIndex(
            model_name="riskactivity",
            index=models.Index(fields=["risk", "at"], name="riskactivity_risk_at_idx"),
        ),
        migrations.AddIndex(
            model_name="mitigation",
            index=models.Index(fields=["risk", "updated_at"], name="mitigation_risk_updated_idx"),
        ),
    ]
