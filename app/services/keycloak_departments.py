import time

import requests
from django.conf import settings

from app.models import Department


_admin_token_cache = {"value": None, "expires_at": 0.0}
_department_sync_cache = {"expires_at": 0.0}


class DepartmentResolutionError(Exception):
    pass


def _normalize_group_path(path):
    cleaned = "/".join(segment for segment in str(path or "").strip().split("/") if segment)
    if not cleaned:
        return ""
    return f"/{cleaned}"


def _group_name_from_path(path):
    normalized = _normalize_group_path(path)
    if not normalized:
        return ""
    return normalized.rsplit("/", 1)[-1]


def _group_display_name(group):
    return (
        str(group.get("description") or "").strip()
        or str(group.get("name") or "").strip()
        or _group_name_from_path(group.get("path"))
    )


def _flatten_groups(groups):
    flat_groups = []
    for group in groups or []:
        path = _normalize_group_path(group.get("path") or group.get("name"))
        flat_groups.append(
            {
                "id": str(group.get("id") or ""),
                "name": group.get("name") or _group_name_from_path(path),
                "description": str(group.get("description") or "").strip(),
                "path": path,
                "sub_group_count": int(group.get("subGroupCount") or len(group.get("subGroups") or [])),
            }
        )
        flat_groups.extend(_flatten_groups(group.get("subGroups") or []))
    return flat_groups


def _admin_api_is_configured():
    has_client_credentials = bool(
        settings.KEYCLOAK_ADMIN_CLIENT_ID and settings.KEYCLOAK_ADMIN_CLIENT_SECRET
    )
    has_user_credentials = bool(
        settings.KEYCLOAK_ADMIN_CLIENT_ID
        and settings.KEYCLOAK_ADMIN_USERNAME
        and settings.KEYCLOAK_ADMIN_PASSWORD
    )
    return has_client_credentials or has_user_credentials


