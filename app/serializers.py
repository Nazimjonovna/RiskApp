from rest_framework import serializers
from .models import (Department, Risk, RiskCommittee, Mitigation, 
                     RiskDecition, RiskActivity, Category, ReplyRiskActivity)

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
        fields = '__all__'
        
        
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