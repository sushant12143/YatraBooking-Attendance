"""Glue between the ORM and the pure-Python analytics."""
from datetime import datetime, time, timedelta

from django.utils import timezone

from . import analytics
from .models import (AdjustmentRequest, Employee, LeaveRequest, OfficeSettings, Punch)

METHOD_LABELS = {"biometric": "Biometric", "mobile": "Mobile", "web": "Web", "manual": "Manual"}


def day_bounds(start, end):
    """Aware datetimes covering [start 00:00, end+1 00:00) in the current time zone."""
    tz = timezone.get_current_timezone()
    s = timezone.make_aware(datetime.combine(start, time.min), tz)
    e = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), tz)
    return s, e


def office_dict(office=None):
    office = office or OfficeSettings.load()
    return {
        "start_minutes": office.start_minutes(),
        "grace": office.grace_minutes,
        "workdays": office.workday_set(),
    }


def load_data(start, end):
    """Build an AttendanceData for active employees between two dates (inclusive)."""
    employees = [
        {"id": e.id, "name": e.name, "department": e.department.name if e.department else ""}
        for e in Employee.objects.filter(status="active").select_related("department")
    ]
    s, e = day_bounds(start, end)
    punches = [
        (emp_id, timezone.localtime(dt).replace(tzinfo=None))
        for emp_id, dt in Punch.objects.filter(
            employee__isnull=False, punched_at__gte=s, punched_at__lt=e
        ).values_list("employee_id", "punched_at")
    ]
    leaves = [
        {"employee_id": lv.employee_id, "start": lv.start_date, "end": lv.end_date, "planned": lv.planned}
        for lv in LeaveRequest.objects.filter(status="approved", start_date__lte=end, end_date__gte=start)
    ]
    adjustments = [
        {"employee_id": a.employee_id, "date": a.date, "check_in": a.check_in, "check_out": a.check_out}
        for a in AdjustmentRequest.objects.filter(status="approved", date__gte=start, date__lte=end)
    ]
    return analytics.AttendanceData(employees, punches, leaves, adjustments, office_dict())


def initials(name):
    parts = (name or "").split()
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def feed_items(limit=10):
    """Latest punches for the live check-in feed."""
    office = OfficeSettings.load()
    late_after = office.start_minutes() + office.grace_minutes
    today = timezone.localdate()
    out = []
    qs = Punch.objects.select_related("employee__department").order_by("-punched_at")[:limit]
    for p in qs:
        local = timezone.localtime(p.punched_at)
        day_start, _ = day_bounds(local.date(), local.date())
        earlier = Punch.objects.filter(punched_at__gte=day_start, punched_at__lt=p.punched_at)
        if p.employee_id:
            earlier = earlier.filter(employee_id=p.employee_id)
        else:
            earlier = earlier.filter(employee__isnull=True, finger_id=p.finger_id)
        minutes = local.hour * 60 + local.minute
        if not p.employee_id:
            status, label = "unknown", "Unknown"
        elif earlier.exists():
            status, label = "repeat", "Punch"
        elif minutes > late_after:
            status, label = "late", "Late"
        else:
            status, label = "ontime", "On Time"
        emp = p.employee
        out.append({
            "name": p.name,
            "initials": initials(p.name),
            "color": (emp.pk % 6) if emp else 5,
            "department": emp.department.name if emp and emp.department else "-",
            "time": local.strftime("%I:%M %p").lstrip("0"),
            "day": "Today" if local.date() == today else local.strftime("%d %b"),
            "method": METHOD_LABELS.get(p.method, p.method),
            "status": status,
            "label": label,
        })
    return out
