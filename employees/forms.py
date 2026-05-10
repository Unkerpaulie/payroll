"""
Forms for the employees app.
"""

from django import forms
from .models import Employee, Group, Unavailability

_INPUT = "form-control"
_SELECT = "form-select form-control"


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": _INPUT, "placeholder": "e.g. Kitchen"}),
            "description": forms.Textarea(attrs={"class": _INPUT, "rows": 3}),
        }


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "first_name", "last_name", "email", "phone",
            "group", "pay_rate", "status", "hire_date", "notes",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": _INPUT}),
            "last_name":  forms.TextInput(attrs={"class": _INPUT}),
            "email":      forms.EmailInput(attrs={"class": _INPUT}),
            "phone":      forms.TextInput(attrs={"class": _INPUT}),
            "group":      forms.Select(attrs={"class": _SELECT}),
            "pay_rate":   forms.NumberInput(attrs={"class": _INPUT, "step": "0.01", "min": "0"}),
            "status":     forms.Select(attrs={"class": _SELECT}),
            "hire_date":  forms.DateInput(attrs={"class": _INPUT, "type": "date"}),
            "notes":      forms.Textarea(attrs={"class": _INPUT, "rows": 3}),
        }


class UnavailabilityForm(forms.ModelForm):
    class Meta:
        model = Unavailability
        fields = ["start_date", "end_date", "reason"]
        widgets = {
            "start_date": forms.DateInput(attrs={"class": _INPUT, "type": "date"}),
            "end_date":   forms.DateInput(attrs={"class": _INPUT, "type": "date"}),
            "reason":     forms.TextInput(attrs={"class": _INPUT, "placeholder": "Optional reason"}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            raise forms.ValidationError("End date cannot be before start date.")
        return cleaned
