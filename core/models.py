"""
Core models.

Deduction       — a named payroll deduction (percentage or fixed amount).
                  Employees may be individually exempted via DeductionExemption
                  in the employees app.

GlobalSettings  — singleton table (enforced by always using pk=1) that
                  holds every project-wide configuration value: pay multipliers,
                  lunch defaults, and the anchor dates that define the bi-weekly
                  schedule and payroll cycles.
"""

from django.core.exceptions import ValidationError
from django.db import models


# ── Deduction ─────────────────────────────────────────────────────────────────

class Deduction(models.Model):
    """
    A named payroll deduction applied at close-off.

    ``deduction_type`` controls how ``amount`` is interpreted:
      - PERCENTAGE : amount is treated as a percentage of gross pay (e.g. 10.00 = 10 %)
      - FIXED      : amount is a flat dollar value deducted regardless of hours
    """

    class DeductionType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage (%)"
        FIXED = "fixed", "Fixed Amount ($)"

    name = models.CharField(max_length=100, unique=True)
    deduction_type = models.CharField(
        max_length=10,
        choices=DeductionType.choices,
        default=DeductionType.PERCENTAGE,
        verbose_name="Type",
    )
    amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Percentage value (e.g. 10.00 = 10 %) or flat dollar amount.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive deductions are excluded from payroll calculations.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Deduction"
        verbose_name_plural = "Deductions"

    def __str__(self):
        return f"{self.name} ({self.display_amount})"

    @property
    def display_amount(self):
        if self.deduction_type == self.DeductionType.PERCENTAGE:
            return f"{self.amount}%"
        return f"${self.amount}"


# ── GlobalSettings ────────────────────────────────────────────────────────────

class GlobalSettings(models.Model):
    """
    Singleton configuration record. Retrieve with GlobalSettings.get().

    Cycle anchor logic
    ------------------
    ``schedule_cycle_start`` is the Sunday that began the very first
    schedule cycle. Every subsequent cycle is exactly 14 days later.

    ``payroll_cycle_offset_days`` is the number of days *before* the
    schedule cycle start that the payroll cycle opens (typically 3,
    so the payroll cycle opens the Thursday of the previous cycle's
    week 2 and closes the Wednesday of the current week 2).
    """

    # --- Pay multipliers -------------------------------------------------
    overtime_rate_multiplier = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default="1.50",
        help_text="e.g. 1.5 for time-and-a-half.",
    )
    holiday_rate_multiplier = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default="2.00",
        help_text="e.g. 2.0 for double time on public holidays.",
    )
    overtime_threshold_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default="40.00",
        help_text="Weekly hours above which the overtime rate applies.",
    )

    # --- Scheduling defaults ---------------------------------------------
    default_lunch_duration_minutes = models.PositiveIntegerField(
        default=30,
        help_text="Minutes deducted from a shift when 'include lunch break' is checked.",
    )

    class WeekStartDay(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    week_start_day = models.IntegerField(
        choices=WeekStartDay.choices,
        default=WeekStartDay.SUNDAY,
        help_text="Day that each schedule week begins on.",
    )

    # --- Payroll close day -----------------------------------------------
    # Identifies which day of which week the "Close Payroll" button appears.
    # E.g. Thursday (3) of Week 2 means the button shows on the Thursday
    # that falls within the second week of the active schedule cycle.

    class CloseWeek(models.IntegerChoices):
        WEEK_1 = 1, "Week 1"
        WEEK_2 = 2, "Week 2"

    payroll_close_weekday = models.IntegerField(
        choices=WeekStartDay.choices,
        default=3,  # Thursday
        help_text="Day of the week on which payroll close-off is triggered.",
    )
    payroll_close_week = models.IntegerField(
        choices=CloseWeek.choices,
        default=CloseWeek.WEEK_2,
        help_text="Which week of the schedule cycle the close day falls in.",
    )

    # --- Cycle anchors ---------------------------------------------------
    schedule_cycle_start = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "The Sunday (or configured week start) of the very first schedule cycle. "
            "All future cycles are calculated as 14-day multiples from this date."
        ),
    )
    payroll_cycle_offset_days = models.IntegerField(
        default=3,
        help_text=(
            "Days before the schedule cycle start that the payroll cycle opens. "
            "Default 3 = the Thursday of the previous cycle's week 2."
        ),
    )

    class Meta:
        verbose_name = "Global Settings"
        verbose_name_plural = "Global Settings"

    # ------------------------------------------------------------------
    # Singleton enforcement
    # ------------------------------------------------------------------

    def clean(self):
        if not self.pk and GlobalSettings.objects.exists():
            raise ValidationError(
                "Only one GlobalSettings record is allowed. Edit the existing one."
            )

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Prevent accidental deletion from admin.
        pass

    @classmethod
    def get(cls):
        """Return the singleton instance, creating defaults if absent."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Global Settings"

