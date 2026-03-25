from rest_framework import serializers
from .models import Department, Risk, RiskCommittee, Mitigation, RiskDecition, RiskActivity, Category

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = [
            'id',
            "name",
        ]
        

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            'id',
            "name",
        ]
        

class RiskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Risk
        fields = [
            'id',
            "title",
            "description",
            "category",
            "department",
            "owner",
            "responsible",
            "created_by_user_id",
            "created_by_department_id",
            "status",
            "probability",
            "impact_min",
            "impact_most_likely",
            "impact_max",
            "expected_loss",
            "severity",
            "inherent_score",
            "residual_score",
            "created_at",
            "updated_at",
            "due_date",
            "last_reviewed_at",
            "tags",
            "attachments",
            "existing_controls_text",
            "planned_controls_text",
        ]
        
        
class RiskCommitteeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskCommittee
        fields = [
            'id',
            "last_decition",
            "last_decition_at",
            "risk",
        ]
        
        
class MitigationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mitigation
        fields = [
            'id',
            "risk",
            "title",
            "owner",
            "due_date",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
        
        
class RiskDecisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskDecition
        fields = [
            'id',
            "risk",
            "decition_type",
            "decided_by",
            "decided_at",
            "notes",
        ]
        
        
class RiskActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskActivity
        fields = [
            'id',
            "risk",
            "type",
            "title",
            "notes",
            "by",
            "at",
            "diff",
        ]
        

class StatusSerializer(serializers.Serializer):
    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In Progress"),
        ("MITIGATED", "Mitigated"),
        ("ACCEPTED", "Accepted"),
        ("CLOSED", "Closed"),
    ]

    status = serializers.ChoiceField(choices=STATUS_CHOICES)