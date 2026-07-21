import logging
import os
import sys
from typing import Dict, List, Optional, Set, Tuple

import requests


KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "master")
KEYCLOAK_ADMIN_REALM = os.getenv("KEYCLOAK_ADMIN_REALM", "master")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "admin-cli")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "")
KEYCLOAK_USERNAME = os.getenv("KEYCLOAK_USERNAME", "admin")
KEYCLOAK_PASSWORD = os.getenv("KEYCLOAK_PASSWORD", "admin")

LDAP_DN_ATTRIBUTE = os.getenv("LDAP_DN_ATTRIBUTE", "ldap_dn")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
ONLY_ENABLED_USERS = os.getenv("ONLY_ENABLED_USERS", "true").lower() == "true"

DEPARTMENTS_ROOT_GROUP = os.getenv("DEPARTMENTS_ROOT_GROUP", "Departments")

ALLOWED_DEPARTMENTS: Set[str] = {
    "accounting",
    "aup",
    "billing_operations",
    "chancellery",
    "commerce",
    "compliance",
    "finance",
    "hr",
    "ib",
    "it",
    "it_app_razrab",
    "it_vnedreniye",
    "legal",
    "managerial",
    "marketing_pr",
    "nabsovet",
    "pm",
    "purchasing",
    "regional",
    "risk",
    "securityaho",
    "students",
    "testgroup",
    "ucmg",
}

