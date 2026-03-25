import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class Department(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Risk(models.Model):

    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In Progress"),
        ("MITIGATED", "Mitigated"),
        ("ACCEPTED", "Accepted"),
        ("CLOSED", "Closed"),
    ]

    CATEGORY_CHOICES = [
        ("STRATEGIC", "Strategic"),
        ("FINANCIAL", "Financial"),
        ("OPERATIONAL", "Operational"),
        ("COMPLIANCE", "Compliance"),
        ("LEGAL", "Legal"),
        ("IT", "IT / Cyber"),
        ("REPUTATIONAL", "Reputational"),
    ]
    title = models.CharField(max_length=255)
    risk_number = models.CharField(max_length=20, unique=True, blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        related_name="risks"
    )
    owner = models.CharField(max_length=255)
    responsible = models.CharField(max_length=255)
    created_by_user_id = models.CharField(max_length=100)
    created_by_department_id = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="OPEN"
    )
    probability = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    impact_min = models.FloatField()
    impact_most_likely = models.FloatField()
    impact_max = models.FloatField()
    expected_loss = models.FloatField(default=0)
    severity = models.FloatField(default=0)
    inherent_score = models.FloatField(null=True, blank=True)
    residual_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    due_date = models.DateTimeField(null=True, blank=True)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    tags = models.JSONField(default=list, blank=True)
    attachments = models.JSONField(default=list, blank=True)
    existing_controls_text = models.TextField(blank=True)
    planned_controls_text = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.risk_number:
            last = Risk.objects.order_by("-id").first()
            if last:
                new_number = last.id + 1
            else:
                new_number = 1
            self.risk_number = f"RISK-{new_number:03d}"
        mean_impact = (self.impact_min + self.impact_most_likely + self.impact_max) / 3
        self.expected_loss = self.probability * mean_impact
        self.severity = self.expected_loss
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.id} - {self.title}"


class RiskCommittee(models.Model):
    risk = models.OneToOneField(
        Risk,
        on_delete=models.CASCADE,
        related_name="committee"
    )
    last_decision = models.TextField(blank=True)
    last_decision_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Committee decision for {self.risk.id}"


class Mitigation(models.Model):
    STATUS_CHOICES = [
        ("NOT_STARTED", "Not Started"),
        ("IN_PROGRESS", "In Progress"),
        ("DONE", "Done"),
    ]
    risk = models.ForeignKey(
        "Risk",
        on_delete=models.CASCADE,
        related_name="mitigations"
    )
    title = models.CharField(max_length=255)
    owner = models.CharField(max_length=200)
    due_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="NOT_STARTED"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.risk.id} - {self.title}"
    
    
class RiskDecision(models.Model):
    DECISION_CHOICES = [
        ("APPROVE", "Approve"),
        ("REJECT", "Reject"),
        ("REQUEST_INFO", "Request Info"),
        ("ACCEPT_RESIDUAL", "Accept Residual Risk"),
    ]
    risk = models.ForeignKey(
        "Risk",
        on_delete=models.CASCADE,
        related_name="decisions"
    )
    decision_type = models.CharField(
        max_length=30,
        choices=DECISION_CHOICES
    )
    decided_by = models.CharField(max_length=500)
    decided_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-decided_at"]

    def __str__(self):
        return f"{self.risk.id} - {self.decision_type}"


class RiskActivity(models.Model):

    TYPE_CHOICES = [
        ("CREATE", "create"),
        ("UPDATE", "update"),
        ("DECISION", "decision"),
        ("ASSIGNMENT", "assignment"),
        ("FINANCIAL", "financial"),
        ("COMMENT", "comment"),
        ("REVIEW", "review"),
    ]
    risk = models.ForeignKey(
        "Risk",
        on_delete=models.CASCADE,
        related_name="activities"
    )
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )
    title = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    by = models.CharField(max_length=500)
    at = models.DateTimeField(default=timezone.now)
    diff = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-at"]
        indexes = [
            models.Index(fields=["risk", "type"]),
            models.Index(fields=["at"]),
        ]

    def __str__(self):
        return f"{self.risk.id} - {self.type}"

