import requests
from jose import jwt
from django.conf import settings

def get_jwks():
    return requests.get(settings.KEYCLOAK_JWKS_URL).json()


def get_public_key(token):
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")

    jwks = get_jwks()

    for key in jwks["keys"]:
        if key["kid"] == kid:
            return key

    return None


def decode_token(token):
    public_key = get_public_key(token)

    return jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        audience=settings.KEYCLOAK_CLIENT_ID,
        issuer=f"{settings.KEYCLOAK_SERVER_URL}/realms/{settings.KEYCLOAK_REALM}",
    )
    
def get_keycloak_public_key():
    url = "http://localhost:8080/realms/risk-management-system/protocol/openid-connect/certs"
    return requests.get(url).json()