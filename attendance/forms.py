from django import forms

from .models import Employee, LeaveRequest, AdjustmentRequest

DAYS = [(0, "Mon"), (1, "Tue"), (2, "Wed"), (3, "Thu"), (4, "Fri"), (5, "Sat"), (6, "Sun")]
DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
TIME = forms.TimeInput(attrs={"type": "time"}, format="%H:%M")


class EmployeeForm(forms.Form):
    name = forms.CharField(max_length=60)
    department = forms.CharField(max_length=60, required=False)
    designation = forms.CharField(max_length=60, required=False)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=30, required=False)

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].replace("|", " ").split())
        if not name:
            raise forms.ValidationError("Name is required.")
        return name

    def clean_department(self):
        return " ".join(self.cleaned_data.get("department", "").split())


class _ActiveEmployeeMixin:
    def _set_employees(self):
        self.fields["employee"].queryset = Employee.objects.filter(status="active")


class LeaveForm(forms.ModelForm, _ActiveEmployeeMixin):
    class Meta:
        model = LeaveRequest
        fields = ["employee", "leave_type", "planned", "start_date", "end_date", "reason"]
        widgets = {"start_date": DATE, "end_date": DATE}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_employees()

    def clean(self):
        data = super().clean()
        s, e = data.get("start_date"), data.get("end_date")
        if s and e:
            if e < s:
                raise forms.ValidationError("End date cannot be before the start date.")
            if (e - s).days > 120:
                raise forms.ValidationError("A leave request cannot be longer than 120 days.")
        return data


class AdjustmentForm(forms.ModelForm, _ActiveEmployeeMixin):
    class Meta:
        model = AdjustmentRequest
        fields = ["employee", "date", "check_in", "check_out", "reason"]
        widgets = {"date": DATE, "check_in": TIME, "check_out": TIME}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_employees()

    def clean(self):
        data = super().clean()
        ci, co = data.get("check_in"), data.get("check_out")
        if not ci and not co:
            raise forms.ValidationError("Enter a check-in time, a check-out time, or both.")
        if ci and co and co < ci:
            raise forms.ValidationError("Check-out cannot be before check-in.")
        return data


class SettingsForm(forms.Form):
    start_time = forms.TimeField(widget=TIME, label="Office start time")
    grace_minutes = forms.IntegerField(min_value=0, max_value=180, label="Grace period (minutes)")
    workdays = forms.TypedMultipleChoiceField(
        choices=DAYS, coerce=int, widget=forms.CheckboxSelectMultiple, label="Working days"
    )


class ReportForm(forms.Form):
    start = forms.DateField(widget=DATE)
    end = forms.DateField(widget=DATE)

    def clean(self):
        data = super().clean()
        s, e = data.get("start"), data.get("end")
        if s and e:
            if e < s:
                raise forms.ValidationError("End date cannot be before the start date.")
            if (e - s).days > 366:
                raise forms.ValidationError("Choose a range of at most one year.")
        return data
