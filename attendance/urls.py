from django.urls import path

from . import device_api, views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("feed/", views.feed, name="feed"),
    path("healthz", views.health, name="health"),
    path("employees/", views.employees, name="employees"),
    path("employees/add/", views.employee_add, name="employee_add"),
    path("employees/<int:pk>/delete/", views.employee_delete, name="employee_delete"),
    path("requests/", views.requests_page, name="requests"),
    path("requests/leave/add/", views.leave_add, name="leave_add"),
    path("requests/leave/<int:pk>/<str:action>/", views.leave_decide, name="leave_decide"),
    path("requests/adjust/add/", views.adjust_add, name="adjust_add"),
    path("requests/adjust/<int:pk>/<str:action>/", views.adjust_decide, name="adjust_decide"),
    path("reports/", views.reports, name="reports"),
    path("settings/", views.settings_page, name="settings"),
    path("api/device/commands", device_api.commands),
    path("api/device/result", device_api.result),
    path("api/device/punch", device_api.punch),
]
