from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class MyOIDCBackend(OIDCAuthenticationBackend):

    def create_user(self, claims):
        return None  # ❌ create yo‘q

    def filter_users_by_claims(self, claims):
        username = claims.get("preferred_username")
        if not username:
            return User.objects.none()

        return User.objects.filter(username=username)