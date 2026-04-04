from datetime import timedelta
import re
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
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


def _request_identity_candidates(request):
    payload = request.auth or {}
    user = request.user
    given_name = str(payload.get("given_name") or "").strip()
    family_name = str(payload.get("family_name") or "").strip()
    full_name = " ".join(part for part in [given_name, family_name] if part).strip()
    values = [
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

    return {
        _normalize_identity_value(value)
        for value in values
        if value is not None and _normalize_identity_value(value)
    }


def _is_risk_creator(request, risk):
    creator_value = _normalize_identity_value(getattr(risk, "created_by_user_id", ""))
    return bool(creator_value) and creator_value in _request_identity_candidates(request)


def _request_actor_label(request):
    payload = request.auth or {}
    user = request.user
    return (
        payload.get("preferred_username")
        or getattr(user, "username", None)
        or payload.get("email")
        or "System"
    )


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
    payload = request.auth or {}
    values = [
        payload.get("department"),
        payload.get("dept"),
        payload.get("org_unit"),
        payload.get("organization"),
        payload.get("division"),
    ]
    group_paths = get_user_group_paths(payload)
    values.extend(group_paths)
    values.extend(
        path.rsplit("/", 1)[-1]
        for path in group_paths
        if isinstance(path, str) and path.strip()
    )

    try:
        department = resolve_user_department(payload, sync=False)
    except DepartmentResolutionError:
        department = None

    if department:
        values.extend(_department_identity_candidates(department))

    candidates = set()
    for value in values:
        normalized = _normalize_identity_value(value)
        canonical = canonical_department_key(value)
        if normalized:
            candidates.add(normalized)
        if canonical:
            candidates.add(canonical)
    return candidates


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


def _is_risk_related_department_director(request, risk):
    if not has_logical_role(request, "dept-director"):
        return False

    request_departments = _request_department_candidates(request)

    try:
        request_department = resolve_user_department(request.auth or {}, sync=False)
    except DepartmentResolutionError:
        request_department = None

    if request_department:
        request_departments.update(_department_identity_candidates(request_department))

    risk_departments = set()
    prioritized_departments = [
        getattr(risk, "responsible_department_id", None),
        getattr(risk, "department", None),
    ]

    for department in prioritized_departments:
        if department:
            risk_departments.update(_department_identity_candidates(department))

    return bool(request_departments & risk_departments)


def _has_risk_mitigation_assignment(request, risk):
    identities = _request_identity_candidates(request)
    if not identities:
        return False

    for mitigation in getattr(risk, "mitigations", []).all():
        if _normalize_identity_value(mitigation.owner) in identities:
            return True

    return False


def _can_view_risk(request, risk):
    if has_any_logical_role(request, ["super-admin", "risk-dept", "risk-committee"]):
        return True

    if _is_risk_creator(request, risk):
        return True

    if _normalize_identity_value(getattr(risk, "responsible", "")) in _request_identity_candidates(request):
        return True

    if _is_risk_related_department_director(request, risk):
        return True

    if _has_risk_mitigation_assignment(request, risk):
        return True

    return False


def _scoped_risk_queryset():
    return Risk.objects.select_related(
        "department",
        "category",
        "responsible_department_id",
    ).prefetch_related(
        Prefetch("mitigations", queryset=Mitigation.objects.only("id", "risk_id", "owner"))
    )


def _get_scoped_risks_for_request(request):
    risks = _scoped_risk_queryset()
    if has_any_logical_role(request, ["super-admin", "risk-dept", "risk-committee"]):
        return risks
    return [risk for risk in risks if _can_view_risk(request, risk)]


def _is_mitigation_owner(request, mitigation):
    return _normalize_identity_value(getattr(mitigation, "owner", "")) in _request_identity_candidates(request)


def _is_mitigation_department_director(request, mitigation):
    return _is_risk_related_department_director(request, mitigation.risk)


def _can_view_mitigation(request, mitigation):
    return _can_view_risk(request, mitigation.risk) or _is_mitigation_owner(request, mitigation)


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


class DepartmentView(APIView):
    permission_classes = [IsAuthenticated, IsReadOnlyOrSuperAdmin]
    
    @swagger_auto_schema(request_body=DepartmentSerializer, tags = ['Department'])
    def post(self, request, *args, **kwargs):
        serializer = DepartmentSerializer(data = request.data)
        if serializer.is_valid():
            instance = serializer.save()
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
        return Response({
            "data":serializer.data,
            "status":status.HTTP_200_OK
        })
        

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
        departments = Category.objects.all()
        serializer = CategorySerializer(departments, many = True)
        return Response({
            "data":serializer.data,
            "status":status.HTTP_200_OK
        })
        

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
        risk = _get_scoped_risks_for_request(request)
        serializer = RiskSerializer(risk, many = True)
        return Response({
            "data":serializer.data
        })
        
        
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
                }
                requested_fields = set(request.data.keys())
                allowed = (
                    requested_fields.issubset(director_editable_fields)
                    and _is_risk_related_department_director(request, risk)
                    and _normalize_status_token(risk.status) in MITIGATION_STAGE_RISK_STATUSES
                )
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
        visible_risk_ids = {risk.id for risk in _get_scoped_risks_for_request(request)}
        riskactivity = RiskActivity.objects.filter(risk_id__in=visible_risk_ids)
        serializer = RiskActivitySerializer(riskactivity, many = True)
        return Response({
            "data":serializer.data
        })
        
        
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
        visible_risk_ids = {risk.id for risk in _get_scoped_risks_for_request(request)}
        decisition = RiskDecition.objects.filter(risk_id__in=visible_risk_ids)
        serializer = RiskDecisionSerializer(decisition, many = True)
        return Response({
            "data":serializer.data,
            "status":status.HTTP_200_OK
        })
        
        
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
        mutable_data["department_director"] = mutable_data.get("department_director") or _request_actor_label(request)
        mutable_data["status"] = mutable_data.get("status") or "NOT_STARTED"

        serialzier = MitigationSerializer(data = mutable_data)
        if serialzier.is_valid():
            mitigation = serialzier.save()
            notify_mitigation_create(mitigation)
            _ensure_mitigation_risk_in_progress(
                mitigation,
                _request_actor_label(request),
                notes="Mitigation action created.",
            )
            _log_mitigation_activity(
                mitigation,
                _request_actor_label(request),
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
        mitigation = [
            item for item in Mitigation.objects.select_related("risk", "risk__responsible_department_id", "risk__department").all()
            if _can_view_mitigation(request, item)
        ]
        seralizer = MitigationSerializer(mitigation, many =True)
        return Response({
            "data":seralizer.data,
            "status":status.HTTP_200_OK
        })
        

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
                updated_mitigation = serializer.save()
                notify_mitigation_update(old_mitigation, updated_mitigation)

                actor = _request_actor_label(request)
                if is_risk_dept and requested_status == MITIGATION_APPROVED_STATUS:
                    _log_mitigation_activity(
                        updated_mitigation,
                        actor,
                        "Mitigation action approved",
                        notes=str(request.data.get("notes", "") or "").strip(),
                    )
                    _advance_risk_to_committee_review_2_if_ready(updated_mitigation.risk, actor)
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
                updated_mitigation = serializer.save()
                notify_mitigation_update(old_mitigation, updated_mitigation)

                actor = _request_actor_label(request)
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
        mitigations = [
            item for item in Mitigation.objects.select_related("risk", "risk__responsible_department_id", "risk__department").filter(risk_id = pk)
            if _can_view_mitigation(request, item)
        ]
        serializer = MitigationSerializer(mitigations, many =True)
        return Response({
            "data":serializer.data,
            "status":status.HTTP_200_OK
        })
        

class FilterRiskByStatusView(APIView):
    # permission_classes = [IsAuthenticated, ]
    
    @swagger_auto_schema(request_body=StatusSerializer, tags = ['Filters'])
    def post(self, request, *args, **kwargs):
        risk = Risk.objects.filter(status = request.data.get("status"))
        if risk:
            serializer = RiskSerializer(risk, many = True)
            return Response({
                "data":serializer.data,
                "status":status.HTTP_200_OK
            })
        else:
            return Response({
                "data":"Bunday ma'lumot topilmadi",
                "status":status.HTTP_404_NOT_FOUND
            })
            
            
class UpcomingRiskAPIView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        today = timezone.now()
        ten_days_later = today + timedelta(days=10)
        risks = Risk.objects.filter(
            status__in=["OPEN", "IN_PROGRESS", "MITIGATED", "ACCEPTED"],
            due_date__gte=today,
            due_date__lte=ten_days_later
        ).order_by("due_date") 
        serializer = RiskSerializer(risks, many=True)
        return Response(
            {
                "count": risks.count(),
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )
        
        
class ReplyRiskActivityCreateView(APIView):
    # permission_classes = [IsAuthenticated]
    
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

        return Response({
            "data": directory_members,
            "status": status.HTTP_200_OK,
        })
