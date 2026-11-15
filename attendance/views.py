from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from . import analytics, reports as report_files, services
from .forms import AdjustmentForm, EmployeeForm, LeaveForm, ReportForm, SettingsForm
from .models import (AdjustmentRequest, Department, DeviceCommand, DeviceState, Employee,
                     LeaveRequest, OfficeSettings, Punch)

MAX_LOGIN_FAILURES = 8
LOGIN_WINDOW = 600


# ---------------------------------------------------------------- login
class ThrottledLoginView(LoginView):
    template_name = "attendance/login.html"
    redirect_authenticated_user = True

    def _key(self):
        fwd = self.request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = fwd.split(",")[0].strip() if fwd else self.request.META.get("REMOTE_ADDR", "?")
        return "login-fail:" + ip

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST" and cache.get(self._key(), 0) >= MAX_LOGIN_FAILURES:
            return HttpResponse("Too many failed attempts. Try again in a few minutes.", status=429)
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        cache.set(self._key(), cache.get(self._key(), 0) + 1, LOGIN_WINDOW)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self._key())
        return super().form_valid(form)


def _back(request, default="dashboard"):
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt)
    return redirect(default)


@require_GET
def health(request):
    return JsonResponse({"ok": True})


# ---------------------------------------------------------------- dashboard
@login_required
def dashboard(request):
    today = timezone.localdate()
    data = services.load_data(today - timedelta(days=45), today)
    summary = data.summary(today)
    trend = data.trend(today, 30)
    dept = data.department_absence(today - timedelta(days=29), today)
    tardy = data.tardiness(today - timedelta(days=29), today)

    status_rows = []
    for e in data.employees:
        s = data.status(e["id"], today)
        t = data.times(e["id"], today)
        status_rows.append({"name": e["name"], "department": e["department"], "status": s,
                            "initials": services.initials(e["name"]), "color": e["id"] % 6,
                            "check_in": analytics.fmt_minutes(t[0]) if t else ""})
    order = {"late": 0, "absent": 1, "leave": 2, "present": 3, "off": 4}
    status_rows.sort(key=lambda r: (order.get(r["status"], 9), r["name"]))

    chart = {
        "trend": trend,
        "donut": [
            {"label": "On time", "value": summary["on_time"], "key": "ontime"},
            {"label": "Late", "value": summary["late"], "key": "late"},
            {"label": "Absent", "value": summary["absent"], "key": "absent"},
            {"label": "On leave", "value": summary["leave"], "key": "leave"},
        ],
        "dept": dept,
        "tardy": tardy,
    }
    device = DeviceState.objects.filter(pk=1).first()
    ctx = {
        "today": today,
        "summary": summary,
        "chart": chart,
        "calendar": data.month_cells(today.year, today.month, today),
        "month_label": today.strftime("%B %Y"),
        "status_rows": status_rows[:8],
        "top_late": data.top_late(today - timedelta(days=29), today),
        "feed": services.feed_items(),
        "pending_leaves": LeaveRequest.objects.filter(status="pending").select_related("employee")[:5],
        "pending_adjust": AdjustmentRequest.objects.filter(status="pending").select_related("employee")[:5],
        "enrolling": Employee.objects.exclude(status="active").count(),
        "device_online": bool(device and device.online),
        "device_seen": timezone.localtime(device.last_seen) if device and device.last_seen else None,
        "weekdays": ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"],
        "page": "dashboard",
    }
    return render(request, "attendance/dashboard.html", ctx)


@login_required
@require_GET
def feed(request):
    return render(request, "attendance/_feed.html", {"feed": services.feed_items()})


# ---------------------------------------------------------------- employees
@login_required
def employees(request):
    q = request.GET.get("q", "").strip()
    qs = Employee.objects.select_related("department")
    if q:
        qs = qs.filter(name__icontains=q)
    device = DeviceState.objects.filter(pk=1).first()
    ctx = {
        "employees": qs,
        "q": q,
        "form": EmployeeForm(),
        "departments": Department.objects.all(),
        "device_online": bool(device and device.online),
        "page": "employees",
    }
    return render(request, "attendance/employees.html", ctx)


@login_required
@require_POST
def employee_add(request):
    form = EmployeeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(e for errs in form.errors.values() for e in errs))
        return redirect("employees")
    d = form.cleaned_data
    with transaction.atomic():
        dept = Department.objects.get_or_create(name=d["department"])[0] if d["department"] else None
        emp = Employee.objects.create(
            name=d["name"], department=dept, designation=d["designation"], email=d["email"],
            phone=d["phone"], status="pending")
        DeviceCommand.objects.create(type="enroll", employee=emp, name=emp.name)
    messages.success(request, "%s added. The device will start enrollment within about 10 seconds "
                              "- follow the prompts at the sensor." % emp.name)
    return redirect("employees")


