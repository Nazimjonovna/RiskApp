import copy
import logging
from datetime import timezone as dt_timezone

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def _to_text(value):
    return str(value) if value is not None else ''


def _user_group_name(raw_username):
    username = _to_text(raw_username).strip().lower()
    if not username:
        return None
    safe = "".join(char for char in username if char.isalnum() or char in "-_")
    if not safe:
        return None
    return f"user-notifications-{safe}"


def _risk_group_name(risk_id):
    return f"risk-activity-{risk_id}"


def _serialize_activity(activity):
    if activity is None:
        return None

    risk = getattr(activity, "risk", None)
    diff = copy.deepcopy(getattr(activity, "diff", None)) or None
    if isinstance(diff, dict):
        diff = {key: value for key, value in diff.items()}

    return {
        "id": _to_text(activity.id),
        "riskId": risk.id if risk is not None else None,
        "risk": risk.id if risk is not None else None,
        "type": _to_text(activity.type).lower() or None,
        "title": _to_text(activity.title) or None,
        "notes": _to_text(activity.notes) or None,
        "by": _to_text(activity.by) or None,
        "at": activity.at.astimezone(dt_timezone.utc).isoformat() if activity.at else None,
        "diff": diff,
    }


def _serialize_notification(notification):
    if notification is None:
        return None

    container = notification.container if notification.container is not None else ''
    object_id = notification.object_id if notification.object_id is not None else None

    return {
        "id": str(notification.id),
        "title": _to_text(notification.title),
        "message": _to_text(notification.note),
        "targetUser": _to_text(notification.user),
        "container": _to_text(container),
        "objectId": str(object_id) if object_id is not None else None,
        "createdAt": notification.created_at.astimezone(dt_timezone.utc).isoformat(),
    }


def _emit(group, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    try:
        async_to_sync(channel_layer.group_send)(group, payload)
    except Exception:
        logger.exception("Failed to send realtime payload to group=%s", group)


def publish_risk_activity(activity):
    data = _serialize_activity(activity)
    if not data or not data.get("riskId"):
        return

    group_name = _risk_group_name(data["riskId"])
    _emit(
        group_name,
        {
            "type": "risk_activity",
            "payload": {
                **data,
                "riskId": _to_text(data.get("riskId")),
            },
        },
    )


def publish_notification(notification):
    data = _serialize_notification(notification)
    if not data or not data.get("targetUser"):
        return

    group_name = _user_group_name(data["targetUser"])
    if not group_name:
        return

    _emit(
        group_name,
        {
            "type": "notification",
            "payload": data,
        },
    )
