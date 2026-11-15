from django.contrib import admin

from . import models

for m in (models.Department, models.Employee, models.Punch, models.DeviceCommand,
          models.OfficeSettings, models.LeaveRequest, models.AdjustmentRequest):
    admin.site.register(m)
