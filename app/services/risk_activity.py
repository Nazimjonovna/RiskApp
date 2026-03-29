from app.models import RiskActivity, RiskActivityRecipient
from app.services.notification import create_notification_chat

def get_or_create_risk_activity(risk, actor, action_type="CREATE", notes=""):
    """
    Har bir risk uchun yagona RiskActivity.
    Mavjud bo'lsa — yangilanadi, yo'q bo'lsa — yaratiladi.
    """
    activity, created = RiskActivity.objects.get_or_create(
        risk=risk,
        defaults={
            "type": action_type,
            "title": f"Risk {action_type.lower()}",
            "notes": notes,
            "by": actor,
        }
    )

    if not created:
        activity.type = action_type
        activity.notes = notes
        activity.by = actor
        activity.save()

    return activity


def add_recipients_to_activity(activity, risk, actor):
    recipients = set()

    if risk.owner:
        recipients.add(risk.owner)

    if risk.risk_derector:
        recipients.add(risk.risk_derector)

    for user in recipients:
        RiskActivityRecipient.objects.get_or_create(
            activity=activity,
            user=user,
            defaults={"is_read": False}
        )

        if user != actor:
            create_notification_chat(
                user=user,
                title=f"Risk {activity.type}",
                message=f"{activity.risk.title} was {activity.type.lower()}d",
                obj=activity.risk
            )

    return recipients


def create_risk_activity_and_notify(risk, actor, action_type="CREATE", notes=""):
    activity = get_or_create_risk_activity(
        risk=risk,
        actor=actor,
        action_type=action_type,
        notes=notes
    )

    add_recipients_to_activity(
        activity=activity,
        risk=risk,
        actor=actor
    )

    return activity


def add_user_to_risk_activity(risk, new_user, actor=None):
    activity = RiskActivity.objects.filter(risk=risk).first()
    if not activity:
        return None

    recipient, created = RiskActivityRecipient.objects.get_or_create(
        activity=activity,
        user=new_user,
        defaults={"is_read": False}
    )

    if created and new_user != actor:
        create_notification_chat(
            user=new_user,
            title="You were added to a risk",
            message=f"You have been added to: {risk.title}",
            obj=risk
        )

    return recipient