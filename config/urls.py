from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path

from attendance.views import ThrottledLoginView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", ThrottledLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("", include("attendance.urls")),
]