def _get_admin_token():
    if not _admin_api_is_configured():
        raise DepartmentResolutionError(
            "Keycloak Admin API credentials are not configured."
        )

    now = time.time()
    if _admin_token_cache["value"] and _admin_token_cache["expires_at"] > now + 15:
        return _admin_token_cache["value"]

    data = {"client_id": settings.KEYCLOAK_ADMIN_CLIENT_ID}
    if settings.KEYCLOAK_ADMIN_CLIENT_SECRET:
        data.update(
            {
                "grant_type": "client_credentials",
                "client_secret": settings.KEYCLOAK_ADMIN_CLIENT_SECRET,
            }
        )
    else:
        data.update(
            {
                "grant_type": "password",
                "username": settings.KEYCLOAK_ADMIN_USERNAME,
                "password": settings.KEYCLOAK_ADMIN_PASSWORD,
            }
        )

    try:
        response = requests.post(settings.KEYCLOAK_TOKEN_URL, data=data, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise DepartmentResolutionError(
            "Keycloak Admin API authentication failed. Check OIDC_ADMIN_CLIENT_ID and OIDC_ADMIN_CLIENT_SECRET."
        ) from exc
    payload = response.json()
    token = payload["access_token"]
    expires_in = int(payload.get("expires_in", 60))
    _admin_token_cache["value"] = token
    _admin_token_cache["expires_at"] = now + expires_in
    return token


def _admin_headers():
    return {"Authorization": f"Bearer {_get_admin_token()}"}


def _fetch_group_children(group_id):
    try:
        response = requests.get(
            f"{settings.KEYCLOAK_ADMIN_BASE_URL}/groups/{group_id}/children",
            params={"briefRepresentation": "false", "max": 1000},
            headers=_admin_headers(),
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise DepartmentResolutionError(
            "Failed to fetch Keycloak group children."
        ) from exc
    return response.json()


def _expand_group_tree(group):
    normalized_group = {
        "id": str(group.get("id") or ""),
        "name": group.get("name") or _group_name_from_path(group.get("path") or group.get("name")),
        "description": str(group.get("description") or "").strip(),
        "path": _normalize_group_path(group.get("path") or group.get("name")),
        "sub_group_count": int(group.get("subGroupCount") or len(group.get("subGroups") or [])),
    }

    flat_groups = [normalized_group]
    children = group.get("subGroups") or []
    if not children and normalized_group["sub_group_count"] > 0 and normalized_group["id"]:
        children = _fetch_group_children(normalized_group["id"])

    for child in children:
        flat_groups.extend(_expand_group_tree(child))

    return flat_groups


def _fetch_all_groups():
    try:
        response = requests.get(
            f"{settings.KEYCLOAK_ADMIN_BASE_URL}/groups",
            params={"briefRepresentation": "false", "max": 1000},
            headers=_admin_headers(),
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise DepartmentResolutionError(
            "Failed to fetch departments from Keycloak Admin API."
        ) from exc

    flat_groups = []
    for group in response.json():
        flat_groups.extend(_expand_group_tree(group))
    return flat_groups


def _fetch_user_groups(user_id):
    try:
        response = requests.get(
            f"{settings.KEYCLOAK_ADMIN_BASE_URL}/users/{user_id}/groups",
            params={"briefRepresentation": "false", "max": 1000},
            headers=_admin_headers(),
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise DepartmentResolutionError(
            "Failed to fetch user groups from Keycloak Admin API."
        ) from exc
    return _flatten_groups(response.json())


def _fetch_group_members(group_id):
    members = []
    first = 0
    batch_size = 200

    while True:
        try:
            response = requests.get(
                f"{settings.KEYCLOAK_ADMIN_BASE_URL}/groups/{group_id}/members",
                params={"briefRepresentation": "false", "first": first, "max": batch_size},
                headers=_admin_headers(),
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DepartmentResolutionError(
                "Failed to fetch department members from Keycloak Admin API."
            ) from exc

        batch = response.json()
        if not batch:
            break

        members.extend(batch)
        if len(batch) < batch_size:
            break

        first += batch_size

    return members


def _department_groups(groups):
    prefix = _normalize_group_path(settings.KEYCLOAK_DEPARTMENT_GROUP_PATH_PREFIX)
    if not prefix:
        return [
            group
            for group in groups
            if group.get("path") and not group.get("sub_group_count")
        ]

    filtered = []
    for group in groups:
        path = group.get("path") or ""
        if not path or path == prefix or group.get("sub_group_count"):
            continue
        if path.startswith(f"{prefix}/"):
            filtered.append(group)
    return filtered


def _department_list_queryset():
    active_departments = Department.objects.filter(is_active=True)
    keycloak_departments = active_departments.filter(keycloak_path__isnull=False).order_by("name")
    if keycloak_departments.exists():
        return keycloak_departments
    return active_departments.order_by("name")


def _upsert_department(group):
    group_id = group.get("id") or None
    path = group.get("path") or None
    technical_name = str(group.get("name") or _group_name_from_path(path)).strip()
    display_name = _group_display_name(group)

    department = None
    if group_id:
        department = Department.objects.filter(keycloak_group_id=group_id).first()
    if department is None and path:
        department = Department.objects.filter(keycloak_path=path).first()
    if department is None and display_name:
        department = Department.objects.filter(
            keycloak_group_id__isnull=True,
            name=display_name,
        ).first()
    if department is None and technical_name:
        department = Department.objects.filter(
            keycloak_group_id__isnull=True,
            name=technical_name,
        ).first()

    defaults = {
        "name": display_name,
        "keycloak_group_id": group_id,
        "keycloak_path": path,
        "is_active": True,
    }

    if department is None:
        return Department.objects.create(**defaults)

    changed = False
    for field, value in defaults.items():
        if getattr(department, field) != value:
            setattr(department, field, value)
            changed = True
    if changed:
        department.save(update_fields=list(defaults.keys()))
    return department


def sync_departments_from_keycloak(force=False):
    if not _admin_api_is_configured():
        return _department_list_queryset()

    now = time.time()
    if not force and _department_sync_cache["expires_at"] > now:
        return _department_list_queryset()

    groups = _department_groups(_fetch_all_groups())
    seen_group_ids = set()

    for group in groups:
        department = _upsert_department(group)
        if department.keycloak_group_id:
            seen_group_ids.add(department.keycloak_group_id)

    Department.objects.exclude(keycloak_group_id__isnull=True).exclude(
        keycloak_group_id__in=seen_group_ids
    ).update(is_active=False)

    _department_sync_cache["expires_at"] = now + max(settings.KEYCLOAK_DEPARTMENT_SYNC_TTL, 0)
    return _department_list_queryset()


def _token_group_paths(payload):
    groups = payload.get("groups") or []
    return sorted(
        {
            _normalize_group_path(group)
            for group in groups
            if isinstance(group, str) and _normalize_group_path(group)
        }
    )


def get_user_group_paths(payload):
    group_paths = _token_group_paths(payload)
    if group_paths:
        return group_paths

    user_id = payload.get("sub")
    if user_id and _admin_api_is_configured():
        try:
            return sorted(
                {
                    group["path"]
                    for group in _department_groups(_fetch_user_groups(user_id))
                    if group.get("path")
                }
            )
        except DepartmentResolutionError:
            return []

    return []


def ensure_departments_for_group_paths(group_paths):
    created = []
    for path in group_paths:
        normalized_path = _normalize_group_path(path)
        if not normalized_path:
            continue

        department = Department.objects.filter(keycloak_path=normalized_path).first()
        if department is None:
            department = Department.objects.create(
                name=_group_name_from_path(normalized_path),
                keycloak_path=normalized_path,
                is_active=True,
            )
        elif not department.is_active:
            department.is_active = True
            department.save(update_fields=["is_active"])
        created.append(department)
    return created


def resolve_user_department(payload, sync=False):
    token_group_paths = _token_group_paths(payload)
    if sync:
        try:
            sync_departments_from_keycloak()
        except DepartmentResolutionError:
            if token_group_paths:
                ensure_departments_for_group_paths(token_group_paths)
            else:
                raise

    group_paths = get_user_group_paths(payload)
    if not group_paths:
        return None

    departments = list(
        Department.objects.filter(
            is_active=True,
            keycloak_path__in=group_paths,
        ).order_by("name")
    )

    if not departments:
        departments = ensure_departments_for_group_paths(group_paths)

    if not departments:
        return None

    departments.sort(key=lambda department: len(department.keycloak_path or ""), reverse=True)
    if len(departments) > 1:
        top_length = len(departments[0].keycloak_path or "")
        second_length = len(departments[1].keycloak_path or "")
        if top_length == second_length:
            raise DepartmentResolutionError(
                "User belongs to multiple Keycloak departments. Narrow the group mapping."
            )

    return departments[0]
