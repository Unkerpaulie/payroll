"""
Employee domain models.

Group       — a named collection of employees (department / employee class).
Employee    — the core employee record including pay rate and group membership.
Unavailability — date-bounded periods during which an employee must not be scheduled.
"""

from django.db import models
from django.conf import settings


class Group(models.Model):
    """
    A named group of employees, e.g. 'Kitchen', 'Front of House', 'Management'.
    Schedules are built per group.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Group"
        verbose_name_plural = "Groups"

    def __str__(self):
        return self.name


class Employee(models.Model):
    """
    Core employee record. Pay rate is stored here and applied at payroll
    close-off time. A single group assignment is enforced; cross-group
    coverage can be modelled through schedule overrides in a later iteration.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    # Personal info
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    # Employment
    group = models.ForeignKey(
        Group,
        on_delete=models.PROTECT,
        related_name="employees",
    )
    pay_rate = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Hourly rate of pay.",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    hire_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = "Employee"
        verbose_name_plural = "Employees"

    def __str__(self):
        return f"{self.last_name}, {self.first_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def is_available_on(self, date):
        """Return True if the employee has no unavailability covering ``date``."""
        return not self.unavailabilities.filter(
            start_date__lte=date,
            end_date__gte=date,
        ).exists()


class Unavailability(models.Model):
    """
    A period during which an employee must not appear in the scheduling UI.
    The period is inclusive on both ends.
    """

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="unavailabilities",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["start_date"]
        verbose_name = "Unavailability"
        verbose_name_plural = "Unavailabilities"

    def __str__(self):
        return f"{self.employee} unavailable {self.start_date} – {self.end_date}"