@login_required
@require_POST
def employee_delete(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    force = request.POST.get("force") == "1"
    with transaction.atomic():
        if emp.finger_id and not force:
            if emp.status != "deleting":
                emp.status = "deleting"
                emp.save(update_fields=["status"])
                DeviceCommand.objects.create(type="delete", employee=emp, finger_id=emp.finger_id, name=emp.name)
            messages.success(request, "Removing %s: the device will delete the fingerprint shortly." % emp.name)
        else:
            DeviceCommand.objects.filter(employee=emp, status__in=["pending", "sent"]).update(
                status="failed", message="cancelled by admin")
            name = emp.name
            emp.delete()
            note = " (the fingerprint may still be stored on the sensor)" if force and emp.finger_id else ""
            messages.success(request, "%s removed%s." % (name, note))
    return redirect("employees")


# ---------------------------------------------------------------- requests
@login_required
def requests_page(request):
    ctx = {
        "leaves": LeaveRequest.objects.select_related("employee").order_by(
            "status", "-created_at")[:50],
        "adjustments": AdjustmentRequest.objects.select_related("employee").order_by(
            "status", "-created_at")[:50],
        "leave_form": LeaveForm(),
        "adjust_form": AdjustmentForm(),
        "page": "requests",
    }
    return render(request, "attendance/requests.html", ctx)


@login_required
@require_POST
def leave_add(request):
    form = LeaveForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Leave request added.")
    else:
        messages.error(request, "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect("requests")


@login_required
@require_POST
def adjust_add(request):
    form = AdjustmentForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Adjustment request added.")
    else:
        messages.error(request, "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect("requests")


def _decide(request, model, pk, action, label):
    if action not in ("approve", "reject"):
        messages.error(request, "Unknown action.")
        return _back(request, "requests")
    updated = model.objects.filter(pk=pk, status="pending").update(
        status="approved" if action == "approve" else "rejected",
        decided_at=timezone.now(), decided_by=request.user)
    if updated:
        messages.success(request, "%s %s." % (label, "approved" if action == "approve" else "rejected"))
    else:
        messages.error(request, "That request was already decided.")
    return _back(request, "requests")


@login_required
@require_POST
def leave_decide(request, pk, action):
    return _decide(request, LeaveRequest, pk, action, "Leave request")


@login_required
@require_POST
def adjust_decide(request, pk, action):
    return _decide(request, AdjustmentRequest, pk, action, "Adjustment")


# ---------------------------------------------------------------- reports
@login_required
def reports(request):
    today = timezone.localdate()
    initial = {"start": today.replace(day=1), "end": today}
    form = ReportForm(request.GET) if request.GET else ReportForm(initial=initial)
    rows, fmt = [], request.GET.get("format", "")
    if request.GET and form.is_valid():
        start, end = form.cleaned_data["start"], form.cleaned_data["end"]
        data = services.load_data(start, end)
        table = analytics.report_table(data.rows(start, end))
        name = "attendance_%s_to_%s" % (start, end)
        if fmt == "csv":
            resp = HttpResponse(report_files.to_csv(analytics.REPORT_HEADERS, table), content_type="text/csv")
            resp["Content-Disposition"] = 'attachment; filename="%s.csv"' % name
            return resp
        if fmt == "xlsx":
            resp = HttpResponse(
                report_files.to_xlsx(analytics.REPORT_HEADERS, table),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            resp["Content-Disposition"] = 'attachment; filename="%s.xlsx"' % name
            return resp
        if fmt == "pdf":
            resp = HttpResponse(
                report_files.to_pdf(analytics.REPORT_HEADERS, table[:5000],
                                    title="Attendance %s to %s" % (start, end)),
                content_type="application/pdf")
            resp["Content-Disposition"] = 'attachment; filename="%s.pdf"' % name
            return resp
        rows = table[:300]
        total = len(table)
    else:
        total = 0
    qs = request.GET.urlencode()
    return render(request, "attendance/reports.html", {
        "form": form, "rows": rows, "total": total, "headers": analytics.REPORT_HEADERS,
        "has_range": bool(request.GET and form.is_valid()),
        "qs": "&".join(p for p in qs.split("&") if not p.startswith("format=")),
        "page": "reports"})


# ---------------------------------------------------------------- settings
@login_required
def settings_page(request):
    office = OfficeSettings.load()
    if request.method == "POST":
        form = SettingsForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            office.start_time = d["start_time"]
            office.grace_minutes = d["grace_minutes"]
            office.workdays = ",".join(str(x) for x in sorted(d["workdays"]))
            office.save()
            messages.success(request, "Settings saved.")
            return redirect("settings")
    else:
        form = SettingsForm(initial={
            "start_time": office.start_time, "grace_minutes": office.grace_minutes,
            "workdays": sorted(office.workday_set())})
    device = DeviceState.objects.filter(pk=1).first()
    from django.conf import settings as dj
    return render(request, "attendance/settings.html", {
        "form": form,
        "device_online": bool(device and device.online),
        "device_seen": timezone.localtime(device.last_seen) if device and device.last_seen else None,
        "server_url": request.build_absolute_uri("/").rstrip("/"),
        "key_set": bool(dj.DEVICE_KEY),
        "page": "settings"})
