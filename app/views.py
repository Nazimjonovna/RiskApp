from datetime import datetime, timedelta
import csv
from collections import defaultdict
import os
import re
from io import StringIO
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q, Subquery
from django.utils.dateparse import parse_datetime as _parse_datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests
from django.core.cache import cache
from django.conf import settings
from django.shortcuts import get_object_or_404
from .services.risk_activity import create_risk_activity_and_notify, add_user_to_risk_activity
from .services.notification import notify_risk_update, notify_mitigation_update, notify_mitigation_create
from rest_framework.permissions import IsAuthenticated, AllowAny
from .permissions import (
    IsReadOnlyOrSuperAdmin,
    get_request_realm_roles,
    has_any_logical_role,
    has_logical_role,
)
from drf_yasg.utils import swagger_auto_schema
from .serializers import (RiskActivitySerializer, RiskCommitteeSerializer, RiskDecisionSerializer,
                          RiskSerializer, MitigationSerializer, DepartmentSerializer, StatusSerializer,
                          CategorySerializer, ReplyRiskActivitySerializer, UserSerializer)
from .services.keycloak_departments import (
    DepartmentResolutionError,
    _fetch_group_members,
    get_user_group_paths,
    resolve_user_department,
    sync_departments_from_keycloak,
)
from .services.department_identity import canonical_department_key
from .models import (Department, Category,  Risk, RiskActivity, RiskCommittee, RiskDecition,
                     Mitigation, ReplyRiskActivity)


CREATOR_EDITABLE_RISK_STATUSES = {
    "DRAFT",
    "INFO_REQUESTED_BY_RISK_MANAGER",
    "INFO_REQUESTED_BY_COMMITTEE",
}

MITIGATION_STAGE_RISK_STATUSES = {
    "ACCEPTED_FOR_MITIGATION",
    "IN_MITIGATION",
    "ADDITIONAL_MITIGATION_REQUIRED",
}

DIRECTOR_ASSIGNABLE_RISK_STATUSES = {
    "COMMITTEE_REVIEW_1",
    "COMMITTEE_REVIEW_2",
    *MITIGATION_STAGE_RISK_STATUSES,
}

MITIGATION_PERFORMER_EDITABLE_STATUSES = {
    "NOT_STARTED",
    "IN_PROGRESS",
}

MITIGATION_REVIEWABLE_STATUS = "PENDING_RISK_REVIEW"
MITIGATION_APPROVED_STATUS = "APPROVED"

DEPARTMENT_ALIASES = {
    "accounting": {"accounting", "бухгалтерия"},
    "aup": {"aup", "департамент по стратегическим проектам"},
    "billing_operations": {"billing_operations", "операционный департамент"},
    "chancellery": {"chancellery", "отдел делопроизводства"},
    "commerce": {"commerce", "коммерческий департамент"},
    "compliance": {"compliance", "внутренний контроль и комплаенс", "департамент комплаенс"},
    "finance": {"finance", "финансовый департамент", "финансовый департамент и фин контроль"},
    "hr": {"hr", "human resources", "департамент управления персоналом", "департамент персонала"},
    "ib": {"ib", "департамент обеспечения информационной безопасности", "департамент иб"},
    "it": {"it", "it and security", "it & security", "департамент ит", "департамент информационных технологий"},
    "it_app_razrab": {"it_app_razrab", "департамент по разработке программных решений"},
    "it_vnedreniye": {"it_vnedreniye"},
    "legal": {"legal", "юридический департамент"},
    "managerial": {"managerial", "административный департамент"},
    "marketing_pr": {"marketing_pr", "департамент маркетинга и продвижения"},
    "nabsovet": {"nabsovet", "аппарат наблюдательного совета"},
    "pm": {"pm", "департамент по разработке и развитию продуктов"},
    "purchasing": {"purchasing", "procurement", "департамент управления закупками", "департамент закупок"},
    "regional": {"regional", "отдел по работе с зарплатными проектами и региональными сотрудниками"},
    "risk": {"risk", "департамент управления рисками"},
    "securityaho": {"securityaho", "департамент физической безопасности"},
    "students": {"students", "департамент работы со стажёрами"},
    "ucmg": {"ucmg"},
}

REFERENCE_LIST_CACHE_TTL = int(os.getenv("RISK_REFERENCE_CACHE_TTL", "300"))
DEPARTMENT_REFERENCE_LIST_CACHE_KEY = "rms:departments:list:v1"
CATEGORY_REFERENCE_LIST_CACHE_KEY = "rms:categories:list:v1"
DEPARTMENT_SCOPE_INDEX_CACHE_KEY = "rms:department-scope-index:v1"
DEPARTMENT_SCOPE_INDEX_TTL = int(os.getenv("DEPARTMENT_SCOPE_INDEX_TTL_SECONDS", "300"))
ME_PROFILE_CACHE_TTL = int(os.getenv("ME_PROFILE_CACHE_TTL_SECONDS", "60"))
ME_PROFILE_CACHE_KEY = "rms:me-profile:{user_id}"
DIRECTORY_MEMBERS_CACHE_TTL = int(os.getenv("DEPARTMENT_MEMBERS_CACHE_TTL_SECONDS", "120"))
DIRECTORY_MEMBERS_CACHE_KEY = "rms:department-members:{department_id}"
DEFAULT_LIST_PAGE_SIZE = int(os.getenv("RISK_LIST_DEFAULT_PAGE_SIZE", "0"))
MAX_LIST_PAGE_SIZE = int(os.getenv("RISK_LIST_MAX_PAGE_SIZE", "250"))

ADMIN_REPORT_TYPE_CHOICES = {
    "risk-register",
    "status-summary",
    "department-summary",
    "decision-log",
}

ADMIN_REPORT_COLUMNS = {
    "risk-register": [
        {"key": "id", "label": "ID"},
        {"key": "title", "label": "Risk"},
        {"key": "department", "label": "Department"},
        {"key": "category", "label": "Category"},
        {"key": "status", "label": "Status"},
        {"key": "owner", "label": "Owner"},
        {"key": "responsible", "label": "Responsible"},
        {"key": "expectedLoss", "label": "Expected Loss"},
        {"key": "updatedAt", "label": "Updated"},
    ],
    "status-summary": [
        {"key": "status", "label": "Status"},
        {"key": "count", "label": "Risk count"},
        {"key": "totalLoss", "label": "Total expected loss"},
        {"key": "avgLoss", "label": "Avg expected loss"},
    ],
    "department-summary": [
        {"key": "department", "label": "Department"},
        {"key": "count", "label": "Risk count"},
        {"key": "totalLoss", "label": "Total expected loss"},
        {"key": "avgLoss", "label": "Avg expected loss"},
    ],
    "decision-log": [
        {"key": "id", "label": "Decision ID"},
        {"key": "riskId", "label": "Risk ID"},
        {"key": "riskTitle", "label": "Risk"},
        {"key": "type", "label": "Decision"},
        {"key": "decidedBy", "label": "Decided By"},
        {"key": "decidedAt", "label": "Date"},
        {"key": "notes", "label": "Notes"},
    ],
}


def _to_datetime_query_value(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)

    raw = str(value).strip()
    if not raw:
        return None

    if raw.isdigit():
        try:
            seconds = float(raw)
        except ValueError:
            return None
        return datetime.fromtimestamp(seconds, tz=timezone.utc)

    parsed = _parse_datetime(raw)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _get_updated_since(request):
    raw = request.query_params.get("updated_since")
    if raw is None:
        raw = request.query_params.get("since")
    if raw is None:
        return None
    return _to_datetime_query_value(raw)


def _apply_updated_since_filter(queryset, request, field_name):
    since = _get_updated_since(request)
    if not since:
        return queryset
    return queryset.filter(**{f"{field_name}__gt": since})


def _normalize_identity_value(value):
    return str(value or "").strip().lower()


def _normalize_status_token(value):
    return str(value or "").strip().upper().replace(" ", "_").replace("-", "_")


