from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification, RiskActivity
from .services.realtime import publish_notification, publish_risk_activity


@receiver(post_save, sender=RiskActivity)
def on_risk_activity_saved(sender, instance, created, **kwargs):  # noqa: ARG001
    if not created:
        return

    transaction.on_commit(lambda: publish_risk_activity(instance))


@receiver(post_save, sender=Notification)
def on_notification_saved(sender, instance, created, **kwargs):  # noqa: ARG001
    if not created:
        return

    transaction.on_commit(lambda: publish_notification(instance))
