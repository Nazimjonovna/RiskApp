# app/permissions.py

from rest_framework.permissions import BasePermission


class IsKeycloakAuthenticated(BasePermission):
    """Faqat valid Keycloak token bo'lsa ruxsat beradi"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.auth)


class HasRole(BasePermission):
    """
    Ishlatish:
        permission_classes = [HasRole]
        required_roles = ["Top-manager"]
    """
    required_roles = []

    def has_permission(self, request, view):
        if not request.auth:
            return False

        realm_access = request.auth.get("realm_access", {})
        user_roles = realm_access.get("roles", [])

        required = getattr(view, "required_roles", self.required_roles)

        return any(role in user_roles for role in required)


class IsTopManager(BasePermission):
    def has_permission(self, request, view):
        if not request.auth:
            return False
        roles = request.auth.get("realm_access", {}).get("roles", [])
        return "Top-manager" in roles


class IsOfflineAccess(BasePermission):
    def has_permission(self, request, view):
        if not request.auth:
            return False
        roles = request.auth.get("realm_access", {}).get("roles", [])
        return "offline_access" in roles