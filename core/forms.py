"""
Forms for the core app.
"""

from django import forms
from .models import Deduction, GlobalSettings

_INPUT  = "form-control"
_SELECT = "form-select form-control"


class GlobalSettingsForm(forms.ModelForm):
    class Meta:
        model = GlobalSettings
        fields = [
            # Pay rules
            "overtime_rate_multiplier",
            "holiday_rate_multiplier",
            "overtime_threshold_hours",
            # Scheduling defaults
            "default_lunch_duration_minutes",
            "week_start_day",
            # Payroll close day
            "payroll_close_weekday",
            "payroll_close_week",
            # Cycle anchors
            "schedule_cycle_start",
            "payroll_cycle_offset_days",
        ]
        widgets = {
            "overtime_rate_multiplier":     forms.NumberInput(attrs={"class": _INPUT, "step": "0.01"}),
            "holiday_rate_multiplier":      forms.NumberInput(attrs={"class": _INPUT, "step": "0.01"}),
            "overtime_threshold_hours":     forms.NumberInput(attrs={"class": _INPUT, "step": "0.01"}),
            "default_lunch_duration_minutes": forms.NumberInput(attrs={"class": _INPUT, "min": "0"}),
            "week_start_day":               forms.Select(attrs={"class": _SELECT}),
            "payroll_close_weekday":        forms.Select(attrs={"class": _SELECT}),
            "payroll_close_week":           forms.Select(attrs={"class": _SELECT}),
            "schedule_cycle_start":         forms.DateInput(attrs={"class": _INPUT, "type": "date"}),
            "payroll_cycle_offset_days":    forms.NumberInput(attrs={"class": _INPUT, "min": "0"}),
        }


class DeductionForm(forms.ModelForm):
    class Meta:
        model = Deduction
        fields = ["name", "deduction_type", "amount", "is_active"]
        widgets = {
            "name":           forms.TextInput(attrs={"class": _INPUT, "placeholder": "e.g. NIS, Health Surcharge"}),
            "deduction_type": forms.Select(attrs={"class": _SELECT}),
            "amount":         forms.NumberInput(attrs={"class": _INPUT, "step": "0.01", "min": "0"}),
            "is_active":      forms.CheckboxInput(attrs={"class": "custom-control-input"}),
        }
        labels = {
            "amount": "Amount (% or $)",
        }
