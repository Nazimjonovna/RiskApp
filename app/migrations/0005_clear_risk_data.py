from django.core.management.color import no_style
from django.db import migrations


RISK_NOTIFICATION_CONTAINERS = [
    "Risk",
    "Mitigation",
    "RiskDecition",
    "RiskCommittee",
    "RiskActivity",
    "ReplyRiskActivity",
]


def clear_risk_data(apps, schema_editor):
    Risk = apps.get_model("app", "Risk")
    Mitigation = apps.get_model("app", "Mitigation")
    RiskDecition = apps.get_model("app", "RiskDecition")
    RiskCommittee = apps.get_model("app", "RiskCommittee")
    RiskActivity = apps.get_model("app", "RiskActivity")
    RiskActivityRecipient = apps.get_model("app", "RiskActivityRecipient")
    ReplyRiskActivity = apps.get_model("app", "ReplyRiskActivity")
    Notification = apps.get_model("app", "Notification")

    RiskActivityRecipient.objects.all().delete()
    ReplyRiskActivity.objects.all().delete()
    RiskCommittee.objects.all().delete()
    RiskActivity.objects.all().delete()
    RiskDecition.objects.all().delete()
    Mitigation.objects.all().delete()
    Notification.objects.filter(
        container__in=RISK_NOTIFICATION_CONTAINERS,
    ).delete()
    Risk.objects.all().delete()

    connection = schema_editor.connection
    sequence_models = [
        Risk,
        Mitigation,
        RiskDecition,
        RiskCommittee,
        RiskActivity,
        RiskActivityRecipient,
        ReplyRiskActivity,
    ]
    for sql in connection.ops.sequence_reset_sql(no_style(), sequence_models):
        schema_editor.execute(sql)


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0004_department_keycloak_fields"),
    ]

    operations = [
        migrations.RunPython(clear_risk_data, migrations.RunPython.noop),
    ]
