from rest_framework.permissions import SAFE_METHODS, BasePermission


ROLE_ALIASES = {
    "super-admin": {
        "super-admin",
        "super_admin",
        "admin",
        "administrator",
        "erm_admin",
        "rms_admin",
    },
    "risk-dept": {
        "risk-dept",
        "risk_dept",
        "risk-management",
        "risk_management",
        "risk-manager",
        "risk_manager",
        "risk_department",
        "risk",
        "risk_analyst",
        "risk_analysts",
        "risk_control",
        "risk_controller",
    },
    "risk-committee": {
        "risk-committee",
        "risk_committee",
        "committee",
        "committee_member",
        "committee-member",
        "committee_secretary",
    },
    "dept-director": {
        "dept-director",
        "dept_director",
        "department_director",
        "department-director",
        "director",
        "head_of_department",
        "head_of_unit",
    },
}


def normalize_role_token(role):
    return str(role or "").strip().lower().replace(" ", "_")


def get_request_realm_roles(request):
    if not request or not request.auth:
        return set()

    realm_access = request.auth.get("realm_access", {})
    return {
        normalize_role_token(role)
        for role in realm_access.get("roles", [])
        if normalize_role_token(role)
    }


def has_logical_role(request, logical_role):
    normalized_role = normalize_role_token(logical_role)
    known_aliases = ROLE_ALIASES.get(normalized_role, {normalized_role})
    return bool(get_request_realm_roles(request) & known_aliases)


def has_any_logical_role(request, logical_roles):
    return any(has_logical_role(request, role) for role in logical_roles)


class IsKeycloakAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.auth)


class HasRole(BasePermission):
    required_roles = []

    def has_permission(self, request, view):
        if not request.auth:
            return False

        required = getattr(view, "required_roles", self.required_roles)
        return has_any_logical_role(request, required)


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return has_logical_role(request, "super-admin")


class IsRiskDept(BasePermission):
    def has_permission(self, request, view):
        return has_logical_role(request, "risk-dept")


class IsRiskCommittee(BasePermission):
    def has_permission(self, request, view):
        return has_logical_role(request, "risk-committee")


class IsDepartmentDirector(BasePermission):
    def has_permission(self, request, view):
        return has_logical_role(request, "dept-director")


class IsReadOnlyOrSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.auth:
            return False

        if request.method in SAFE_METHODS:
            return True

        return has_logical_role(request, "super-admin")


class IsTopManager(BasePermission):
    def has_permission(self, request, view):
        return has_any_logical_role(request, ["risk-dept", "risk-committee"])


class IsReadOnlyOrTopManager(BasePermission):
    def has_permission(self, request, view):
        if not request.auth:
            return False

        if request.method in SAFE_METHODS:
            return True

        return has_any_logical_role(request, ["risk-dept", "risk-committee"])


class IsOfflineAccess(BasePermission):
    def has_permission(self, request, view):
        if not request.auth:
            return False

        roles = get_request_realm_roles(request)
        return "offline_access" in roles
