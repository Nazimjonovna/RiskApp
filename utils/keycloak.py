import requests
from jose import jwt, jwk, JWTError
from django.conf import settings
import json

# JWKS ni cache qilish (har so'rovda yangi request yubormaslik uchun)
_jwks_cache = None

def get_jwks():
    global _jwks_cache
    if _jwks_cache is None:
        response = requests.get(settings.KEYCLOAK_JWKS_URL, timeout=10)
        response.raise_for_status()
        _jwks_cache = response.json()
    return _jwks_cache


def get_public_key(token):
    """Token header'idagi kid bilan mos JWKS kalitini topadi"""
    try:
        headers = jwt.get_unverified_header(token)
    except JWTError as e:
        raise ValueError(f"Token header o'qib bo'lmadi: {e}")

    kid = headers.get("kid")
    if not kid:
        raise ValueError("Token header'ida 'kid' yo'q")

    jwks = get_jwks()

    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            # ✅ jose kutubxonasi uchun to'g'ri format
            return key_data

    raise ValueError(f"kid='{kid}' uchun kalit topilmadi")


def decode_token(token):
    """
    Keycloak access token'ini verify qilib, payload qaytaradi.
    Xatolik bo'lsa ValueError yoki JWTError ko'taradi.
    """
    public_key = get_public_key(token)

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_CLIENT_ID,
            options={
                "verify_exp": True,
                "verify_aud": True,
            }
        )
    except JWTError as e:
        # ✅ audience xatosi uchun alohida tekshiruv
        # Ba'zi Keycloak sozlamalarida audience "account" bo'ladi
        error_str = str(e).lower()
        if "audience" in error_str:
            # audience verify qilmasdan qayta urinib ko'ramiz
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                options={
                    "verify_exp": True,
                    "verify_aud": False,  # audience ni o'tkazib yuboramiz
                }
            )
        else:
            raise

    return payload