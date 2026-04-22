from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0010_align_mitigation_model_state"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="risk",
            index=models.Index(fields=["status"], name="risk_status_idx"),
        ),
        migrations.AddIndex(
            model_name="risk",
            index=models.Index(fields=["due_date"], name="risk_due_date_idx"),
        ),
        migrations.AddIndex(
            model_name="risk",
            index=models.Index(fields=["created_by_user_id"], name="risk_creator_user_idx"),
        ),
        migrations.AddIndex(
            model_name="risk",
            index=models.Index(fields=["responsible"], name="risk_responsible_idx"),
        ),
        migrations.AddIndex(
            model_name="risk",
            index=models.Index(fields=["responsible_department_id"], name="risk_resp_dept_idx"),
        ),
        migrations.AddIndex(
            model_name="risk",
            index=models.Index(fields=["department", "status"], name="risk_department_status_idx"),
        ),
        migrations.AddIndex(
            model_name="risk",
            index=models.Index(fields=["status", "due_date"], name="risk_status_due_date_idx"),
        ),
        migrations.AddIndex(
            model_name="mitigation",
            index=models.Index(fields=["risk", "status"], name="mitigation_risk_status_idx"),
        ),
        migrations.AddIndex(
            model_name="mitigation",
            index=models.Index(fields=["owner"], name="mitigation_owner_idx"),
        ),
        migrations.AddIndex(
            model_name="mitigation",
            index=models.Index(fields=["status"], name="mitigation_status_idx"),
        ),
        migrations.AddIndex(
            model_name="riskdecition",
            index=models.Index(fields=["risk", "decition_type"], name="decition_risk_type_idx"),
        ),
        migrations.AddIndex(
            model_name="riskdecition",
            index=models.Index(fields=["decided_at"], name="decition_decided_at_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["user", "is_read"], name="notification_user_read_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["created_at"], name="notification_created_at_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["container", "object_id"], name="notification_obj_idx"),
        ),
    ]
