import random
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from attendance.models import (AdjustmentRequest, Department, Employee, LeaveRequest, Punch)

DEMO_DOMAIN = "@demo.local"
PEOPLE = [
    ("Asha Sharma", "Sales"), ("Bikash Thapa", "Sales"), ("Chitra Rai", "IT"), ("Dipesh Karki", "IT"),
    ("Elina Gurung", "HR"), ("Faisal Ansari", "Finance"), ("Gita Basnet", "Finance"),
    ("Hari Adhikari", "Operations"), ("Isha Pandey", "Operations"), ("Jiwan Shrestha", "Support"),
    ("Kabita Lama", "Support"), ("Laxman Khadka", "IT"),
]


class Command(BaseCommand):
    help = "Fill the database with demo employees and 30 days of punches. Use --clear to remove them again."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true")

    def handle(self, *args, **opts):
        demo = Employee.objects.filter(email__endswith=DEMO_DOMAIN)
        Punch.objects.filter(employee__in=demo).delete()
        demo.delete()
        if opts["clear"]:
            self.stdout.write("Demo data removed.")
            return
        rnd = random.Random(7)
        used = set(Employee.objects.exclude(finger_id=None).values_list("finger_id", flat=True))
        slot = 100
        tz = timezone.get_current_timezone()
        today = timezone.localdate()
        emps = []
        for name, dept in PEOPLE:
            while slot in used:
                slot += 1
            used.add(slot)
            d, _ = Department.objects.get_or_create(name=dept)
            emps.append(Employee.objects.create(
                name=name, department=d, finger_id=slot, status="active",
                email=name.split()[0].lower() + DEMO_DOMAIN, designation="Staff"))
        for e in emps:
            late_bias = rnd.choice([0.05, 0.1, 0.3])
            absent_bias = rnd.choice([0.02, 0.06, 0.12])
            for back in range(30, -1, -1):
                day = today - timedelta(days=back)
                if day.weekday() not in (0, 1, 2, 3, 4, 6):
                    continue
                if back == 0 and rnd.random() < 0.15:
                    continue
                if rnd.random() < absent_bias:
                    continue
                if rnd.random() < late_bias:
                    mins = rnd.randint(611, 665)
                else:
                    mins = rnd.randint(545, 609)
                self._punch(e, day, mins, tz, rnd)
                if back > 0 or rnd.random() < 0.3:
                    self._punch(e, day, rnd.randint(1000, 1090), tz, rnd)
        LeaveRequest.objects.create(employee=emps[2], leave_type="sick", planned=False,
                                    start_date=today, end_date=today, reason="Fever", status="approved")
        LeaveRequest.objects.create(employee=emps[4], leave_type="annual", planned=True,
                                    start_date=today + timedelta(days=3), end_date=today + timedelta(days=5),
                                    reason="Family trip")
        LeaveRequest.objects.create(employee=emps[7], leave_type="casual", planned=True,
                                    start_date=today + timedelta(days=1), end_date=today + timedelta(days=1),
                                    reason="Personal work")
        AdjustmentRequest.objects.create(employee=emps[1], date=today - timedelta(days=1),
                                         check_in=time(9, 45), check_out=time(17, 30),
                                         reason="Forgot to punch in")
        self.stdout.write("Demo data created: %d employees." % len(emps))

    def _punch(self, emp, day, mins, tz, rnd):
        when = timezone.make_aware(datetime.combine(day, time(mins // 60, mins % 60, rnd.randint(0, 59))), tz)
        if when > timezone.now():
            return
        Punch.objects.get_or_create(
            finger_id=emp.finger_id, punched_at=when,
            defaults={"employee": emp, "name": emp.name, "confidence": rnd.randint(80, 250)})
