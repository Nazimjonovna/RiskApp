from rest_framework import serializers
from .models import Department, Risk, RiskCommittee, Mitigation, RiskDecision, RiskActivity

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = [
            "name",
        ]
        

class RiskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Risk
        fields = [
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
            "last_decision",
            "last_decision_at",
            "risk",
        ]
        
        
class MitigationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mitigation
        fields = [
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
        model = RiskDecision
        fields = [
            "risk",
            "decision_type",
            "decided_by",
            "decided_at",
            "notes",
        ]
        
        
class RiskActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskActivity
        fields = [
            "risk",
            "type",
            "title",
            "notes",
            "by",
            "at",
            "diff",
        ]