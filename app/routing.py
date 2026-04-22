from django.urls import re_path

from .consumers import NotificationConsumer, RiskActivityConsumer

websocket_urlpatterns = [
    re_path(r"^app/ws/risk-activity/(?P<risk_id>\d+)/$", RiskActivityConsumer.as_asgi()),
    re_path(r"^ws/risk-activity/(?P<risk_id>\d+)/$", RiskActivityConsumer.as_asgi()),
    re_path(r"^app/ws/notifications/$", NotificationConsumer.as_asgi()),
    re_path(r"^ws/notifications/$", NotificationConsumer.as_asgi()),
]
