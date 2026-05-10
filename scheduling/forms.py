"""
Scheduling forms.

CycleCreateForm  — opens a new bi-weekly PayrollCycle.
ShiftForm        — adds a scheduled shift in the builder (AJAX-backed).
AdHocShiftForm   — creates an unscheduled (ad-hoc) shift on the fly.
"""

import datetime

from django import forms
from django.core.exceptions import ValidationError

from employees.models import Employee, Group
from .models import Day, PayrollCycle, Schedule, ScheduledShift, Week


_INPUT  = "form-control"
_SELECT = "form-control"


# ── New cycle ─────────────────────────────────────────────────────────────────

class CycleCreateForm(forms.Form):
    schedule_start = forms.DateField(
        label="Schedule Start Date",
        help_text="First day of the 14-day schedule window (should be the configured week-start day).",
        widget=forms.DateInput(attrs={"class": _INPUT, "type": "date"}),
    )
    pay_date = forms.DateField(
        label="Pay Date",
        help_text="Date employees receive their paycheques for this cycle.",
        widget=forms.DateInput(attrs={"class": _INPUT, "type": "date"}),
    )

    def clean_schedule_start(self):
        date = self.cleaned_data["schedule_start"]
        if PayrollCycle.objects.filter(status=PayrollCycle.Status.OPEN).exists():
            raise ValidationError(
                "There is already an open payroll cycle. Close it before starting a new one."
            )
        return date


# ── Builder shift form ────────────────────────────────────────────────────────

class ShiftForm(forms.Form):
    """Used by the schedule builder AJAX endpoint to create a single shift."""

    employee = forms.ModelChoiceField(
        queryset=Employee.objects.none(),   # set in view
        widget=forms.Select(attrs={"class": _SELECT}),
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"class": _INPUT, "type": "time"}),
    )
    end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"class": _INPUT, "type": "time"}),
    )
    include_lunch = forms.BooleanField(
        required=False,
        label="Include Lunch Break",
        widget=forms.CheckboxInput(attrs={"class": "custom-control-input"}),
    )

    def __init__(self, *args, group=None, **kwargs):
        super().__init__(*args, **kwargs)
        if group:
            self.fields["employee"].queryset = (
                Employee.objects.filter(group=group, status=Employee.Status.ACTIVE)
                .order_by("last_name", "first_name")
            )

    def clean(self):
        cleaned = super().clean()
        s, e = cleaned.get("start_time"), cleaned.get("end_time")
        if s and e and e <= s:
            raise ValidationError("End time must be after start time.")
        return cleaned


class AdHocShiftForm(forms.Form):
    """
    Creates a ScheduledShift with is_adhoc=True inside the Week of the
    currently open PayrollCycle that contains the selected date.

    Validation ensures:
      - There is an open cycle.
      - The selected date falls within that cycle's schedule window.
      - The employee is not already scheduled on that date.
      - end_time is after start_time.
    """

    employee = forms.ModelChoiceField(
        queryset=Employee.objects.filter(status=Employee.Status.ACTIVE).order_by(
            "last_name", "first_name"
        ),
        label="Employee",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    date = forms.DateField(
        initial=datetime.date.today,
        label="Date",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    start_time = forms.TimeField(
        label="Start Time",
        widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
    )
    end_time = forms.TimeField(
        label="End Time",
        widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
    )
    include_lunch = forms.BooleanField(
        required=False,
        label="Include Lunch Break",
        widget=forms.CheckboxInput(attrs={"class": "custom-control-input"}),
    )

    def clean(self):
        cleaned = super().clean()
        employee = cleaned.get("employee")
        date = cleaned.get("date")
        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")

        if start_time and end_time and end_time <= start_time:
            raise ValidationError("End time must be after start time.")

        if not date:
            return cleaned

        # Ensure an open cycle exists and the date falls within it.
        try:
            cycle = PayrollCycle.objects.get(status=PayrollCycle.Status.OPEN)
        except PayrollCycle.DoesNotExist:
            raise ValidationError("There is no open payroll cycle. Start a new cycle first.")
        except PayrollCycle.MultipleObjectsReturned:
            raise ValidationError("Multiple open cycles found. Please resolve this in admin.")

        if not (cycle.schedule_start <= date <= cycle.schedule_end):
            raise ValidationError(
                f"The selected date must fall within the current cycle "
                f"({cycle.schedule_start} – {cycle.schedule_end})."
            )

        # Check the employee isn't already scheduled that day.
        if employee and ScheduledShift.objects.filter(employee=employee, day__date=date).exists():
            raise ValidationError(
                f"{employee.full_name} already has a shift on {date}."
            )

        cleaned["_cycle"] = cycle
        return cleaned

    def save(self):
        """
        Locate the correct Week for the date and create the ScheduledShift.
        Returns the newly created ScheduledShift instance.
        """
        data = self.cleaned_data
        cycle = data["_cycle"]
        employee = data["employee"]
        date = data["date"]

        # Find which Week (1 or 2) this date belongs to, across any group's
        # schedule in this cycle. Ad-hoc shifts use the employee's own group
        # schedule; if no schedule exists for their group, fall back to any
        # Week in the cycle that covers the date.
        week = (
            Week.objects.filter(
                schedule__cycle=cycle,
                schedule__group=employee.group,
                start_date__lte=date,
            )
            .filter(start_date__lte=date)
            .order_by("-start_date")
            .first()
        )

        if week is None:
            # Fallback: any week in the cycle covering this date.
            week = (
                Week.objects.filter(schedule__cycle=cycle, start_date__lte=date)
                .order_by("-start_date")
                .first()
            )

        if week is None:
            raise ValidationError(
                "No schedule weeks found for this cycle. Build a schedule first."
            )

        # Get or create the Day object for this date within the located week.
        day, _ = Day.objects.get_or_create(week=week, date=date)

        return ScheduledShift.objects.create(
            day=day,
            employee=employee,
            start_time=data["start_time"],
            end_time=data["end_time"],
            include_lunch=data.get("include_lunch", False),
            is_adhoc=True,
        )
