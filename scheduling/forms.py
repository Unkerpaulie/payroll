"""
Scheduling forms.

CycleCreateForm  — opens a new bi-weekly PayrollCycle.
ShiftForm        — adds a scheduled shift in the builder (AJAX-backed).
AdHocShiftForm   — creates an unscheduled (ad-hoc) shift on the fly.
"""

import datetime

from django import forms
from django.core.exceptions import ValidationError

from employees.models import Employee, Group, Unavailability, Unavailability
from .models import Day, PayrollCycle, Schedule, ScheduledShift, Week


_INPUT  = "form-control"
_SELECT = "form-control"


# ── New cycle ─────────────────────────────────────────────────────────────────

class CycleCreateForm(forms.Form):
    schedule_start = forms.DateField(
        label="Schedule Start Date",
        # type="text" so Flatpickr controls the picker; value is still YYYY-MM-DD
        widget=forms.DateInput(attrs={
            "class": _INPUT,
            "type": "text",
            "autocomplete": "off",
            "readonly": "readonly",
            "id": "id_schedule_start",
        }),
    )

    def clean_schedule_start(self):
        from core.models import GlobalSettings
        date = self.cleaned_data["schedule_start"]

        settings = GlobalSettings.get()
        anchor = settings.schedule_cycle_start
        week_start_day = settings.week_start_day  # 0=Mon … 6=Sun (same as Python weekday())

        # Must be the configured week-start day of week.
        if date.weekday() != week_start_day:
            day_name = dict(GlobalSettings.WeekStartDay.choices)[week_start_day]
            raise ValidationError(
                f"The schedule must start on a {day_name} (matching the Week Starts On setting)."
            )

        # If an anchor is configured, must be a valid 14-day multiple from it.
        if anchor:
            diff = (date - anchor).days
            if diff < 0 or diff % 14 != 0:
                raise ValidationError(
                    "The selected date is not a valid bi-weekly start from the configured cycle anchor."
                )

        # Block only true duplicates (same start date already recorded).
        # A new cycle started while another is open will be created as Pending —
        # that logic lives in CycleCreateView.form_valid.
        if PayrollCycle.objects.filter(schedule_start=date).exists():
            pass  # form_valid will redirect to the existing cycle.

        return date


# ── Builder shift form ────────────────────────────────────────────────────────

class ShiftForm(forms.Form):
    """Used by the schedule builder AJAX endpoint to create a single shift."""

    employee = forms.ModelChoiceField(
        queryset=Employee.objects.none(),   # populated in __init__
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

    def __init__(self, *args, group=None, date=None, **kwargs):
        super().__init__(*args, **kwargs)
        if group:
            qs = Employee.objects.filter(group=group, status=Employee.Status.ACTIVE)
            if date:
                unavailable = Unavailability.objects.filter(
                    start_date__lte=date,
                    end_date__gte=date,
                ).values_list("employee_id", flat=True)
                qs = qs.exclude(pk__in=unavailable)
            self.fields["employee"].queryset = qs.order_by("last_name", "first_name")

    def clean(self):
        cleaned = super().clean()
        s, e = cleaned.get("start_time"), cleaned.get("end_time")
        if s and e and e <= s:
            raise ValidationError("End time must be after start time.")
        return cleaned


class AdHocShiftForm(forms.Form):
    """
    Creates a ScheduledShift with is_adhoc=True for TODAY inside the currently
    open PayrollCycle.

    The date is always today — it is not a form field and cannot be submitted
    or overridden by the user.  Validation ensures:
      - There is an open cycle.
      - Today falls within that cycle's schedule window.
      - The employee is not already scheduled today.
      - The employee has no Unavailability record covering today.
      - end_time is after start_time.

    The employee dropdown is pre-filtered at form instantiation time to show
    only employees who are active, not already scheduled today, and not marked
    unavailable today — so invalid choices never appear in the list.
    """

    employee = forms.ModelChoiceField(
        queryset=Employee.objects.none(),   # populated in __init__
        label="Employee",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    # No 'date' field — always today; set in clean() and unavailable to the user.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = datetime.date.today()

        # Employees already on the schedule for today (any shift, any group).
        already_scheduled = ScheduledShift.objects.filter(
            day__date=today
        ).values_list("employee_id", flat=True)

        # Employees whose unavailability window covers today.
        unavailable = Unavailability.objects.filter(
            start_date__lte=today,
            end_date__gte=today,
        ).values_list("employee_id", flat=True)

        self.fields["employee"].queryset = (
            Employee.objects
            .filter(status=Employee.Status.ACTIVE)
            .exclude(pk__in=already_scheduled)
            .exclude(pk__in=unavailable)
            .order_by("last_name", "first_name")
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
        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")

        if start_time and end_time and end_time <= start_time:
            raise ValidationError("End time must be after start time.")

        # Date is always today — not supplied by the user.
        date = datetime.date.today()
        cleaned["date"] = date

        # Ensure an open cycle exists and today falls within it.
        try:
            cycle = PayrollCycle.objects.get(status=PayrollCycle.Status.OPEN)
        except PayrollCycle.DoesNotExist:
            raise ValidationError("There is no open payroll cycle. Start a new cycle first.")
        except PayrollCycle.MultipleObjectsReturned:
            raise ValidationError("Multiple open cycles found. Please resolve this in admin.")

        if not (cycle.schedule_start <= date <= cycle.schedule_end):
            raise ValidationError(
                f"Today ({date}) is not within the current open cycle "
                f"({cycle.schedule_start} – {cycle.schedule_end}). "
                f"Ad-hoc shifts can only be added for today."
            )

        # Check the employee isn't already scheduled today.
        if employee and ScheduledShift.objects.filter(employee=employee, day__date=date).exists():
            raise ValidationError(
                f"{employee.full_name} already has a shift scheduled for today."
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
