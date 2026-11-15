from .models import AdjustmentRequest, Employee, LeaveRequest
from .services import initials


def sidebar(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    name = user.get_full_name() or user.get_username()
    return {
        "nav_name": name,
        "nav_initials": initials(name),
        "nav_pending": LeaveRequest.objects.filter(status="pending").count()
        + AdjustmentRequest.objects.filter(status="pending").count(),
        "nav_employees": Employee.objects.filter(status="active").count(),
    }
