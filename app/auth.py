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
            raise AuthenticationFailed("Token formati noto'g'ri")

        token = auth_header.split(" ", 1)[1].strip()

        try:
            payload = decode_token(token)
        except Exception as e:
            raise AuthenticationFailed(f"Token xatolik: {str(e)}")

        username = payload.get("preferred_username")
        if not username:
            raise AuthenticationFailed("Token'da 'preferred_username' yo'q")

        # ✅ faqat GET — yaratmaymiz
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise AuthenticationFailed(f"'{username}' bazada topilmadi")

        return (user, payload)