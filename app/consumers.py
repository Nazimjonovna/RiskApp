from datetime import datetime
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncWebsocketConsumer

from utils.keycloak import decode_token

from .services.realtime import _risk_group_name


def _extract_token(scope):
    query = parse_qs((scope.get("query_string") or b"").decode())
    return (query.get("token") or [None])[0]


def _normalize_username(payload):
    if not isinstance(payload, dict):
        return ""
    return (payload.get("preferred_username") or "").strip().lower()


def _normalize_group_name(value):
    return value.strip().lower() if isinstance(value, str) else ""


async def _send_error(self, message, code=4001):
    try:
        await self.send_json({"eventType": "error", "message": message})
    except Exception:
        return
    await self.close(code=code)


class RiskActivityConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = None
        self.risk_id = self.scope["url_route"].get("kwargs", {}).get("risk_id")

        raw_token = _extract_token(self.scope)
        if not raw_token:
            await _send_error(self, "Authentication token is required")
            return

        try:
            payload = decode_token(raw_token)
            username = _normalize_username(payload)
            if not username:
                raise ValueError("Token does not contain preferred_username")
        except Exception:
            await _send_error(self, "Invalid or expired token")
            return

        self.risk_id = str(self.risk_id or "").strip()
        if not self.risk_id:
            await _send_error(self, "Invalid risk id")
            return

        self.username = username
        self.group_name = _risk_group_name(self.risk_id)

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({
            "eventType": "connected",
            "status": "ok",
            "riskId": self.risk_id,
        })

    async def disconnect(self, code):  # noqa: ARG002
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def risk_activity(self, event):
        payload = event.get("payload") or {}
        payload.setdefault("riskId", self.risk_id)
        await self.send_json({
            "eventType": "risk_activity",
            "data": payload,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = None
        raw_token = _extract_token(self.scope)

        if not raw_token:
            await _send_error(self, "Authentication token is required")
            return

        try:
            payload = decode_token(raw_token)
            username = _normalize_username(payload)
            if not username:
                raise ValueError("Token does not contain preferred_username")
        except Exception:
            await _send_error(self, "Invalid or expired token")
            return

        self.username = username
        self.group_name = f"user-notifications-{_normalize_group_name(self.username)}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({
            "eventType": "connected",
            "status": "ok",
        })

    async def disconnect(self, code):  # noqa: ARG002
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notification(self, event):
        payload = event.get("payload") or {}
        await self.send_json({
            "eventType": "notification",
            "data": payload,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })
