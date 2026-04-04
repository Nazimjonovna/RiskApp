from django.contrib.auth import get_user_model
from app.models import Notification

User = get_user_model()

def resolve_user(user):
    if not user:
        return None

    if isinstance(user, User):
        return user

    return User.objects.filter(username=user).first()


def get_notification_username(user):
    if not user:
        return None

    if isinstance(user, User):
        return user.username

    return str(user)


def create_notification(user, title, message, obj):
    username = get_notification_username(user)
    if not username or not obj:
        return

    Notification.objects.create(
        user=username,
        title=title,
        note=message,
        container=obj.__class__.__name__,
        object_id=obj.id
    )


def notify_risk_update(old_risk, new_risk):
    """
    Risk update bo‘lganda kimga notification borishini hal qiladi
    """
    changed_fields = []

    for field in [
        "status", "probability", "Impact", "possible_loss",
        "due_date", "last_reviewed_at", "tags",
        "existing_controls_text", "planned_controls_text"
    ]:
        if getattr(old_risk, field) != getattr(new_risk, field):
            changed_fields.append(field)

    if new_risk.responsible:
        create_notification(
            user=new_risk.responsible,
            title="Risk updated",
            message=f"Risk '{new_risk.id}' updated",
            obj=new_risk
        )

    if new_risk.responsible_department_id:
        director = getattr(new_risk.responsible_department_id, "director", None)

        if director and director != new_risk.responsible:
            create_notification(
                user=director,
                title="Risk update (department)",
                message=f"Risk '{new_risk.id}' updated in your department",
                obj=new_risk
            )

    if changed_fields:

        # risk_manager
        if new_risk.risk_manager:
            create_notification(
                user=new_risk.risk_manager,
                title="Risk changed",
                message=f"Fields changed: {', '.join(changed_fields)}",
                obj=new_risk
            )

        # risk_director
        if new_risk.risk_derector:
            create_notification(
                user=new_risk.risk_derector,
                title="Risk changed",
                message=f"Fields changed: {', '.join(changed_fields)}",
                obj=new_risk
            )

        # created_by_user
        if new_risk.created_by_user_id:
            create_notification(
                user=new_risk.created_by_user_id,
                title="Risk changed",
                message=f"Fields changed: {', '.join(changed_fields)}",
                obj=new_risk
            )
            

def notify_mitigation_create(mitigation):
    """
    Mitigation create bo‘lganda faqat owner ga notification
    """
    if mitigation.owner:
        create_notification(
            user=mitigation.owner,
            title="New Mitigation assigned",
            message=f"Mitigation '{mitigation.title}' assigned to you",
            obj=mitigation
        )
        

def notify_mitigation_update(old_mitigation, new_mitigation):
    """
    Mitigation update bo‘lganda status yoki notes o‘zgarsa notify
    """
    changed_fields = []

    if old_mitigation.status != new_mitigation.status:
        changed_fields.append("status")

    if old_mitigation.notes != new_mitigation.notes:
        changed_fields.append("notes")

    if not changed_fields:
        return

    risk = new_mitigation.risk

    if risk.risk_manager:
        create_notification(
            user=risk.risk_manager,
            title="Mitigation updated",
            message=f"Changed: {', '.join(changed_fields)}",
            obj=new_mitigation
        )

    if risk.risk_derector and risk.risk_derector != risk.risk_manager:
        create_notification(
            user=risk.risk_derector,
            title="Mitigation updated",
            message=f"Changed: {', '.join(changed_fields)}",
            obj=new_mitigation
        )
        
def create_notification_chat(user, title, message, obj=None):
    """
    Universal notification creator
    """
    user_obj = resolve_user(user)

    if not user_obj:
        return None

    return Notification.objects.create(
        user=user_obj.username,
        title=title,
        note=message,
        container=obj.__class__.__name__ if obj else "",
        object_id=obj.id if obj else 0
    )
