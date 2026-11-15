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
        emp_id = cmd.employee_id
        new_finger = cmd.finger_id
        if cmd.type == "enroll":
            if ok and finger_id > 0 and emp_id:
                # a sensor slot belongs to one person: release it from anyone stale
                Employee.objects.filter(finger_id=finger_id).exclude(pk=emp_id).update(finger_id=None)
                Employee.objects.filter(pk=emp_id).update(finger_id=finger_id, status="active")
                new_finger = finger_id
            elif emp_id:
                Employee.objects.filter(pk=emp_id, status="pending").delete()  # nothing was enrolled
        else:  # delete
            if emp_id:
                if ok:
                    Employee.objects.filter(pk=emp_id).delete()
                else:
                    Employee.objects.filter(pk=emp_id).update(status="active")
        DeviceCommand.objects.filter(pk=cmd.pk).update(
            status="done" if ok else "failed",
            message=message or ("done" if ok else "failed"),
            finger_id=new_finger,
        )
    return _text("ok")