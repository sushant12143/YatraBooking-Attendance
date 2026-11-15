from datetime import time

from django.conf import settings
from django.db import models
from django.utils import timezone

METHOD_CHOICES = [
    ("biometric", "Biometric"),
    ("mobile", "Mobile"),
    ("web", "Web"),
    ("manual", "Manual"),
]
REQUEST_STATUS = [
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]


class Department(models.Model):
    name = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("pending", "Enrolling"),
        ("deleting", "Removing"),
    ]

    name = models.CharField(max_length=60)
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="employees"
    )
    designation = models.CharField(max_length=60, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    finger_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def initials(self):
        parts = self.name.split()
        if not parts:
            return "?"
        return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()

    @property
    def color_index(self):
        return (self.pk or 0) % 6


class Punch(models.Model):
    employee = models.ForeignKey(
        Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="punches"
    )
    finger_id = models.PositiveIntegerField(null=True, blank=True)
    name = models.CharField(max_length=60)
    punched_at = models.DateTimeField(db_index=True)
    confidence = models.PositiveIntegerField(default=0)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default="biometric")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["finger_id", "punched_at"], name="punch_unique_finger_time"),
        ]

    def __str__(self):
        return f"{self.name} @ {self.punched_at:%Y-%m-%d %H:%M}"


class DeviceCommand(models.Model):
    TYPE_CHOICES = [("enroll", "Enroll"), ("delete", "Delete")]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("done", "Done"),
        ("failed", "Failed"),
    ]

    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    employee = models.ForeignKey(
        Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="commands"
    )
    finger_id = models.PositiveIntegerField(null=True, blank=True)
    name = models.CharField(max_length=60, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    message = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.type} #{self.pk} ({self.status})"


class DeviceState(models.Model):
    """Single row (pk=1): when the fingerprint device last contacted the server."""

    last_seen = models.DateTimeField(null=True, blank=True)

    @property
    def online(self):
        return bool(self.last_seen and (timezone.now() - self.last_seen).total_seconds() < 90)

    @classmethod
    def touch(cls):
        cls.objects.update_or_create(pk=1, defaults={"last_seen": timezone.now()})


class OfficeSettings(models.Model):
    """Single row (pk=1). Workdays use Python weekday numbers: Mon=0 ... Sun=6."""

    start_time = models.TimeField(default=time(10, 0))
    grace_minutes = models.PositiveIntegerField(default=10)
    workdays = models.CharField(max_length=20, default="0,1,2,3,4,6")

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def workday_set(self):
        return {int(x) for x in self.workdays.split(",") if x.strip().isdigit()}

    def start_minutes(self):
        return self.start_time.hour * 60 + self.start_time.minute


class LeaveRequest(models.Model):
    TYPE_CHOICES = [
        ("casual", "Casual"),
        ("sick", "Sick"),
        ("annual", "Annual"),
        ("unpaid", "Unpaid"),
        ("other", "Other"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leaves")
    leave_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="casual")
    planned = models.BooleanField(default=True)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=REQUEST_STATUS, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1

    def __str__(self):
        return f"{self.employee} {self.start_date}..{self.end_date} ({self.status})"


class AdjustmentRequest(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="adjustments")
    date = models.DateField()
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    reason = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=REQUEST_STATUS, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    def __str__(self):
        return f"{self.employee} {self.date} ({self.status})"
