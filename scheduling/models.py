"""
Scheduling domain models.

PayrollCycle    — the universal bi-weekly cycle (has schedule + payroll date spans).
Schedule        — one group's schedule for a payroll cycle.
Week            — one of the two weeks within a schedule (week 1 or week 2).
Day             — a single calendar date within a Week; may be flagged as a holiday.
ScheduledShift  — a single employee shift on a specific Day.
                  Enforces one shift per employee per Day (and by extension per date)
                  via a unique constraint plus cross-group clean() validation.
"""

import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from employees.models import Employee, Group


class PayrollCycle(models.Model):
    """
    The universal bi-weekly cycle. There is one active cycle at a time.

    Schedule cycle  : schedule_start → schedule_end  (14 days, Sun–Sat by default)
    Payroll cycle   : payroll_start  → payroll_end   (offset by GlobalSettings)

    Paychecks are disbursed on ``pay_date`` (typically the Friday following
    payroll_end).
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    # Schedule window
    schedule_start = models.DateField()
    schedule_end = models.DateField()

    # Payroll window (may differ from schedule window)
    payroll_start = models.DateField()
    payroll_end = models.DateField()
    pay_date = models.DateField(help_text="Expected paycheck disbursement date.")

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-schedule_start"]
        verbose_name = "Payroll Cycle"
        verbose_name_plural = "Payroll Cycles"

    def __str__(self):
        return (
            f"Cycle {self.schedule_start.strftime('%b %d')}–"
            f"{self.schedule_end.strftime('%b %d, %Y')} [{self.status}]"
        )

    @property
    def is_open(self):
        return self.status == self.Status.OPEN


class Schedule(models.Model):
    """
    One group's schedule for a PayrollCycle. A cycle has one Schedule per Group.
    """

    cycle = models.ForeignKey(
        PayrollCycle,
        on_delete=models.CASCADE,
        related_name="schedules",
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.PROTECT,
        related_name="schedules",
    )
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [("cycle", "group")]
        verbose_name = "Schedule"
        verbose_name_plural = "Schedules"

    def __str__(self):
        return f"{self.group} — {self.cycle}"


class Week(models.Model):
    """
    One of the two 7-day weeks within a Schedule (WEEK_1 or WEEK_2).
    ``start_date`` is the Sunday (or configured week start day) that opens
    the week.
    """

    class WeekNumber(models.IntegerChoices):
        WEEK_1 = 1, "Week 1"
        WEEK_2 = 2, "Week 2"

    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name="weeks",
    )
    week_number = models.IntegerField(choices=WeekNumber.choices)
    start_date = models.DateField()

    class Meta:
        unique_together = [("schedule", "week_number")]
        ordering = ["week_number"]
        verbose_name = "Week"
        verbose_name_plural = "Weeks"

    def __str__(self):
        return f"{self.schedule} — Week {self.week_number}"

    @property
    def end_date(self):
        return self.start_date + datetime.timedelta(days=6)


class Day(models.Model):
    """
    A single calendar date within a Week.

    ``is_holiday`` flags the day as a public holiday so that the schedule
    builder and payroll engine can apply the holiday_rate_multiplier from
    GlobalSettings instead of the standard rate.

    ``holiday_name`` is optional descriptive text shown in the schedule UI.
    """

    week = models.ForeignKey(
        Week,
        on_delete=models.CASCADE,
        related_name="days",
    )
    date = models.DateField()
    is_holiday = models.BooleanField(
        default=False,
        help_text="Flag this date as a public holiday.",
    )
    holiday_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional name shown on the schedule (e.g. 'Christmas Day').",
    )

    class Meta:
        unique_together = [("week", "date")]
        ordering = ["date"]
        verbose_name = "Day"
        verbose_name_plural = "Days"

    def __str__(self):
        label = self.date.strftime("%a, %b %d, %Y")
        if self.is_holiday:
            suffix = f" – {self.holiday_name}" if self.holiday_name else " [Holiday]"
            return label + suffix
        return label


class ScheduledShift(models.Model):
    """
    A single planned shift for one employee on a specific Day.

    Conflict rule: one shift per employee per calendar date (system-wide).
      - unique_together = [("employee", "day")] enforces uniqueness at DB level
        within a single Day object.
      - clean() catches the cross-group case where two Day objects share the
        same calendar date (different groups, same cycle).

    ``include_lunch`` — when True, the default lunch duration (from GlobalSettings)
    is subtracted from gross hours; the clock-in board generates a
    lunch_start / lunch_end button pair for this shift.

    The shift date is obtained via ``shift.day.date`` — it is not stored again
    on this model to keep the data normalised.
    """

    day = models.ForeignKey(
        Day,
        on_delete=models.CASCADE,
        related_name="shifts",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="scheduled_shifts",
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    include_lunch = models.BooleanField(
        default=False,
        help_text="Deduct the default lunch duration from total scheduled hours.",
    )
    is_adhoc = models.BooleanField(
        default=False,
        help_text=(
            "True when this shift was added on the fly (not part of the original schedule). "
            "Ad-hoc shifts appear on the time-keeping board and count toward payroll "
            "but are visually distinguished on schedule views."
        ),
    )

    class Meta:
        # DB-level: one shift per employee per Day object.
        unique_together = [("employee", "day")]
        ordering = ["day__date", "start_time"]
        verbose_name = "Scheduled Shift"
        verbose_name_plural = "Scheduled Shifts"

    def __str__(self):
        date = self.day.date
        return (
            f"{self.employee} on {date} "
            f"{self.start_time.strftime('%H:%M')}–{self.end_time.strftime('%H:%M')}"
        )

    def clean(self):
        """
        Cross-group validation: ensure this employee has no shift on the same
        calendar date in any other group's schedule.
        """
        if not self.day_id:
            return
        qs = ScheduledShift.objects.filter(
            employee=self.employee,
            day__date=self.day.date,
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.exists():
            raise ValidationError(
                f"{self.employee.full_name} already has a shift scheduled on {self.day.date}."
            )

    def gross_hours(self, lunch_minutes=None):
        """
        Return scheduled paid hours as a Decimal.
        If ``include_lunch`` is True, subtract ``lunch_minutes``
        (falls back to GlobalSettings.default_lunch_duration_minutes).
        """
        date = self.day.date
        start_dt = datetime.datetime.combine(date, self.start_time)
        end_dt = datetime.datetime.combine(date, self.end_time)
        total_minutes = (end_dt - start_dt).seconds // 60
        if self.include_lunch:
            if lunch_minutes is None:
                from core.models import GlobalSettings
                lunch_minutes = GlobalSettings.get().default_lunch_duration_minutes
            total_minutes -= lunch_minutes
        return Decimal(max(total_minutes, 0)) / Decimal(60)
