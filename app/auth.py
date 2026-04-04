from django.contrib.auth.models import User
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from utils.keycloak import decode_token


class KeycloakAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None
        if not auth_header.startswith("Bearer "):
            raise AuthenticationFailed("Token formati noto'g'ri")

        token = auth_header.split(" ", 1)[1].strip()

        try:
            payload = decode_token(token)
        except Exception as exc:
            raise AuthenticationFailed(f"Token xatolik: {str(exc)}")

        username = payload.get("preferred_username")
        if not username:
            raise AuthenticationFailed("Token'da 'preferred_username' yo'q")

        defaults = {
            "email": payload.get("email", "") or "",
            "first_name": payload.get("given_name", "") or "",
            "last_name": payload.get("family_name", "") or "",
            "is_active": True,
        }

        user, created = User.objects.get_or_create(
            username=username,
            defaults=defaults,
        )

        fields_to_update = []
        for field, value in defaults.items():
            if getattr(user, field) != value:
                setattr(user, field, value)
                fields_to_update.append(field)

        if created:
            user.set_unusable_password()
            fields_to_update.append("password")

        if fields_to_update:
            user.save(update_fields=list(dict.fromkeys(fields_to_update)))

        return (user, payload)
