from django.db import models
from django.utils import timezone


class Department(models.Model):
    name = models.CharField(max_length=255)
    keycloak_group_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    keycloak_path = models.CharField(max_length=500, unique=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class Risk(models.Model):

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('UNDER_RISK_REVIEW', 'Under review by Risk Manager'),
        ('INFO_REQUESTED_BY_RISK_MANAGER', 'Information requested by Risk Manager'),
        ('REJECTED_BY_RISK_MANAGER', 'Rejected by Risk Manager'),
        ('COMMITTEE_REVIEW_1', 'Committee Review 1'),
        ('INFO_REQUESTED_BY_COMMITTEE', 'Information requested by committee'),
        ('ACCEPTED_FOR_MITIGATION', 'Approved for mitigation'),
        ('COMMITTEE_REVIEW_2', 'Committee Review 2'),
        ('ADDITIONAL_MITIGATION_REQUIRED', 'Additional mitigation is required.'),
        ('RISK_ACCEPTED', 'Risk accepted'),
        ('IN_MITIGATION', 'IN_MITIGATION'),
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In Progress"),
        ("MITIGATED", "Mitigated"),
        ("ACCEPTED", "Accepted"),
        ("CLOSED", "Closed"),
    ]
    
    PROBABILITY_CHOICES = [
    ('LOW', 'Low'),
    ('HIGH', 'High'),
    ('MEDIUM', 'Medium')
    ]
    
    IMPACT_CHOICES = [
        ('SMALL', 'Small'),
        ("AVERAGE", 'Average'),
        ('HUGE', 'Huge'),
        ('CRITICAL', 'Critical')
    ]
    title = models.CharField(max_length=255)
    risk_number = models.CharField(max_length=20, unique=True, blank=True)
    description = models.TextField(blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        related_name="risks"
    )
    is_active = models.BooleanField(default=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name="risks"
    )
    owner = models.CharField(max_length=255) # Bu nimaga kerak edi
    risk_manager = models.CharField(max_length=250, null=True, blank=True) # keycloak va ad qo'shilgandan keyin foreginkey bo'ladi
    risk_derector = models.CharField(max_length=250, null=True, blank=True) # keycloak va ad qo'shilgandan keyin foreginkey bo'ladi
    responsible = models.CharField(max_length=255) # after keycloak and ad change this foreginkey
    responsible_department_id = models.ForeignKey(Department, on_delete=models.CASCADE)
    created_by_user_id = models.CharField(max_length=100)
    created_by_department_id = models.CharField(max_length=100)
    status = models.CharField(
        max_length=2000,
        choices=STATUS_CHOICES,
        default="OPEN"
    )
    probability = models.CharField(choices=PROBABILITY_CHOICES, max_length=500, null = True, blank=True)
    Impact = models.CharField(choices=IMPACT_CHOICES, max_length=500, null = True, blank=True)
    possible_loss = models.FloatField(default=0)
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
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.id} - {self.title}"


class Mitigation(models.Model):
    STATUS_CHOICES = [
        ("NOT_STARTED", "Not Started"),
        ("IN_PROGRESS", "In Progress"),
        ("PENDING_RISK_REVIEW", "Pending Risk Review"),
        ("APPROVED", "Approved"),
    ]
    risk = models.ForeignKey(
        "Risk",
        on_delete=models.CASCADE,
        related_name="mitigations"
    )
    department_director = models.CharField(max_length=500)
    title = models.CharField(max_length=255)
    owner = models.CharField(max_length=200) # keycloak va ad qo'shilganda foreginkey, bu mitigation ni qilishi kk bo'lgan odam
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
    
    
class RiskDecition(models.Model):
    DECITION_CHOICES = [
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
    decition_type = models.CharField(
        max_length=30,
        choices=DECITION_CHOICES
    )
    decided_by = models.CharField(max_length=500)# keycloak va ad qo'shilganda foreginkey, bu decision ni qilgan kk bo'lgan odam
    decided_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-decided_at"]

    def __str__(self):
        return f"{self.risk.id} - {self.decition_type}"


class RiskCommittee(models.Model):
    risk = models.OneToOneField(
        Risk,
        on_delete=models.CASCADE,
        related_name="committee"
    )
    decision = models.ForeignKey(RiskDecition, on_delete=models.CASCADE, null=True, blank=True)
    mitigation = models.ForeignKey(Mitigation, on_delete=models.CASCADE, null=True, blank=True)
    last_decition = models.TextField(blank=True)
    last_decition_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Committee decision for {self.risk.id}"


class RiskActivity(models.Model): # Risk chat

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
    by = models.CharField(max_length=500)# Keckloak va ad dan keyin Foreginkey boladi bu yozayotgan odam
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
    
class RiskActivityRecipient(models.Model):
    activity = models.ForeignKey(RiskActivity, on_delete=models.CASCADE)
    user = models.CharField(max_length=500)
    is_read = models.BooleanField(default=False)


class ReplyRiskActivity(models.Model): # Risk chat reply 
    riskactivity = models.ForeignKey(RiskActivity, on_delete=models.CASCADE, null=True, blank=True)
    riskdecision = models.ForeignKey(RiskDecition, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=250, null=True, blank=True)
    notes = models.TextField()
    created_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=200) # After keycloak and ad must change to foreginkey user
    
    def __str__(self):
        return f"{self.riskactivity.id} - {self.created_at}"
    

class Notification(models.Model):
    user = models.CharField(max_length=200)
    title = models.CharField(max_length=250)
    note = models.TextField()
    container = models.CharField(max_length=250) # ko'raman yeslicho enum qilaman bu qaysi model ekani
    object_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now=True)
    is_read = models.BooleanField(default=False)
    
    def __str__(self):
        return f'{self.container} ---- {self.object_id} ---- {self.created_at}'
