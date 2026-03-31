from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.models import User

from utils.keycloak import decode_token


class KeycloakAuthentication(BaseAuthentication):

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return None

        if not auth_header.startswith("Bearer "):
            raise AuthenticationFailed("Invalid token format")

        token = auth_header.split(" ")[1]

        try:
            payload = decode_token(token)
        except Exception as e:
            raise AuthenticationFailed(f"Token error: {str(e)}")

        username = payload.get("preferred_username")

        user, _ = User.objects.get_or_create(username=username)

        return (user, payload)