DEPARTMENT_NAME_MAP: Dict[str, str] = {
    # "it_app_razrab": "it-dev",
    # "marketing_pr": "marketing",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


class KeycloakAdminError(Exception):
    pass


def normalize_base_url(url: str) -> str:
    return url.rstrip("/")


def normalize_department_name(name: str) -> str:
    if not name:
        return name
    return name.strip().lower()


def extract_department_from_dn(dn: str) -> Optional[str]:
    if not dn:
        return None

    parts = [p.strip() for p in dn.split(",") if p.strip()]
    lower_parts = [p.lower() for p in parts]

    try:
        domain_users_idx = lower_parts.index("ou=domain users")
    except ValueError:
        return None

    if domain_users_idx <= 0:
        return None

    for idx in range(domain_users_idx - 1, -1, -1):
        part = parts[idx]
        if part.lower().startswith("ou="):
            return part[3:]

    return None


def get_first_attr_value(user: dict, attr_name: str) -> Optional[str]:
    attrs = user.get("attributes") or {}
    value = attrs.get(attr_name)

    if value is None:
        return None

    if isinstance(value, list):
        return value[0] if value else None

    if isinstance(value, str):
        return value

    return str(value)


class KeycloakAdminClient:
    def __init__(
        self,
        base_url: str,
        admin_realm: str,
        realm: str,
        client_id: str,
        username: str,
        password: str,
        client_secret: str = "",
        timeout: int = 30,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self.admin_realm = admin_realm
        self.realm = realm
        self.client_id = client_id
        self.username = username
        self.password = password
        self.client_secret = client_secret
        self.timeout = timeout

        self.session = requests.Session()
        self.access_token: Optional[str] = None

    def authenticate(self) -> None:
        token_url = f"{self.base_url}/realms/{self.admin_realm}/protocol/openid-connect/token"

        data = {
            "grant_type": "password",
            "client_id": self.client_id,
            "username": self.username,
            "password": self.password,
        }

        if self.client_secret:
            data["client_secret"] = self.client_secret

        response = self.session.post(token_url, data=data, timeout=self.timeout)
        if response.status_code != 200:
            raise KeycloakAdminError(
                f"Failed to authenticate: {response.status_code} {response.text}"
            )

        payload = response.json()
        self.access_token = payload["access_token"]
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
        )

    def _admin_url(self, path: str) -> str:
        return f"{self.base_url}/admin/realms/{self.realm}{path}"

    def get_users(self, batch_size: int = 200) -> List[dict]:
        users: List[dict] = []
        first = 0

        while True:
            params = {
                "first": first,
                "max": batch_size,
            }
            response = self.session.get(
                self._admin_url("/users"),
                params=params,
                timeout=self.timeout,
            )
            if response.status_code != 200:
                raise KeycloakAdminError(
                    f"Failed to get users: {response.status_code} {response.text}"
                )

            batch = response.json()
            if not batch:
                break

            users.extend(batch)
            if len(batch) < batch_size:
                break

            first += batch_size

        return users

    def get_user(self, user_id: str) -> dict:
        response = self.session.get(
            self._admin_url(f"/users/{user_id}"),
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise KeycloakAdminError(
                f"Failed to get user {user_id}: {response.status_code} {response.text}"
            )
        return response.json()

    def get_groups(self) -> List[dict]:
        response = self.session.get(
            self._admin_url("/groups"),
            params={"briefRepresentation": "false", "max": 1000},
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise KeycloakAdminError(
                f"Failed to get groups: {response.status_code} {response.text}"
            )
        return response.json()

    def get_group_children(self, group_id: str) -> List[dict]:
        response = self.session.get(
            self._admin_url(f"/groups/{group_id}/children"),
            params={"briefRepresentation": "false", "max": 1000},
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise KeycloakAdminError(
                f"Failed to get group children for {group_id}: {response.status_code} {response.text}"
            )
        return response.json()

    def get_user_groups(self, user_id: str) -> List[dict]:
        response = self.session.get(
            self._admin_url(f"/users/{user_id}/groups"),
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise KeycloakAdminError(
                f"Failed to get user groups: {response.status_code} {response.text}"
            )
        return response.json()

    def add_user_to_group(self, user_id: str, group_id: str) -> None:
        response = self.session.put(
            self._admin_url(f"/users/{user_id}/groups/{group_id}"),
            timeout=self.timeout,
        )
        if response.status_code != 204:
            raise KeycloakAdminError(
                f"Failed to add user to group: {response.status_code} {response.text}"
            )

    def remove_user_from_group(self, user_id: str, group_id: str) -> None:
        response = self.session.delete(
            self._admin_url(f"/users/{user_id}/groups/{group_id}"),
            timeout=self.timeout,
        )
        if response.status_code != 204:
            raise KeycloakAdminError(
                f"Failed to remove user from group: {response.status_code} {response.text}"
            )


def flatten_groups(groups: List[dict], parent_path: str = "") -> List[dict]:
    result: List[dict] = []

    for group in groups:
        current_path = f"{parent_path}/{group['name']}" if parent_path else f"/{group['name']}"
        item = {
            "id": group["id"],
            "name": group["name"],
            "description": (group.get("description") or "").strip(),
            "path": group.get("path") or current_path,
        }
        result.append(item)

        children = group.get("subGroups") or []
        result.extend(flatten_groups(children, current_path))

    return result


def resolve_target_department(department_from_dn: str) -> Optional[str]:
    if not department_from_dn:
        return None

    normalized = normalize_department_name(department_from_dn)
    mapped = DEPARTMENT_NAME_MAP.get(normalized, normalized)

    if mapped not in ALLOWED_DEPARTMENTS:
        return None

    return mapped


def ensure_user_has_attributes(kc: "KeycloakAdminClient", user: dict) -> dict:
    ldap_dn = get_first_attr_value(user, LDAP_DN_ATTRIBUTE)
    if ldap_dn:
        return user
    return kc.get_user(user["id"])


def build_department_group_index(kc: KeycloakAdminClient, all_groups: List[dict]) -> Dict[str, dict]:
    root_group = None
    for group in all_groups:
        if normalize_department_name(group.get("name", "")) == normalize_department_name(DEPARTMENTS_ROOT_GROUP):
            root_group = group
            break

    if not root_group:
        logger.warning("Root group '/%s' not found", DEPARTMENTS_ROOT_GROUP)
        return {}

    children = kc.get_group_children(root_group["id"])
    by_name: Dict[str, dict] = {}

    for group in children:
        normalized_name = normalize_department_name(group.get("name", ""))
        if normalized_name not in ALLOWED_DEPARTMENTS:
            continue

        by_name[normalized_name] = {
            "id": group["id"],
            "name": group["name"],
            "display_name": (group.get("description") or group["name"]).strip(),
            "path": group.get("path") or f"/{DEPARTMENTS_ROOT_GROUP}/{group['name']}",
        }

    return by_name


def sync_user_department(
    kc: KeycloakAdminClient,
    user: dict,
    department_group_index: Dict[str, dict],
) -> Tuple[bool, str]:
    user_id = user["id"]
    username = user.get("username", "<unknown>")
    enabled = user.get("enabled", True)

    if ONLY_ENABLED_USERS and not enabled:
        return False, f"{username}: skipped, user disabled"

    user = ensure_user_has_attributes(kc, user)

    ldap_dn = get_first_attr_value(user, LDAP_DN_ATTRIBUTE)
    if not ldap_dn:
        return False, f"{username}: skipped, no {LDAP_DN_ATTRIBUTE}"

    department_raw = extract_department_from_dn(ldap_dn)
    if not department_raw:
        return False, f"{username}: skipped, could not extract department from DN '{ldap_dn}'"

    department = resolve_target_department(department_raw)
    if not department:
        return False, f"{username}: skipped, extracted department '{department_raw}' is not allowed"

    target_group = department_group_index.get(department)
    if not target_group:
        return False, (
            f"{username}: skipped, target group '/{DEPARTMENTS_ROOT_GROUP}/{department}' "
            f"not found in Keycloak"
        )

    user_groups = kc.get_user_groups(user_id)

    departments_root_path = f"/{DEPARTMENTS_ROOT_GROUP}"
    current_department_groups = [
        g for g in user_groups
        if g.get("path", "").startswith(departments_root_path + "/")
        and normalize_department_name(g["name"]) in ALLOWED_DEPARTMENTS
    ]

    current_department_names = {
        normalize_department_name(g["name"]) for g in current_department_groups
    }

    if current_department_names == {department}:
        return False, (
            f"{username}: already in correct department "
            f"'{target_group['path']}'"
        )

    actions = []

    for group in current_department_groups:
        group_name_normalized = normalize_department_name(group["name"])
        if group_name_normalized != department:
            actions.append(("remove", group["id"], group["path"]))

    if department not in current_department_names:
        actions.append(("add", target_group["id"], target_group["path"]))

    if not actions:
        return False, f"{username}: no actions needed"

    if DRY_RUN:
        action_text = ", ".join([f"{action}:{path}" for action, _, path in actions])
        return True, f"{username}: DRY RUN -> {action_text}"

    for action, group_id, _group_path in actions:
        if action == "remove":
            kc.remove_user_from_group(user_id, group_id)
        elif action == "add":
            kc.add_user_to_group(user_id, group_id)
        else:
            raise ValueError(f"Unknown action: {action}")

    action_text = ", ".join([f"{action}:{path}" for action, _, path in actions])
    return True, f"{username}: applied -> {action_text}"


def main() -> int:
    logger.info("Starting Keycloak department sync job")
    logger.info("DRY_RUN=%s", DRY_RUN)
    logger.info("DEPARTMENTS_ROOT_GROUP=%s", DEPARTMENTS_ROOT_GROUP)

    try:
        kc = KeycloakAdminClient(
            base_url=KEYCLOAK_BASE_URL,
            admin_realm=KEYCLOAK_ADMIN_REALM,
            realm=KEYCLOAK_REALM,
            client_id=KEYCLOAK_CLIENT_ID,
            client_secret=KEYCLOAK_CLIENT_SECRET,
            username=KEYCLOAK_USERNAME,
            password=KEYCLOAK_PASSWORD,
            timeout=REQUEST_TIMEOUT,
        )

        kc.authenticate()
        logger.info("Authenticated successfully")

        groups = kc.get_groups()
        department_group_index = build_department_group_index(kc, groups)

        missing_groups = sorted(ALLOWED_DEPARTMENTS - set(department_group_index.keys()))
        if missing_groups:
            logger.warning(
                "Missing department subgroups under /%s: %s",
                DEPARTMENTS_ROOT_GROUP,
                missing_groups,
            )

        users = kc.get_users()
        logger.info("Loaded %s users", len(users))

        changed = 0
        skipped = 0
        failed = 0

        for user in users:
            username = user.get("username", "<unknown>")
            try:
                was_changed, message = sync_user_department(kc, user, department_group_index)
                if was_changed:
                    changed += 1
                    logger.info(message)
                else:
                    skipped += 1
                    logger.info(message)
            except Exception as exc:
                failed += 1
                logger.exception("Failed to process user %s: %s", username, exc)

        logger.info(
            "Finished sync. changed=%s skipped=%s failed=%s",
            changed,
            skipped,
            failed,
        )
        return 0 if failed == 0 else 2

    except Exception as exc:
        logger.exception("Sync job failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
