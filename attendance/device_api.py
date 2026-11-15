"""Endpoints used by the ESP8266 (header X-API-Key). Protocol kept identical to the sketch:

GET  /api/device/commands -> text/plain: none | enroll|<cmdId>|<name> | delete|<cmdId>|<fingerId>
POST /api/device/result   -> form: command_id, ok(1/0), finger_id, message
POST /api/device/punch    -> form: ts (unix seconds, 0 = clock not synced), finger_id, confidence
"""
import hmac
from datetime import datetime, timedelta, timezone as dt_timezone
from functools import wraps

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import DeviceCommand, DeviceState, Employee, Punch

RESEND_AFTER = timedelta(seconds=120)


def _text(body, status=200):
    return HttpResponse(body, content_type="text/plain; charset=utf-8", status=status)


def device_auth(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        key = settings.DEVICE_KEY
        given = request.headers.get("X-API-Key", "")
        if not key or not hmac.compare_digest(given.encode(), key.encode()):
            return _text("unauthorized", 401)
        return view(request, *args, **kwargs)

    return wrapper


def _int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _clean(name):
    return " ".join(str(name).replace("|", " ").split())[:60]


@csrf_exempt
@require_GET
@device_auth
def commands(request):
    DeviceState.touch()
    with transaction.atomic():
        now = timezone.now()
        cmd = (
            DeviceCommand.objects.select_for_update()
            .filter(status="pending")
            .order_by("id")
            .first()
        )
        if cmd is None:  # re-deliver one that was sent but never answered (device rebooted)
            cmd = (
                DeviceCommand.objects.select_for_update()
                .filter(status="sent", sent_at__lt=now - RESEND_AFTER)
                .order_by("id")
                .first()
            )
        if cmd is None:
            return _text("none")
        cmd.status = "sent"
        cmd.sent_at = now
        cmd.save(update_fields=["status", "sent_at"])
    if cmd.type == "enroll":
        return _text("enroll|%d|%s" % (cmd.id, _clean(cmd.name) or "Employee"))
    return _text("delete|%d|%d" % (cmd.id, cmd.finger_id or 0))


@csrf_exempt
@require_POST
@device_auth
def result(request):
    DeviceState.touch()
    cmd_id = _int(request.POST.get("command_id"), -1)
    ok = request.POST.get("ok", "0").strip() in ("1", "true", "True")
    finger_id = _int(request.POST.get("finger_id"), 0)
    message = request.POST.get("message", "")[:200]
    with transaction.atomic():
        cmd = DeviceCommand.objects.select_for_update().filter(pk=cmd_id).first()
        if cmd is None:
            return _text("unknown command", 404)
        if cmd.status in ("done", "failed"):
            return _text("ok")  # duplicate report
        emp = cmd.employee
        if cmd.type == "enroll":
            if ok and finger_id > 0 and emp is not None:
                # a sensor slot belongs to one person: release it from anyone stale
                Employee.objects.filter(finger_id=finger_id).exclude(pk=emp.pk).update(finger_id=None)
                emp.finger_id = finger_id
                emp.status = "active"
                emp.save(update_fields=["finger_id", "status"])
                cmd.finger_id = finger_id
            elif emp is not None and emp.status == "pending":
                emp.delete()  # nothing was enrolled
                emp = None
        else:  # delete
            if emp is not None:
                if ok:
                    emp.delete()
                else:
                    emp.status = "active"
                    emp.save(update_fields=["status"])
        cmd.status = "done" if ok else "failed"
        cmd.message = message or ("done" if ok else "failed")
        cmd.save(update_fields=["status", "message", "finger_id"] if cmd.type == "enroll" and ok
                 else ["status", "message"])
    return _text("ok")


@csrf_exempt
@require_POST
@device_auth
def punch(request):
    DeviceState.touch()
    finger_id = _int(request.POST.get("finger_id"), 0)
    confidence = max(0, _int(request.POST.get("confidence"), 0))
    ts = _int(request.POST.get("ts"), 0)
    now = timezone.now()
    if ts < 1_500_000_000:  # clock was not synced on the device
        when = now
    else:
        when = datetime.fromtimestamp(ts, tz=dt_timezone.utc)
        if when > now + timedelta(minutes=5):  # nonsense future timestamp
            when = now
    emp = Employee.objects.filter(finger_id=finger_id, status="active").first() if finger_id else None
    name = emp.name if emp else "(unknown #%d)" % finger_id
    try:
        with transaction.atomic():
            Punch.objects.create(
                employee=emp, finger_id=finger_id, name=name, punched_at=when,
                confidence=confidence, method="biometric",
            )
    except IntegrityError:
        pass  # offline queue replay of a punch we already have
    return _text("ok")
