from .models import (Department, Risk, RiskCommittee, Mitigation, 
                     RiskDecition, RiskActivity, Category, ReplyRiskActivity)
from rest_framework import serializers
from django.contrib.auth.models import User

from app.services.keycloak_departments import DepartmentResolutionError, resolve_user_department


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "is_staff",
            "is_active",
            "is_superuser",
            "date_joined",
            "last_login",
        ]
        # Parol va xavfsiz fieldlarni hech qachon qaytarmaymiz
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.get_full_name()


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = [
            'id',
            "name",
            "code",
        ]
        

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            'id',
            "name",
            "code",
        ]
        

class RiskSerializer(serializers.ModelSerializer):
    created_by_user_id = serializers.CharField(read_only=True)
    created_by_department_id = serializers.CharField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    responsible_department_name = serializers.CharField(
        source="responsible_department_id.name",
        read_only=True,
    )

    class Meta:
        model = Risk
        fields = '__all__'
        extra_kwargs = {
            "responsible": {"allow_blank": True, "required": False},
            "risk_manager": {"allow_blank": True, "required": False},
            "risk_derector": {"allow_blank": True, "required": False},
            "owner": {"allow_blank": True, "required": False},
        }

    def create(self, validated_data):
        request = self.context.get("request")
        payload = request.auth or {} if request else {}
        user = request.user if request else None

        if user and getattr(user, "is_authenticated", False):
            validated_data["created_by_user_id"] = (
                payload.get("preferred_username")
                or getattr(user, "username", "")
                or payload.get("sub", "")
            )

            try:
                department = resolve_user_department(payload, sync=True)
            except DepartmentResolutionError as exc:
                raise serializers.ValidationError(
                    {"created_by_department_id": str(exc)}
                )

            if department is None:
                requested_department = validated_data.get("department") or validated_data.get("responsible_department_id")
                if requested_department:
                    department = requested_department

            if department is None:
                raise serializers.ValidationError(
                    {
                        "created_by_department_id": (
                            "Unable to determine the creator department from Keycloak groups."
                        )
                    }
                )

            validated_data["created_by_department_id"] = str(department.id)

        return super().create(validated_data)
        
        
class RiskCommitteeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskCommittee
        fields = "__all__"
        
        
class MitigationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mitigation
        fields = "__all__"
        
        
class RiskDecisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskDecition
        fields = "__all__"
        
        
class RiskActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskActivity
        fields = "__all__"
        

class StatusSerializer(serializers.Serializer):
    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In Progress"),
        ("MITIGATED", "Mitigated"),
        ("ACCEPTED", "Accepted"),
        ("CLOSED", "Closed"),
    ]

    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    

class ReplyRiskActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ReplyRiskActivity
        fields = "__all__"