def _sanitize_department_value(value):
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    text = text.replace("&", " and ")
    text = re.sub(r"[\"'`]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


_SANITIZED_DEPARTMENT_ALIASES = {
    canonical: {_sanitize_department_value(canonical), *{_sanitize_department_value(alias) for alias in aliases}}
    for canonical, aliases in DEPARTMENT_ALIASES.items()
}


def _canonical_department_key(value):
    normalized = _sanitize_department_value(value)
    if not normalized:
        return ""

    for canonical, aliases in _SANITIZED_DEPARTMENT_ALIASES.items():
        if normalized in aliases:
            return canonical

    return normalized


def _get_request_context(request):
    context = getattr(request, "_rms_request_context", None)
    if context is not None:
        return context

    payload = request.auth or {}
    user = request.user
    given_name = str(payload.get("given_name") or "").strip()
    family_name = str(payload.get("family_name") or "").strip()
    full_name = " ".join(part for part in [given_name, family_name] if part).strip()
    identity_values = [
        payload.get("preferred_username"),
        payload.get("email"),
        payload.get("name"),
        full_name,
        getattr(user, "username", None),
        getattr(user, "email", None),
        getattr(user, "get_full_name", lambda: "")(),
        payload.get("sub"),
        getattr(user, "id", None),
    ]

    identity_candidates = {
        _normalize_identity_value(value)
        for value in identity_values
        if value is not None and _normalize_identity_value(value)
    }

    department_values = [
        payload.get("department"),
        payload.get("dept"),
        payload.get("org_unit"),
        payload.get("organization"),
        payload.get("division"),
    ]
    group_paths = get_user_group_paths(payload)
    department_values.extend(group_paths)
    department_values.extend(
        path.rsplit("/", 1)[-1]
        for path in group_paths
        if isinstance(path, str) and path.strip()
    )

    try:
        department = resolve_user_department(payload, sync=False)
    except DepartmentResolutionError:
        department = None

    if department:
        department_values.extend(_department_identity_candidates(department))

    department_candidates = set()
    for value in department_values:
        normalized = _normalize_identity_value(value)
        canonical = canonical_department_key(value)
        if normalized:
            department_candidates.add(normalized)
        if canonical:
            department_candidates.add(canonical)

    context = {
        "identity_candidates": identity_candidates,
        "department_candidates": department_candidates,
        "actor_label": (
            payload.get("preferred_username")
            or getattr(user, "username", None)
            or payload.get("email")
            or "System"
        ),
        "can_view_all_risks": has_any_logical_role(
            request,
            ["super-admin", "risk-dept", "risk-committee"],
        ),
        "is_dept_director": has_logical_role(request, "dept-director"),
        "is_risk_dept_or_committee": has_any_logical_role(request, ["risk-dept", "risk-committee"]),
        "is_risk_dept": has_logical_role(request, "risk-dept"),
    }

    request._rms_request_context = context
    return context


def _request_identity_candidates(request):
    return _get_request_context(request)["identity_candidates"]


def _parse_positive_int(value, default=0, max_value=None):
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default

    if parsed < 1:
        return default

    if max_value and parsed > max_value:
        return max_value

    return parsed


def _is_pagination_requested(request):
    params = request.query_params
    return ("page" in params) or ("page_size" in params) or (params.get("paginate") == "1")


def _get_pagination_params(request):
    if not _is_pagination_requested(request):
        return None

    page = _parse_positive_int(request.query_params.get("page"), 1)
    page_size = _parse_positive_int(
        request.query_params.get("page_size"),
        DEFAULT_LIST_PAGE_SIZE or 50,
        MAX_LIST_PAGE_SIZE,
    )
    include_count = request.query_params.get("include_count", "1") != "0"

    return {
        "page": page,
        "page_size": page_size,
        "include_count": include_count,
    }


def _paginate_queryset(queryset, request):
    pagination = _get_pagination_params(request)
    if not pagination:
        return {"count": None, "results": list(queryset), "next": None, "previous": None}

    page = pagination["page"]
    page_size = pagination["page_size"]
    include_count = pagination["include_count"]
    offset = (page - 1) * page_size
    sliced = queryset[offset : offset + page_size + 1]
    values = list(sliced)
    has_more = len(values) > page_size
    next_page = page + 1 if has_more else None
    if has_more:
        values = values[:page_size]

    return {
        "count": queryset.count() if include_count else None,
        "next": next_page,
        "previous": page - 1 if page > 1 else None,
        "results": values,
        "page": page,
        "page_size": page_size,
    }


def _is_risk_creator(request, risk, request_context=None):
    creator_value = _normalize_identity_value(getattr(risk, "created_by_user_id", ""))
    identities = (request_context or _get_request_context(request))["identity_candidates"]
    return bool(creator_value) and creator_value in identities


def _request_actor_label(request):
    return _get_request_context(request)["actor_label"]


def _directory_member_label(member):
    joined_name = " ".join(
        part
        for part in [
            str(member.get("firstName") or "").strip(),
            str(member.get("lastName") or "").strip(),
        ]
        if part
    ).strip()
    return (
        joined_name
        or str(member.get("username") or "").strip()
        or str(member.get("email") or "").strip()
        or str(member.get("id") or "").strip()
    )


def _request_department_candidates(request):
    return set(_get_request_context(request)["department_candidates"])


def _department_identity_candidates(department):
    values = [
        getattr(department, "name", None),
        getattr(department, "keycloak_path", None),
    ]

    keycloak_path = str(getattr(department, "keycloak_path", "") or "").strip()
    if keycloak_path:
        values.append(keycloak_path.rsplit("/", 1)[-1])

    candidates = set()
    for value in values:
        normalized = _normalize_identity_value(value)
        canonical = canonical_department_key(value)
        if normalized:
            candidates.add(normalized)
        if canonical:
            candidates.add(canonical)
    return candidates


def _get_department_scope_index():
    cached_payload = cache.get(DEPARTMENT_SCOPE_INDEX_CACHE_KEY)
    if isinstance(cached_payload, dict):
        return {
            key: set(department_ids)
            for key, department_ids in cached_payload.items()
            if isinstance(department_ids, (list, tuple, set))
        }

    department_index = {}
    departments = Department.objects.filter(is_active=True).only("id", "name", "keycloak_path")
    for department in departments:
        candidates = _department_identity_candidates(department)
        for candidate in candidates:
            if not candidate:
                continue
            department_ids = department_index.setdefault(candidate, set())
            department_ids.add(department.id)

    cache.set(
        DEPARTMENT_SCOPE_INDEX_CACHE_KEY,
        {key: sorted(value) for key, value in department_index.items()},
        DEPARTMENT_SCOPE_INDEX_TTL,
    )
    return department_index


def _is_risk_related_department_director(request, risk, request_context=None):
    request_context = request_context or _get_request_context(request)
    if not request_context["is_dept_director"]:
        return False

    request_departments = request_context["department_candidates"]
    risk_departments = set()
    prioritized_departments = [
        getattr(risk, "responsible_department_id", None),
        getattr(risk, "department", None),
    ]

    for department in prioritized_departments:
        if department:
            risk_departments.update(_department_identity_candidates(department))

    return bool(request_departments & risk_departments)


def _has_risk_mitigation_assignment(request, risk, request_context=None):
    identities = (request_context or _get_request_context(request))["identity_candidates"]
    if not identities:
        return False

    return Mitigation.objects.filter(
        risk_id=getattr(risk, "id", None),
        owner__in=identities,
    ).exists()


def _department_ids_for_request(request_context):
    cached_department_ids = request_context.get("_department_ids")
    if cached_department_ids is not None:
        return cached_department_ids

    department_candidates = set(request_context.get("department_candidates", ()))
    if not department_candidates:
        request_context["_department_ids"] = set()
        return set()

    scope_index = _get_department_scope_index()
    department_ids = set()
    for candidate in department_candidates:
        department_ids.update(scope_index.get(candidate, set()))

    request_context["_department_ids"] = department_ids
    return department_ids


def _get_scoped_risks_for_request(request):
    return _scoped_risk_queryset(request)


def _can_view_risk(request, risk, request_context=None):
    context = request_context or _get_request_context(request)
    if context["can_view_all_risks"]:
        return True

    if _is_risk_creator(request, risk, context):
        return True

    if _normalize_identity_value(getattr(risk, "responsible", "")) in context["identity_candidates"]:
        return True

    if _is_risk_related_department_director(request, risk, context):
        return True

    if _has_risk_mitigation_assignment(request, risk, context):
        return True

    return False


def _scoped_risk_queryset(request, request_context=None):
    request_context = request_context or _get_request_context(request)
    department_ids = _department_ids_for_request(request_context)

    queryset = Risk.objects.select_related(
        "department",
        "category",
        "responsible_department_id",
    )

    if request_context["can_view_all_risks"]:
        return queryset

    identities = request_context["identity_candidates"]
    access_filter = Q(created_by_user_id__in=identities) | Q(responsible__in=identities)
    if department_ids:
        access_filter |= Q(responsible_department_id__in=department_ids)

    mitigation_risk_ids = Subquery(
        Mitigation.objects.filter(owner__in=identities).values("risk_id")
    )
    access_filter |= Q(id__in=mitigation_risk_ids)

    scoped = queryset.filter(access_filter).distinct()
    return scoped


def _normalize_report_query(value):
    return str(value or "").strip().lower()


def _to_safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_report_iso_datetime(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone()).isoformat()
    return value.isoformat()


def _report_decision_display(value):
    return dict(RiskDecition.DECITION_CHOICES).get(value, value or "")


def _report_risk_status_display(value):
    return dict(Risk.STATUS_CHOICES).get(value, value or "")


def _report_department_name(risk):
    department = risk.department or getattr(risk, "responsible_department_id", None)
    if department is not None:
        return department.name or ""
    return ""


def _build_report_risk_search_filter(query):
    text = _normalize_report_query(query)
    if not text:
        return Q()

    search_filter = (
        Q(risk_number__icontains=text)
        | Q(title__icontains=text)
        | Q(status__icontains=text)
        | Q(owner__icontains=text)
        | Q(responsible__icontains=text)
        | Q(department__name__icontains=text)
        | Q(category__name__icontains=text)
        | Q(responsible_department_id__name__icontains=text)
    )

    if text.isdigit():
        search_filter |= Q(id=int(text))

    return search_filter


def _build_risk_register_rows(risk_queryset):
    rows = []
    for risk in risk_queryset:
        rows.append({
            "id": risk.risk_number or str(risk.id),
            "title": risk.title or "",
            "department": _report_department_name(risk),
            "category": risk.category.name if getattr(risk, "category", None) else "",
            "status": _report_risk_status_display(risk.status),
            "owner": risk.owner or "",
            "responsible": risk.responsible or "",
            "expectedLoss": _to_safe_float(risk.possible_loss),
            "updatedAt": _safe_report_iso_datetime(risk.updated_at),
        })
    return rows


def _build_status_summary_rows(risks):
    buckets = defaultdict(lambda: {"count": 0, "totalLoss": 0.0})

    for risk in risks:
        status = _report_risk_status_display(risk.status)
        bucket = buckets[status]
        bucket["count"] += 1
        bucket["totalLoss"] += _to_safe_float(risk.possible_loss)

    rows = []
    for status, data in buckets.items():
        total = data["totalLoss"]
        count = data["count"]
        rows.append({
            "status": status,
            "count": count,
            "totalLoss": total,
            "avgLoss": total / count if count else 0.0,
        })

    return sorted(rows, key=lambda item: item["count"], reverse=True)


def _build_department_summary_rows(risks):
    buckets = defaultdict(lambda: {"count": 0, "totalLoss": 0.0})

    for risk in risks:
        department = _report_department_name(risk) or "Not assigned"
        bucket = buckets[department]
        bucket["count"] += 1
        bucket["totalLoss"] += _to_safe_float(risk.possible_loss)

    rows = []
    for department, data in buckets.items():
        total = data["totalLoss"]
        count = data["count"]
        rows.append({
            "department": department,
            "count": count,
            "totalLoss": total,
            "avgLoss": total / count if count else 0.0,
        })

    return sorted(rows, key=lambda item: item["count"], reverse=True)


def _build_decision_log_rows(decision_queryset):
    rows = []
    for decision in decision_queryset:
        risk = decision.risk
        rows.append({
            "id": str(decision.id),
            "riskId": str(getattr(risk, "id", "")),
            "riskTitle": risk.title if risk else "",
            "type": _report_decision_display(decision.decition_type),
            "decidedBy": decision.decided_by or "",
            "decidedAt": _safe_report_iso_datetime(decision.decided_at),
            "notes": decision.notes or "",
        })

    return rows


def _build_admin_report_payload(request, report_type, search_query=""):
    scoped_risks = _scoped_risk_queryset(request)
    now = timezone.now().isoformat()

    if report_type == "risk-register":
        filtered_risks = scoped_risks.filter(_build_report_risk_search_filter(search_query)).order_by(
            "-updated_at",
            "-id",
        )
        return {
            "type": report_type,
            "generatedAt": now,
            "columns": ADMIN_REPORT_COLUMNS[report_type],
            "rows": _build_risk_register_rows(filtered_risks),
        }

    if report_type == "status-summary":
        rows = _build_status_summary_rows(scoped_risks)
        return {
            "type": report_type,
            "generatedAt": now,
            "columns": ADMIN_REPORT_COLUMNS[report_type],
            "rows": rows,
        }

    if report_type == "department-summary":
        rows = _build_department_summary_rows(scoped_risks)
        return {
            "type": report_type,
            "generatedAt": now,
            "columns": ADMIN_REPORT_COLUMNS[report_type],
            "rows": rows,
        }

    visible_risk_ids = list(scoped_risks.values_list("id", flat=True))
    decisions = (
        RiskDecition.objects.select_related("risk")
        .filter(risk_id__in=visible_risk_ids)
        .order_by("-decided_at")
    )
    rows = _build_decision_log_rows(decisions)
    return {
        "type": report_type,
        "generatedAt": now,
        "columns": ADMIN_REPORT_COLUMNS[report_type],
        "rows": rows,
    }


def _admin_report_csv_filename(report_type, generated_at):
    prefix = report_type.replace("-", "_")
    if isinstance(generated_at, str):
        date_part = generated_at[:10]
    else:
        date_part = timezone.localtime(generated_at or timezone.now()).date().isoformat()
    return f"{prefix}-{date_part}.csv"


def _admin_report_csv_response(payload):
    columns = payload["columns"]
    rows = payload["rows"]
    generated_at = payload.get("generatedAt")
    report_type = payload["type"]

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=[column["key"] for column in columns], extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({
            "id": row.get("id", ""),
            "title": row.get("title", ""),
            "department": row.get("department", ""),
            "category": row.get("category", ""),
            "status": row.get("status", ""),
            "owner": row.get("owner", ""),
            "responsible": row.get("responsible", ""),
            "expectedLoss": row.get("expectedLoss", ""),
            "updatedAt": row.get("updatedAt", ""),
            "count": row.get("count", ""),
            "totalLoss": row.get("totalLoss", ""),
            "avgLoss": row.get("avgLoss", ""),
            "riskId": row.get("riskId", ""),
            "riskTitle": row.get("riskTitle", ""),
            "type": row.get("type", ""),
            "decidedBy": row.get("decidedBy", ""),
            "decidedAt": row.get("decidedAt", ""),
            "notes": row.get("notes", ""),
        })

    response = HttpResponse(f"\ufeff{output.getvalue()}", content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{_admin_report_csv_filename(report_type, generated_at)}"'
    response["Cache-Control"] = "no-store"
    return response


class AdminReportsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["Reports"])
    def get(self, request, *args, **kwargs):
        if not has_logical_role(request, "super-admin"):
            return Response({
                "detail": "Only administrators can generate reports.",
                "status": status.HTTP_403_FORBIDDEN,
            }, status=status.HTTP_403_FORBIDDEN)

        report_type = _normalize_report_query(request.query_params.get("type"))
        if not report_type:
            return Response({
                "detail": "The report type is required.",
                "status": status.HTTP_400_BAD_REQUEST,
            }, status=status.HTTP_400_BAD_REQUEST)

        if report_type not in ADMIN_REPORT_TYPE_CHOICES:
            return Response({
                "detail": "Invalid report type.",
                "status": status.HTTP_400_BAD_REQUEST,
            }, status=status.HTTP_400_BAD_REQUEST)

        search_query = request.query_params.get("search", "")
        payload = _build_admin_report_payload(request, report_type, search_query)
        output_format = _normalize_report_query(request.query_params.get("format"))

        if output_format == "csv":
            return _admin_report_csv_response(payload)

        return Response(payload)


def _is_mitigation_owner(request, mitigation, request_context=None):
    identities = (request_context or _get_request_context(request))["identity_candidates"]
    return _normalize_identity_value(getattr(mitigation, "owner", "")) in identities


def _is_mitigation_department_director(request, mitigation, request_context=None):
    return _is_risk_related_department_director(request, mitigation.risk, request_context)


def _can_view_mitigation(request, mitigation, request_context=None):
    return _can_view_risk(request, mitigation.risk, request_context) or _is_mitigation_owner(
        request,
        mitigation,
        request_context,
    )


def _ensure_mitigation_risk_in_progress(mitigation, actor, notes=""):
    risk = mitigation.risk
    if _normalize_status_token(risk.status) in {"ACCEPTED_FOR_MITIGATION", "ADDITIONAL_MITIGATION_REQUIRED"}:
        risk.status = "IN_MITIGATION"
        risk.last_reviewed_at = timezone.now()
        risk.save(update_fields=["status", "last_reviewed_at", "updated_at"])
        RiskActivity.objects.create(
            risk=risk,
            type="REVIEW",
            title="Mitigation in progress",
            notes=notes or "Mitigation work is in progress.",
            by=actor,
            diff={
                "workflowStatus": "In Mitigation",
                "mitigationId": mitigation.id,
                "mitigationTitle": mitigation.title,
            },
        )


def _log_mitigation_activity(mitigation, actor, title, notes="", activity_type="REVIEW", extra_diff=None):
    diff = {
        "mitigationId": mitigation.id,
        "mitigationTitle": mitigation.title,
        "mitigationStatus": mitigation.status,
    }
    if extra_diff:
        diff.update(extra_diff)

    RiskActivity.objects.create(
        risk=mitigation.risk,
        type=activity_type,
        title=title,
        notes=notes,
        by=actor,
        diff=diff,
    )


def _advance_risk_to_committee_review_2_if_ready(risk, actor):
    mitigations = list(risk.mitigations.all())
    if not mitigations:
        return

    if any(_normalize_status_token(mitigation.status) != MITIGATION_APPROVED_STATUS for mitigation in mitigations):
        return

    if _normalize_status_token(risk.status) == "COMMITTEE_REVIEW_2":
        return

    risk.status = "COMMITTEE_REVIEW_2"
    risk.last_reviewed_at = timezone.now()
    risk.save(update_fields=["status", "last_reviewed_at", "updated_at"])

    RiskActivity.objects.create(
        risk=risk,
        type="REVIEW",
        title="All mitigation actions approved",
        notes="All mitigation actions were approved by the risk department and sent to Committee Review 2.",
        by=actor,
        diff={
            "workflowStatus": "Committee Review 2",
        },
    )


def _get_department_reference_payload_from_cache():
    payload = cache.get(DEPARTMENT_REFERENCE_LIST_CACHE_KEY)
    if isinstance(payload, dict):
        return payload
    return None


def _set_department_reference_payload_cache(payload):
    cache.set(DEPARTMENT_REFERENCE_LIST_CACHE_KEY, payload, REFERENCE_LIST_CACHE_TTL)


def _get_category_reference_payload_from_cache():
    payload = cache.get(CATEGORY_REFERENCE_LIST_CACHE_KEY)
    if isinstance(payload, dict):
        return payload
    return None


def _set_category_reference_payload_cache(payload):
    cache.set(CATEGORY_REFERENCE_LIST_CACHE_KEY, payload, REFERENCE_LIST_CACHE_TTL)


def _invalidate_reference_list_caches():
    cache.delete_many([
        DEPARTMENT_REFERENCE_LIST_CACHE_KEY,
        CATEGORY_REFERENCE_LIST_CACHE_KEY,
        DEPARTMENT_SCOPE_INDEX_CACHE_KEY,
    ])


def _all_mitigation_actions_approved(risk):
    mitigations = list(risk.mitigations.all())
    if not mitigations:
        return False

    return all(
        _normalize_status_token(mitigation.status) == MITIGATION_APPROVED_STATUS
        for mitigation in mitigations
    )


def _sync_risk_mitigation_owners(risk, responsible_value):
    normalized_responsible = str(responsible_value or "").strip()
    if not normalized_responsible:
        return

    Mitigation.objects.filter(risk=risk).exclude(
        status=MITIGATION_APPROVED_STATUS,
    ).update(owner=normalized_responsible)


class DepartmentView(APIView):
    permission_classes = [IsAuthenticated, IsReadOnlyOrSuperAdmin]
    
    @swagger_auto_schema(request_body=DepartmentSerializer, tags = ['Department'])
    def post(self, request, *args, **kwargs):
        serializer = DepartmentSerializer(data = request.data)
        if serializer.is_valid():
            instance = serializer.save()
            _invalidate_reference_list_caches()
            return Response({
                "data":serializer.data,
                "status":status.HTTP_201_CREATED
            })
        else:
            return Response({
                "error":serializer.errors
            })
            
    @swagger_auto_schema(tags = ['Department'])
    def get(self, request, *args,**kwargs):
        cached_response = _get_department_reference_payload_from_cache()
        if cached_response is not None:
            return Response(cached_response)

        try:
            departments = sync_departments_from_keycloak()
        except Exception:
            departments = Department.objects.filter(
                is_active=True,
                keycloak_path__isnull=False,
            ).order_by("name")
            if not departments.exists():
                departments = Department.objects.filter(is_active=True).order_by("name")
        serializer = DepartmentSerializer(departments, many = True)
        response_payload = {
            "data":serializer.data,
            "status":status.HTTP_200_OK
        }
        _set_department_reference_payload_cache(response_payload)
        return Response(response_payload)
        

class DepartmentCRUDView(APIView):
    permission_classes = [IsAuthenticated, IsReadOnlyOrSuperAdmin]
    
    @swagger_auto_schema(tags = ['Department'])
    def get(self, request, pk, *args, **kwargs):
        department = Department.objects.filter(id = pk).first()
        if department:
            seralizer = DepartmentSerializer(department)
            return Response({
                "data":seralizer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(tags = ['Department'])
    def delete(self, request, pk, *args, **kwargs):
        department = Department.objects.get(id = pk)
        if department:
            department.delete()
            _invalidate_reference_list_caches()
            return Response({
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(request_body=DepartmentSerializer, tags = ['Department'])
    def patch(self, request, pk, *args, **kwargs):
        department = Department.objects.filter(id =pk).first()
        if department:
            serializer = DepartmentSerializer(instance = department, data = request.data, partial = True)
            if serializer.is_valid():
                serializer.save()
                _invalidate_reference_list_caches()
                return Response({
                    "data":serializer.data,
                    "status":status.HTTP_200_OK
                })
            else:
                return Response({
                    "errors":serializer.errors
                })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
            
class CategoryView(APIView):
    permission_classes = [IsAuthenticated, IsReadOnlyOrSuperAdmin]
    
    @swagger_auto_schema(request_body=CategorySerializer, tags = ['Category'])
    def post(self, request, *args, **kwargs):
        serializer = CategorySerializer(data = request.data)
        if serializer.is_valid():
            instance = serializer.save()
            _invalidate_reference_list_caches()
            return Response({
                "data":serializer.data,
                "status":status.HTTP_201_CREATED
            })
        else:
            return Response({
                "error":serializer.errors
            })
            
    @swagger_auto_schema(tags = ['Category'])
    def get(self, request, *args,**kwargs):
        cached_response = _get_category_reference_payload_from_cache()
        if cached_response is not None:
            return Response(cached_response)

        departments = Category.objects.all()
        serializer = CategorySerializer(departments, many = True)
        response_payload = {
            "data":serializer.data,
            "status":status.HTTP_200_OK
        }
        _set_category_reference_payload_cache(response_payload)
        return Response(response_payload)
        

class CategoryCRUDView(APIView):
    permission_classes = [IsAuthenticated, IsReadOnlyOrSuperAdmin]
    
    @swagger_auto_schema(tags = ['Category'])
    def get(self, request, pk, *args, **kwargs):
        department = Category.objects.filter(id = pk).first()
        if department:
            seralizer = CategorySerializer(department)
            return Response({
                "data":seralizer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(tags = ['Category'])
    def delete(self, request, pk, *args, **kwargs):
        department = Category.objects.get(id = pk)
        if department:
            department.delete()
            _invalidate_reference_list_caches()
            return Response({
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(request_body=CategorySerializer, tags = ['Category'])
    def patch(self, request, pk, *args, **kwargs):
        department = Category.objects.filter(id =pk).first()
        if department:
            serializer = CategorySerializer(instance = department, data = request.data, partial = True)
            if serializer.is_valid():
                serializer.save()
                _invalidate_reference_list_caches()
                return Response({
                    "data":serializer.data,
                    "status":status.HTTP_200_OK
                })
            else:
                return Response({
                    "errors":serializer.errors
                })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
            
class CreateRiskView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(request_body=RiskSerializer, tags=['Risk'])
    def post(self, request, *args, **kwargs):
        serializer = RiskSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            risk = serializer.save()

            create_risk_activity_and_notify(
                risk=risk,
                actor=risk.owner,     
                action_type="CREATE",
                notes="Risk created"
            )

            return Response({
                "data": serializer.data,
                "status": status.HTTP_200_OK
            })

        return Response({
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
            
    @swagger_auto_schema(tags = ['Risk'])
    def get(self, request, *args, **kwargs):
        risk_query = _scoped_risk_queryset(request).order_by("-updated_at", "-id")
        risk_query = _apply_updated_since_filter(risk_query, request, "updated_at")
        paginated = _paginate_queryset(risk_query, request)
        serializer = RiskSerializer(paginated["results"], many=True)
        payload = {
            "data": serializer.data,
        }
        if paginated["count"] is not None:
            payload["syncedUntil"] = timezone.now().isoformat()
            payload["pagination"] = {
                "page": paginated["page"],
                "pageSize": paginated["page_size"],
                "count": paginated["count"],
                "next": paginated["next"],
                "previous": paginated["previous"],
            }
        return Response(payload)
        
        
class RiskCRUDView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(tags = ['Risk'])
    def get(self, request, pk, *args, **kwargs):
        risk = Risk.objects.filter(id = pk).first()
        if risk:
            if not _can_view_risk(request, risk):
                return Response({
                    "detail": "You do not have access to this risk.",
                    "status": status.HTTP_403_FORBIDDEN,
                }, status=status.HTTP_403_FORBIDDEN)
            serializer = RiskSerializer(risk)
            return Response({
                "data":serializer.data
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(tags = ["Risk"])
    def delete(self, request, pk, *args, **kwargs):
        if not has_logical_role(request, "super-admin"):
            return Response({
                "detail": "Only super admins can delete risk records.",
                "status": status.HTTP_403_FORBIDDEN,
            }, status=status.HTTP_403_FORBIDDEN)
        risk = Risk.objects.get(id = pk)
        if risk:
            risk.delete()
            return Response({
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(request_body=RiskSerializer, tags = ['Risk'])
    def patch(self, request, pk, *args, **kwargs):
        risk = Risk.objects.filter(id =pk).first()
        if risk:
            payload_data = request.data.copy()
            allowed = has_any_logical_role(request, ["risk-dept", "risk-committee"])
            request_department = None

            if not allowed and has_logical_role(request, "dept-director"):
                director_editable_fields = {
                    "responsible",
                    "responsible_department_id",
                    "due_date",
                    "last_reviewed_at",
                    "status",
                }
                requested_fields = set(request.data.keys())
                requested_status = _normalize_status_token(payload_data.get("status"))
                director_controls_own_risk = (
                    requested_fields.issubset(director_editable_fields)
                    and _is_risk_related_department_director(request, risk)
                )

                director_can_assign = (
                    director_controls_own_risk
                    and "status" not in requested_fields
                    and _normalize_status_token(risk.status) in DIRECTOR_ASSIGNABLE_RISK_STATUSES
                )
                director_can_send_to_committee = (
                    director_controls_own_risk
                    and requested_fields.issubset({"status", "last_reviewed_at"})
                    and requested_status == "COMMITTEE_REVIEW_2"
                    and _normalize_status_token(risk.status) in MITIGATION_STAGE_RISK_STATUSES
                    and _all_mitigation_actions_approved(risk)
                )
                allowed = director_can_assign or director_can_send_to_committee
                if allowed:
                    try:
                        request_department = resolve_user_department(request.auth or {}, sync=False)
                    except DepartmentResolutionError:
                        request_department = None

            if not allowed:
                return Response({
                    "detail": "You do not have permission to update this risk.",
                    "status": status.HTTP_403_FORBIDDEN,
                }, status=status.HTTP_403_FORBIDDEN)

            if request_department and "responsible" in payload_data and "responsible_department_id" not in payload_data:
                payload_data["responsible_department_id"] = request_department.id

            old_risk = Risk.objects.get(id=pk)
            serializer = RiskSerializer(
                instance=risk,
                data=payload_data,
                partial=True,
                context={"request": request},
            )
            if serializer.is_valid():
                updated_risk = serializer.save()
                if "responsible" in payload_data:
                    _sync_risk_mitigation_owners(updated_risk, updated_risk.responsible)
                notify_risk_update(old_risk, updated_risk)
                return Response({
                    "data":serializer.data,
                    "status":status.HTTP_200_OK
                })
            else:
                return Response({
                    "errors":serializer.errors
                })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
            
class UserRiskCrudView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(request_body=RiskSerializer, tags = ['Risk'])
    def patch(self, request, pk, *args, **kwargs):
        risk = Risk.objects.filter(id =pk).first()
        if risk:
            old_risk = Risk.objects.get(id=pk)
            if not _is_risk_creator(request, old_risk):
                return Response({
                    "detail": "Only the risk creator can update this record.",
                    "status": status.HTTP_403_FORBIDDEN,
                }, status=status.HTTP_403_FORBIDDEN)

            if _normalize_status_token(old_risk.status) in CREATOR_EDITABLE_RISK_STATUSES:
                serializer = RiskSerializer(
                    instance=risk,
                    data=request.data,
                    partial=True,
                    context={"request": request},
                )
                if serializer.is_valid():
                    updated_risk = serializer.save()
                    notify_risk_update(old_risk, updated_risk)
                    return Response({
                        "data":serializer.data,
                        "status":status.HTTP_200_OK
                    })
                else:
                    return Response({
                        "errors":serializer.errors
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    "detail":"This risk can only be updated by the creator while it is Draft or awaiting an information response.",
                    "status":status.HTTP_400_BAD_REQUEST
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            }, status=status.HTTP_404_NOT_FOUND)
            
            
class RiskCloseView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(tag = ['Risk'])
    def get(self, request, pk, *args, **kwargs):
        user = request.user
        risk = Risk.objects.filter(id = pk).first()
        if risk and (
            _normalize_identity_value(getattr(user, "username", "")) == _normalize_identity_value(risk.risk_derector)
            or has_logical_role(request, "risk-committee")
        ):
            risk.status = 'CLOSED'
            risk.is_active = False
            risk.save()
            serializer = RiskSerializer(data = risk)
            return Response({
                "data":serializer.data,
                'status':status.HTTP_200_OK
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })


class CreateRiskActivityView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(request_body=RiskActivitySerializer, tags = ['RiskActivity'])
    def post(self, request, *args, **kwargs):
        serializer = RiskActivitySerializer(data = request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "data":serializer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "errors":serializer.errors
            })
            
    @swagger_auto_schema(tags = ['RiskActivity'])
    def get(self, request, *args, **kwargs):
        visible_risk_ids = set(_get_scoped_risks_for_request(request).values_list("id", flat=True))
        riskactivity = (
            RiskActivity.objects.select_related("risk")
            .filter(risk_id__in=visible_risk_ids)
            .order_by("-at")
        )
        riskactivity = _apply_updated_since_filter(riskactivity, request, "at")
        paginated = _paginate_queryset(riskactivity, request)
        serializer = RiskActivitySerializer(paginated["results"], many=True)

        payload = {"data": serializer.data}
        if paginated["count"] is not None:
            payload["syncedUntil"] = timezone.now().isoformat()
            payload["pagination"] = {
                "page": paginated["page"],
                "pageSize": paginated["page_size"],
                "count": paginated["count"],
                "next": paginated["next"],
                "previous": paginated["previous"],
            }

        return Response(payload)
        
        
class RiskActivityCRUDView(APIView):
    # permission_classes = [IsAuthenticated] 
    
    @swagger_auto_schema(tags = ['RiskActivity'])
    def get(self, request, pk, *args, **kwargs):
        riskactivity = RiskActivity.objects.filter(id = pk).first()
        if riskactivity:
            serializer = RiskActivitySerializer(riskactivity)
            return Response({
                "data":serializer.data
            })
        else:
            return Response({
                "status":status.HTTP_404_NOT_FOUND
            })
            
    # @swagger_auto_schema(tags = ["RiskActivity"])
    # def delete(self, request, pk, *args, **kwargs):
    #     riskactivity = RiskActivity.objects.get(id = pk)
    #     if riskactivity:
    #         riskactivity.delete()
    #         return Response({
    #             "status":status.HTTP_200_OK
    #         })
    #     else:
    #         return Response({
    #             "status":status.HTTP_404_NOT_FOUND
    #         })
            
    # @swagger_auto_schema(request_body=RiskActivitySerializer, tags = ['RiskActivity'])
    # def patch(self, request, pk, *args, **kwargs):
    #     riskactivity = RiskActivity.objects.filter(id =pk).first()
    #     if riskactivity:
    #         serializer = RiskActivitySerializer(instance = riskactivity, data = request.data, partial = True)
    #         if serializer.is_valid():
    #             serializer.save()
    #             return Response({
    #                 "data":serializer.data,
    #                 "status":status.HTTP_200_OK
    #             })
    #         else:
    #             return Response({
    #                 "errors":serializer.errors
    #             })
    #     else:
    #         return Response({
    #             "status":status.HTTP_404_NOT_FOUND
    #         })
            
            
class CreateRiskCommitteeView(APIView):
    # parser_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(request_body=RiskCommitteeSerializer, tags = ['RiskCommittee'])
    def post(self, request, *args, **kwargs):
        serializer = RiskCommitteeSerializer(data = request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "data":serializer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "errors":serializer.errors
            })
            
    @swagger_auto_schema(tags = ['RiskCommittee'])
    def get(self, request, *args, **kwargs):
        data = RiskCommittee.objects.all()
        serializer = RiskCommitteeSerializer(data, many = True)
        return Response({
            "data":serializer.data,
            "status":status.HTTP_200_OK
        })
        
        
class RiskCommitteeCRUDView(APIView):
    # permission_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(tags = ["RiskCommittee"])
    def get(self, request, pk, *args, **kwargs):
        data = RiskCommittee.objects.filter(id = pk).first()
        if data:
            seralizer = RiskCommitteeSerializer(data)
            return Response({
                "data":seralizer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            })
            
    # @swagger_auto_schema(tags = ["RiskCommittee"])
    # def delete(self, request, pk, *args, **kwargs):
    #     data = RiskCommittee.objects.get(id = pk)
    #     if data:
    #         data.delete()
    #         return Response({
    #             "satatus":status.HTTP_200_OK
    #         })
    #     else:
    #         return Response({
    #             "data":"Bunday ma'lumot topilmadi",
    #             "status":status.HTTP_404_NOT_FOUND
    #         })
            
    # @swagger_auto_schema(request_body=RiskCommitteeSerializer, tags = ['RiskCommittee'])
    # def patch(self, request, pk, *args, **kwargs):
    #     data1 = RiskCommittee.objects.filter(id = pk).first()
    #     if data1:
    #         serializer = RiskCommitteeSerializer(instance = data1, data = request.data, partial = True)
    #         if serializer.is_valid():
    #             serializer.save()
    #             return Response({
    #                 "data":serializer.data,
    #                 "status":status.HTTP_200_OK
    #             })
    #         else:
    #             return Response({
    #                 "errors":serializer.errors
    #             })
    #     else:
    #         return Response({
    #             "data":"Bunday ma'lumot topilmadi",
    #             "status":status.HTTP_404_NOT_FOUND
    #         })
            
            
class CreateRiskDecitionView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(request_body=RiskDecisionSerializer, tags = ['RiskDecition'])
    def post(self, request, *args, **kwargs):
        if not has_any_logical_role(request, ["risk-dept", "risk-committee"]):
            return Response({
                "detail": "Only risk department and committee members can create decisions.",
                "status": status.HTTP_403_FORBIDDEN,
            }, status=status.HTTP_403_FORBIDDEN)
        serializer = RiskDecisionSerializer(data = request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "data":serializer.data,
                "status":status.HTTP_201_CREATED
            })
        else:
            return Response({
                "errors":serializer.errors
            })
            
    @swagger_auto_schema(tags = ['RiskDecition'])
    def get(self, request, *args, **kwargs):
        visible_risk_ids = set(_get_scoped_risks_for_request(request).values_list("id", flat=True))
        decisition = (
            RiskDecition.objects.filter(risk_id__in=visible_risk_ids)
            .order_by("-decided_at")
        )
        decisition = _apply_updated_since_filter(decisition, request, "decided_at")
        paginated = _paginate_queryset(decisition, request)
        serializer = RiskDecisionSerializer(paginated["results"], many=True)
        payload = {"data": serializer.data, "status": status.HTTP_200_OK}

        if paginated["count"] is not None:
            payload["syncedUntil"] = timezone.now().isoformat()
            payload["pagination"] = {
                "page": paginated["page"],
                "pageSize": paginated["page_size"],
                "count": paginated["count"],
                "next": paginated["next"],
                "previous": paginated["previous"],
            }

        return Response(payload)
        
        
class RiskDecitionCRUDView(APIView):
    # permission_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(tags = ['RiskDecition'])
    def get(self, request, pk, *args, **kwargs):
        decisition = RiskDecition.objects.filter(id = pk).first()
        if decisition:
            serializer = RiskDecisionSerializer(decisition)
            return Response({
                "data":serializer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            })
            
    # @swagger_auto_schema(tags = ['RiskDecition'])
    # def delete(self, request, pk, *args, **kwargs):
    #     decisition = RiskDecition.objects.filter(id = pk).first()
    #     if decisition:
    #         decisition.delete()
    #         return Response({
    #             "status":status.HTTP_200_OK
    #         })
    #     else:
    #         return Response({
    #             "data":"Bunday ma'lumot topilmadi",
    #             "status":status.HTTP_404_NOT_FOUND
    #         })
            
    # @swagger_auto_schema(request_body=RiskDecisionSerializer, tags = ['RiskDecition'])
    # def patch(self, request, pk, *args, **kwargs):
    #     decisition = RiskDecition.objects.filter(id = pk).first()
    #     if decisition:
    #         serializer = RiskDecisionSerializer(instance = decisition, data = request.data, partial = True)
    #         if serializer.is_valid():
    #             serializer.save()
    #             return Response({
    #                 "data":serializer.data,
    #                 'status':status.HTTP_201_CREATED
    #             })
    #         else:
    #             return Response({
    #                 "errors":serializer.errors
    #             })
    #     else:
    #         return Response({
    #             "data":"Bunday ma'lumot topilmadi",
    #             "status":status.HTTP_404_NOT_FOUND
    #         })
            
            
class CreateMitigationView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(request_body=MitigationSerializer, tags = ['Mitigation'])
    def post(self, request, *args, **kwargs):
        risk_id = request.data.get("risk")
        risk = Risk.objects.select_related("responsible_department_id", "department").filter(id=risk_id).first()
        if not risk:
            return Response({
                "errors": {"risk": ["Risk not found."]},
            }, status=status.HTTP_400_BAD_REQUEST)

        if not has_any_logical_role(request, ["risk-dept", "risk-committee", "dept-director"]):
            return Response({
                "detail": "Only risk department, risk committee, and department directors can create mitigation actions.",
                "status": status.HTTP_403_FORBIDDEN,
            }, status=status.HTTP_403_FORBIDDEN)

        if has_logical_role(request, "dept-director") and not _is_risk_related_department_director(request, risk):
            return Response({
                "detail": "Department directors can only create mitigation actions for their own department.",
                "status": status.HTTP_403_FORBIDDEN,
            }, status=status.HTTP_403_FORBIDDEN)

        mutable_data = request.data.copy()
        mutable_data["status"] = mutable_data.get("status") or "NOT_STARTED"
        actor = _request_actor_label(request)

        serialzier = MitigationSerializer(data = mutable_data)
        if serialzier.is_valid():
            mitigation = serialzier.save(
                department_director=actor,
                created_by=actor,
            )
            notify_mitigation_create(mitigation)
            _ensure_mitigation_risk_in_progress(
                mitigation,
                actor,
                notes="Mitigation action created.",
            )
            _log_mitigation_activity(
                mitigation,
                actor,
                "Mitigation action created",
                notes=mutable_data.get("notes", "") or "",
                activity_type="ASSIGNMENT",
            )
            return Response({
                "data":serialzier.data,
                "status":status.HTTP_201_CREATED
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                "errors":serialzier.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    @swagger_auto_schema(tags = ['Mitigation'])
    def get(self, request, *args, **kwargs):
        risk_ids = _scoped_risk_queryset(request).values_list("id", flat=True)
        mitigation = (
            Mitigation.objects
            .select_related("risk", "risk__responsible_department_id", "risk__department")
            .filter(risk_id__in=risk_ids)
            .order_by("-updated_at", "-id")
        )
        mitigation = _apply_updated_since_filter(mitigation, request, "updated_at")
        paginated = _paginate_queryset(mitigation, request)
        seralizer = MitigationSerializer(paginated["results"], many=True)
        payload = {"data": seralizer.data, "status": status.HTTP_200_OK}

        if paginated["count"] is not None:
            payload["syncedUntil"] = timezone.now().isoformat()
            payload["pagination"] = {
                "page": paginated["page"],
                "pageSize": paginated["page_size"],
                "count": paginated["count"],
                "next": paginated["next"],
                "previous": paginated["previous"],
            }

        return Response(payload)
        

class MitigationCRUDView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(tags = ['Mitigation'])
    def get(self, request, pk, *args, **kwargs):
        mitigation = Mitigation.objects.filter(id = pk).first()
        if mitigation:
            if not _can_view_mitigation(request, mitigation):
                return Response({
                    "detail": "You do not have access to this mitigation action.",
                    "status": status.HTTP_403_FORBIDDEN,
                }, status=status.HTTP_403_FORBIDDEN)
            serializer = MitigationSerializer(mitigation)
            return Response({
                "data":serializer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            })
            
    @swagger_auto_schema(tags = ['Mitigation'])
    def delete(self, request, pk, *args, **kwargs):
        if not has_any_logical_role(request, ["risk-dept", "dept-director"]):
            return Response({
                "detail": "You do not have permission to delete mitigation actions.",
                "status": status.HTTP_403_FORBIDDEN,
            }, status=status.HTTP_403_FORBIDDEN)
        mitigation = Mitigation.objects.filter(id = pk).first()
        if mitigation:
            if has_logical_role(request, "dept-director") and not _is_mitigation_department_director(request, mitigation):
                return Response({
                    "detail": "Department directors can only delete mitigation actions in their own department.",
                    "status": status.HTTP_403_FORBIDDEN,
                }, status=status.HTTP_403_FORBIDDEN)
            mitigation.delete()
            return Response({
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            })
    
    @swagger_auto_schema(request_body=MitigationSerializer, tags = ['Mitigation'])
    def patch(self, request, pk, *args, **kwargs):
        mitigation = Mitigation.objects.select_related("risk", "risk__responsible_department_id", "risk__department").get(id = pk)
        if mitigation:
            is_risk_dept = has_logical_role(request, "risk-dept")
            is_dept_director = has_logical_role(request, "dept-director")
            requested_status = _normalize_status_token(request.data.get("status"))

            if not is_risk_dept and not is_dept_director:
                return Response({
                    "detail": "You do not have permission to manage mitigation actions.",
                    "status": status.HTTP_403_FORBIDDEN,
                }, status=status.HTTP_403_FORBIDDEN)

            if is_dept_director and not _is_mitigation_department_director(request, mitigation):
                return Response({
                    "detail": "Department directors can only manage mitigation actions in their own department.",
                    "status": status.HTTP_403_FORBIDDEN,
                }, status=status.HTTP_403_FORBIDDEN)

            if is_dept_director and _normalize_status_token(mitigation.status) in {MITIGATION_REVIEWABLE_STATUS, MITIGATION_APPROVED_STATUS}:
                return Response({
                    "detail": "This mitigation action is locked while it is under risk review or already approved.",
                    "status": status.HTTP_400_BAD_REQUEST,
                }, status=status.HTTP_400_BAD_REQUEST)

            if requested_status == "NOT_STARTED" and _normalize_status_token(mitigation.status) != "NOT_STARTED":
                return Response({
                    "detail": "A mitigation action cannot be moved back to Not Started after work has begun.",
                    "status": status.HTTP_400_BAD_REQUEST,
                }, status=status.HTTP_400_BAD_REQUEST)

            if is_dept_director and requested_status == MITIGATION_APPROVED_STATUS:
                return Response({
                    "detail": "Department directors cannot approve mitigation actions.",
                    "status": status.HTTP_403_FORBIDDEN,
                }, status=status.HTTP_403_FORBIDDEN)

            if is_risk_dept and requested_status == "IN_PROGRESS" and _normalize_status_token(mitigation.status) == MITIGATION_REVIEWABLE_STATUS:
                if not str(request.data.get("notes", "") or "").strip():
                    return Response({
                        "errors": {"notes": ["A decline comment is required."]},
                    }, status=status.HTTP_400_BAD_REQUEST)

            if is_risk_dept and requested_status == MITIGATION_APPROVED_STATUS and _normalize_status_token(mitigation.status) != MITIGATION_REVIEWABLE_STATUS:
                return Response({
                    "detail": "Only mitigation actions pending risk review can be approved.",
                    "status": status.HTTP_400_BAD_REQUEST,
                }, status=status.HTTP_400_BAD_REQUEST)

            old_mitigation = Mitigation.objects.get(id=pk)
            serializer = MitigationSerializer(instance = mitigation, data = request.data, partial = True)
            if serializer.is_valid():
                actor = _request_actor_label(request)
                save_kwargs = {}
                if is_risk_dept and requested_status == "IN_PROGRESS" and _normalize_status_token(old_mitigation.status) == MITIGATION_REVIEWABLE_STATUS:
                    save_kwargs["completed_by"] = ""
                    save_kwargs["completed_at"] = None

                updated_mitigation = serializer.save(**save_kwargs)
                notify_mitigation_update(old_mitigation, updated_mitigation)

                if is_risk_dept and requested_status == MITIGATION_APPROVED_STATUS:
                    _log_mitigation_activity(
                        updated_mitigation,
                        actor,
                        "Mitigation action approved",
                        notes=str(request.data.get("notes", "") or "").strip(),
                    )
                elif is_risk_dept and requested_status == "IN_PROGRESS" and _normalize_status_token(old_mitigation.status) == MITIGATION_REVIEWABLE_STATUS:
                    _ensure_mitigation_risk_in_progress(
                        updated_mitigation,
                        actor,
                        notes="Mitigation work resumed after a risk department decline.",
                    )
                    _log_mitigation_activity(
                        updated_mitigation,
                        actor,
                        "Mitigation action declined",
                        notes=str(request.data.get("notes", "") or "").strip(),
                    )
                elif is_dept_director:
                    _log_mitigation_activity(
                        updated_mitigation,
                        actor,
                        "Mitigation action updated",
                        notes=str(request.data.get("notes", "") or "").strip(),
                        activity_type="UPDATE",
                    )

                return Response({
                    "data":serializer.data,
                    "status":status.HTTP_200_OK
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "errors":serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            }, status=status.HTTP_404_NOT_FOUND)
            
            
class StaffRiskMitigationCRYDView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(request_body=MitigationSerializer, tags = ['Mitigation'])
    def patch(self, request, pk, *args, **kwargs):
        mitigation = Mitigation.objects.select_related("risk", "risk__responsible_department_id", "risk__department").get(id = pk)
        if mitigation:
            is_owner = _is_mitigation_owner(request, mitigation)
            is_dept_director = _is_mitigation_department_director(request, mitigation)

            if not is_owner and not is_dept_director:
                return Response({
                    "detail": "Only the assigned mitigation owner or the mitigation department director can update this action.",
                    "status": status.HTTP_403_FORBIDDEN,
                }, status=status.HTTP_403_FORBIDDEN)

            if _normalize_status_token(mitigation.status) in {MITIGATION_REVIEWABLE_STATUS, MITIGATION_APPROVED_STATUS}:
                return Response({
                    "detail": "This mitigation action cannot be edited while it is under review or already approved.",
                    "status": status.HTTP_400_BAD_REQUEST,
                }, status=status.HTTP_400_BAD_REQUEST)

            requested_status = _normalize_status_token(request.data.get("status"))
            if requested_status == "NOT_STARTED" and _normalize_status_token(mitigation.status) != "NOT_STARTED":
                return Response({
                    "detail": "A mitigation action cannot be moved back to Not Started after work has begun.",
                    "status": status.HTTP_400_BAD_REQUEST,
                }, status=status.HTTP_400_BAD_REQUEST)
            if requested_status and requested_status not in MITIGATION_PERFORMER_EDITABLE_STATUSES | {MITIGATION_REVIEWABLE_STATUS}:
                return Response({
                    "detail": "Assigned staff can only move mitigation actions to In Progress or Pending Risk Review.",
                    "status": status.HTTP_400_BAD_REQUEST,
                }, status=status.HTTP_400_BAD_REQUEST)

            if requested_status == MITIGATION_REVIEWABLE_STATUS and not str(request.data.get("notes", "") or "").strip():
                return Response({
                    "errors": {"notes": ["A completion comment is required before sending mitigation for review."]},
                }, status=status.HTTP_400_BAD_REQUEST)

            old_mitigation = Mitigation.objects.get(id=pk)
            serializer = MitigationSerializer(instance = mitigation, data = request.data, partial = True)
            if serializer.is_valid():
                actor = _request_actor_label(request)
                save_kwargs = {}
                if requested_status == MITIGATION_REVIEWABLE_STATUS:
                    save_kwargs["completed_by"] = actor
                    save_kwargs["completed_at"] = timezone.now()

                updated_mitigation = serializer.save(**save_kwargs)
                notify_mitigation_update(old_mitigation, updated_mitigation)

                if requested_status == MITIGATION_REVIEWABLE_STATUS:
                    _ensure_mitigation_risk_in_progress(
                        updated_mitigation,
                        actor,
                        notes="Mitigation action submitted for risk department review.",
                    )
                    _log_mitigation_activity(
                        updated_mitigation,
                        actor,
                        "Mitigation action submitted for review",
                        notes=str(request.data.get("notes", "") or "").strip(),
                    )
                elif requested_status in MITIGATION_PERFORMER_EDITABLE_STATUSES:
                    _ensure_mitigation_risk_in_progress(
                        updated_mitigation,
                        actor,
                        notes="Mitigation work updated.",
                    )
                    _log_mitigation_activity(
                        updated_mitigation,
                        actor,
                        "Mitigation action updated",
                        notes=str(request.data.get("notes", "") or "").strip(),
                        activity_type="UPDATE",
                    )

                return Response({
                    "data":serializer.data,
                    "status":status.HTTP_200_OK
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "errors":serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            }, status=status.HTTP_404_NOT_FOUND)
            
            
class GetRiskMitigationView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(tags = ['Filters'])
    def get(self, request, pk, *args, **kwargs):
        risk = _scoped_risk_queryset(request).filter(id=pk).only("id").first()
        if not risk:
            return Response({
                "data": "Bunday ma'lumot topilmadi",
                "status": status.HTTP_404_NOT_FOUND
            }, status=status.HTTP_404_NOT_FOUND)

        mitigations = Mitigation.objects.select_related(
            "risk",
            "risk__responsible_department_id",
            "risk__department",
        ).filter(risk_id=pk)
        serializer = MitigationSerializer(mitigations, many =True)
        return Response({
            "data":serializer.data,
            "status":status.HTTP_200_OK
        })
        

class FilterRiskByStatusView(APIView):
    # permission_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(request_body=StatusSerializer, tags = ['Filters'])
    def post(self, request, *args, **kwargs):
        requested_status = _normalize_status_token(request.data.get("status"))
        if not requested_status:
            return Response({
                "data": "Invalid or missing status",
                "status": status.HTTP_400_BAD_REQUEST,
            }, status=status.HTTP_400_BAD_REQUEST)

        risk = (
            _scoped_risk_queryset(request)
            .filter(status = requested_status)
            .order_by("-updated_at", "-id")
        )
        risk = _apply_updated_since_filter(risk, request, "updated_at")
        paginated = _paginate_queryset(risk, request)

        if not paginated["results"]:
            return Response({
                "data": "Bunday ma'lumot topilmadi",
                "status": status.HTTP_404_NOT_FOUND
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = RiskSerializer(paginated["results"], many = True)
        payload = {"data": serializer.data, "status": status.HTTP_200_OK}

        if paginated["count"] is not None:
            payload["syncedUntil"] = timezone.now().isoformat()
            payload["pagination"] = {
                "page": paginated["page"],
                "pageSize": paginated["page_size"],
                "count": paginated["count"],
                "next": paginated["next"],
                "previous": paginated["previous"],
            }

        return Response(payload)
            
            
class UpcomingRiskAPIView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        today = timezone.now()
        ten_days_later = today + timedelta(days=10)
        risks = _scoped_risk_queryset(request).filter(
            status__in=["OPEN", "IN_PROGRESS", "MITIGATED", "ACCEPTED"],
            due_date__gte=today,
            due_date__lte=ten_days_later
        ).order_by("due_date")
        risks = _apply_updated_since_filter(risks, request, "updated_at")
        paginated = _paginate_queryset(risks, request)
        serializer = RiskSerializer(paginated["results"], many=True)
        payload = {
            "count": paginated["count"] or risks.count(),
            "data": serializer.data,
            "syncedUntil": timezone.now().isoformat(),
        }

        if paginated["count"] is not None:
            payload["pagination"] = {
                "page": paginated["page"],
                "pageSize": paginated["page_size"],
                "count": paginated["count"],
                "next": paginated["next"],
                "previous": paginated["previous"],
            }
            payload["data"] = serializer.data

        return Response(payload, status=status.HTTP_200_OK)
        
        
class ReplyRiskActivityCreateView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(request_body=ReplyRiskActivitySerializer, tag = ['ReplyRiskActivity'])
    def post(self, request, *args, **kwargs):
        serializer = ReplyRiskActivitySerializer(data = request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "data":serializer.data,
                "status":status.HTTP_201_CREATED
            })
        else:
            return Response({
                "errors":serializer.errors,
                "status":status.HTTP_400_BAD_REQUEST
            })
        
    @swagger_auto_schema(tag = ['ReplyRiskActivity'])        
    def get(self, request, *args, **kwargs):
        data = ReplyRiskActivity.objects.all()
        serializer = ReplyRiskActivitySerializer(data, many=True)
        return Response({
            "data":serializer.data,
            "status":status.HTTP_200_OK
        })
        
        
class ReplyRiskActivityCRUDView(APIView):
    # permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(tag = ['ReplyRiskActivity'])
    def get(self, request, pk, *args, **kwargs):
        data1 = ReplyRiskActivity.objects.filter(id = pk).first()
        if data1:
            serializer = ReplyRiskActivitySerializer(data = data1)
            return Response({
                "data":serializer.data,
                'status':status.HTTP_200_OK
            })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_400_BAD_REQUEST
            })
            
    # @swagger_auto_schema(tag = ['ReplyRiskActivity'])
    # def delete(self, request, pk, *args, **kwargs):
    #     data = ReplyRiskActivity.objects.filter(id = pk).first()
    #     if data:
    #         data.delete()
    #         return Response({
    #             "data":"Ma'lumot muvaffaqiyatli o'chirildi",
    #             'status':status.HTTP_200_OK
    #         })
    #     else:
    #         return Response({
    #             "data":"Bunday ma'lumot topilmadi",
    #             "status":status.HTTP_400_BAD_REQUEST
    #         })
            
    @swagger_auto_schema(request_body=ReplyRiskActivitySerializer, tag = ['ReplyRiskActivity'])
    def patch(self, request, pk, *args, **kwargs):
        data1 = ReplyRiskActivity.objects.filter(id = pk).first()
        if data1:
            serializer = ReplyRiskActivitySerializer(instance = data1, data = request.data, partial = True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "data":serializer.data,
                    'status':status.HTTP_200_OK
                })
            else:
                return Response({
                    "errors":serializer.errors,
                    'status':status.HTTP_400_BAD_REQUEST
                })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_400_BAD_REQUEST
            })
            

class AddRecipientToRiskView(APIView):
    
    @swagger_auto_schema(tags=["RiskActivity"])
    def post(self, request, pk):
        risk = get_object_or_404(Risk, pk=pk)
        new_user = request.data.get("user")

        if not new_user:
            return Response(
                {"error": "user field is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        recipient = add_user_to_risk_activity(
            risk=risk,
            new_user=new_user,
            actor=request.user  
        )

        if not recipient:
            return Response(
                {"error": "RiskActivity not found for this risk"},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {"message": f"{new_user} added to risk activity"},
            status=status.HTTP_200_OK
        )
        
        
class UpdateRiskView(APIView):
    
    @swagger_auto_schema(request_body=RiskSerializer, tags=["Risk"])
    def put(self, request, pk):
        risk = get_object_or_404(Risk, pk=pk)
        serializer = RiskSerializer(
            risk,
            data=request.data,
            partial=True,
            context={"request": request},
        )

        if serializer.is_valid():
            updated_risk = serializer.save()

            create_risk_activity_and_notify(
                risk=updated_risk,
                actor=request.user,
                action_type="UPDATE",
                notes="Risk updated"
            )

            extra_users = request.data.get("extra_recipients", [])
            for user in extra_users:
                add_user_to_risk_activity(
                    risk=updated_risk,
                    new_user=user,
                    actor=request.user
                )

            return Response(
                {"data": serializer.data},
                status=status.HTTP_200_OK
            )

        return Response(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
        
        
class AssignRiskView(APIView):
    
    @swagger_auto_schema(tags=["Risk"])
    def post(self, request, pk):
        risk = get_object_or_404(Risk, pk=pk)
        assigned_user = request.data.get("user")

        if not assigned_user:
            return Response(
                {"error": "user field is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        add_user_to_risk_activity(
            risk=risk,
            new_user=assigned_user,
            actor=request.user
        )

        create_risk_activity_and_notify(
            risk=risk,
            actor=request.user,
            action_type="ASSIGNMENT",
            notes=f"{assigned_user} assigned to risk"
        )

        return Response(
            {"message": f"{assigned_user} assigned and notified"},
            status=status.HTTP_200_OK
        )
        
        

class GetTokenView(APIView):
    """
    Frontend bu endpoint'ni ishlatmaydi — to'g'ridan-to'g'ri
    Keycloak'dan token oladi. Bu faqat test/debug uchun.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "username va password majburiy"},
                status=400
            )

        data = {
            "grant_type": "password",
            "client_id": settings.KEYCLOAK_CLIENT_ID,
            "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
            "username": username,
            "password": password,
        }

        try:
            response = requests.post(
                settings.KEYCLOAK_TOKEN_URL,
                data=data,
                timeout=10
            )
        except requests.RequestException as e:
            return Response(
                {"error": f"Keycloak server'ga ulanib bo'lmadi: {str(e)}"},
                status=503
            )

        # Keycloak xatolik qaytarsa
        if response.status_code != 200:
            return Response(
                {"error": "Login muvaffaqiyatsiz", "detail": response.json()},
                status=response.status_code
            )

        return Response(response.json())


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        payload = request.auth or {}

        cache_key = ME_PROFILE_CACHE_KEY.format(user_id=getattr(user, "id", "anonymous"))
        cached_profile = cache.get(cache_key)
        if isinstance(cached_profile, dict):
            return Response(cached_profile)

        user_data = UserSerializer(user).data
        # Keycloak'dan kelgan qo'shimcha ma'lumotlar
        user_data["roles"] = payload.get("realm_access", {}).get("roles", [])
        user_data["keycloak_id"] = payload.get("sub")
        user_data["groups"] = get_user_group_paths(payload)

        try:
            department = resolve_user_department(payload, sync=True)
            user_data["department_id"] = department.id if department else None
            user_data["department_name"] = department.name if department else None
            user_data["department"] = (
                DepartmentSerializer(department).data if department else None
            )
        except DepartmentResolutionError as exc:
            user_data["department_id"] = None
            user_data["department_name"] = None
            user_data["department"] = None
            user_data["department_error"] = str(exc)

        cache.set(cache_key, user_data, ME_PROFILE_CACHE_TTL)
        return Response(user_data)


class DepartmentMemberDirectoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_logical_role(request, "dept-director"):
            return Response({
                "detail": "Only department directors can view department members.",
                "status": status.HTTP_403_FORBIDDEN,
            }, status=status.HTTP_403_FORBIDDEN)

        payload = request.auth or {}

        try:
            department = resolve_user_department(payload, sync=True)
        except DepartmentResolutionError as exc:
            return Response({
                "detail": str(exc),
                "status": status.HTTP_400_BAD_REQUEST,
            }, status=status.HTTP_400_BAD_REQUEST)

        if department is None:
            return Response({
                "detail": "Unable to determine your department from Keycloak groups.",
                "status": status.HTTP_400_BAD_REQUEST,
            }, status=status.HTTP_400_BAD_REQUEST)

        if not department.keycloak_group_id:
            sync_departments_from_keycloak(force=True)
            department.refresh_from_db()

        if not department.keycloak_group_id:
            return Response({
                "detail": "The current department is not linked to a Keycloak group.",
                "status": status.HTTP_400_BAD_REQUEST,
            }, status=status.HTTP_400_BAD_REQUEST)

        directory_cache_key = DIRECTORY_MEMBERS_CACHE_KEY.format(department_id=department.id)
        cached_members = cache.get(directory_cache_key)
        if cached_members is not None and isinstance(cached_members, list):
            return Response({
                "data": cached_members,
                "status": status.HTTP_200_OK,
            })

        try:
            members = _fetch_group_members(department.keycloak_group_id)
        except DepartmentResolutionError as exc:
            return Response({
                "detail": str(exc),
                "status": status.HTTP_400_BAD_REQUEST,
            }, status=status.HTTP_400_BAD_REQUEST)

        request_identities = _request_identity_candidates(request)
        seen_usernames = set()
        directory_members = []

        for member in members:
            username = str(member.get("username") or "").strip()
            email = str(member.get("email") or "").strip()
            keycloak_id = str(member.get("id") or "").strip()

            if not username or username.startswith("service-account-"):
                continue

            member_identities = {
                _normalize_identity_value(username),
                _normalize_identity_value(email),
                _normalize_identity_value(keycloak_id),
            }
            member_identities.discard("")

            if request_identities & member_identities:
                continue

            normalized_username = _normalize_identity_value(username)
            if normalized_username in seen_usernames:
                continue

            seen_usernames.add(normalized_username)
            directory_members.append({
                "id": keycloak_id or username,
                "keycloak_id": keycloak_id or None,
                "username": username,
                "email": email,
                "first_name": str(member.get("firstName") or "").strip(),
                "last_name": str(member.get("lastName") or "").strip(),
                "full_name": _directory_member_label(member),
                "name": _directory_member_label(member),
                "department_id": department.id,
                "department_name": department.name,
                "department": DepartmentSerializer(department).data,
                "is_active": bool(member.get("enabled", True)),
            })

        directory_members.sort(key=lambda item: item["name"].lower())

        cache.set(directory_cache_key, directory_members, DIRECTORY_MEMBERS_CACHE_TTL)

        return Response({
            "data": directory_members,
            "status": status.HTTP_200_OK,
        })
