"""
Attendance domain models.

ActualShift — records what actually happened during a scheduled shift:
              clock-in, optional lunch window, and clock-out.
              Paid hours are computed from these timestamps at payroll close.
"""

import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from scheduling.models import ScheduledShift


class ActualShift(models.Model):
    """
    The recorded attendance for one ScheduledShift.

    Clock-in and clock-out are required to compute pay. Lunch timestamps
    are only expected (and validated) when the linked ScheduledShift has
    ``include_lunch=True``.

    All time values are stored as TimeField so they pair with the shift date
    from the related ScheduledShift. Shifts crossing midnight are not yet
    supported (deferred edge case).
    """

    scheduled_shift = models.OneToOneField(
        ScheduledShift,
        on_delete=models.CASCADE,
        related_name="actual_shift",
    )

    clock_in = models.TimeField(null=True, blank=True)
    lunch_start = models.TimeField(null=True, blank=True)
    lunch_end = models.TimeField(null=True, blank=True)
    clock_out = models.TimeField(null=True, blank=True)

    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Actual Shift"
        verbose_name_plural = "Actual Shifts"

    def __str__(self):
        return f"Actual: {self.scheduled_shift}"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self):
        errors = {}

        if self.clock_in and self.clock_out:
            if self.clock_out <= self.clock_in:
                errors["clock_out"] = "Clock-out must be after clock-in."

        if self.scheduled_shift.include_lunch:
            if self.lunch_start and self.lunch_end:
                if self.lunch_end <= self.lunch_start:
                    errors["lunch_end"] = "Lunch end must be after lunch start."
                if self.clock_in and self.lunch_start < self.clock_in:
                    errors["lunch_start"] = "Lunch cannot start before clock-in."
                if self.clock_out and self.lunch_end > self.clock_out:
                    errors["lunch_end"] = "Lunch cannot end after clock-out."

        if errors:
            raise ValidationError(errors)

    # ------------------------------------------------------------------
    # Computed paid hours
    # ------------------------------------------------------------------

    def _time_diff_hours(self, t_start, t_end):
        """Return decimal hours between two time values on the same day."""
        ref = datetime.date.today()
        start_dt = datetime.datetime.combine(ref, t_start)
        end_dt = datetime.datetime.combine(ref, t_end)
        minutes = (end_dt - start_dt).seconds // 60
        return Decimal(minutes) / Decimal(60)

    def paid_hours(self):
        """
        Return the total paid hours for this shift.

        Calculation:
            gross = clock_out - clock_in
            if include_lunch and both lunch timestamps recorded:
                deduct lunch_end - lunch_start
            else if include_lunch but no lunch timestamps:
                deduct GlobalSettings.default_lunch_duration_minutes

        Returns None if clock_in or clock_out has not been recorded yet.
        """
        if not self.clock_in or not self.clock_out:
            return None

        gross = self._time_diff_hours(self.clock_in, self.clock_out)

        if self.scheduled_shift.include_lunch:
            if self.lunch_start and self.lunch_end:
                lunch = self._time_diff_hours(self.lunch_start, self.lunch_end)
            else:
                from core.models import GlobalSettings
                lunch_minutes = GlobalSettings.get().default_lunch_duration_minutes
                lunch = Decimal(lunch_minutes) / Decimal(60)
            gross -= lunch

        return max(gross, Decimal("0"))
