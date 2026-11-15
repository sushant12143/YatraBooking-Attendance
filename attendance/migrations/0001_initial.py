import datetime

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _id():
    return ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"))


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Department",
            fields=[
                _id(),
                ("name", models.CharField(max_length=60, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Employee",
            fields=[
                _id(),
                ("name", models.CharField(max_length=60)),
                ("designation", models.CharField(blank=True, max_length=60)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("finger_id", models.PositiveIntegerField(blank=True, null=True, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("pending", "Enrolling"), ("deleting", "Removing")],
                        default="active",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="employees",
                        to="attendance.department",
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Punch",
            fields=[
                _id(),
                ("finger_id", models.PositiveIntegerField(blank=True, null=True)),
                ("name", models.CharField(max_length=60)),
                ("punched_at", models.DateTimeField(db_index=True)),
                ("confidence", models.PositiveIntegerField(default=0)),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("biometric", "Biometric"),
                            ("mobile", "Mobile"),
                            ("web", "Web"),
                            ("manual", "Manual"),
                        ],
                        default="biometric",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "employee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="punches",
                        to="attendance.employee",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="punch",
            constraint=models.UniqueConstraint(fields=("finger_id", "punched_at"), name="punch_unique_finger_time"),
        ),
        migrations.CreateModel(
            name="DeviceCommand",
            fields=[
                _id(),
                (
                    "type",
                    models.CharField(choices=[("enroll", "Enroll"), ("delete", "Delete")], max_length=10),
                ),
                ("finger_id", models.PositiveIntegerField(blank=True, null=True)),
                ("name", models.CharField(blank=True, max_length=60)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("sent", "Sent"), ("done", "Done"), ("failed", "Failed")],
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("message", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                (
                    "employee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="commands",
                        to="attendance.employee",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="DeviceState",
            fields=[
                _id(),
                ("last_seen", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="OfficeSettings",
            fields=[
                _id(),
                ("start_time", models.TimeField(default=datetime.time(10, 0))),
                ("grace_minutes", models.PositiveIntegerField(default=10)),
                ("workdays", models.CharField(default="0,1,2,3,4,6", max_length=20)),
            ],
        ),
        migrations.CreateModel(
            name="LeaveRequest",
            fields=[
                _id(),
                (
                    "leave_type",
                    models.CharField(
                        choices=[
                            ("casual", "Casual"),
                            ("sick", "Sick"),
                            ("annual", "Annual"),
                            ("unpaid", "Unpaid"),
                            ("other", "Other"),
                        ],
                        default="casual",
                        max_length=10,
                    ),
                ),
                ("planned", models.BooleanField(default=True)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("reason", models.CharField(blank=True, max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                (
                    "decided_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="leaves",
                        to="attendance.employee",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="AdjustmentRequest",
            fields=[
                _id(),
                ("date", models.DateField()),
                ("check_in", models.TimeField(blank=True, null=True)),
                ("check_out", models.TimeField(blank=True, null=True)),
                ("reason", models.CharField(blank=True, max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                (
                    "decided_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="adjustments",
                        to="attendance.employee",
                    ),
                ),
            ],
        ),
    ]
