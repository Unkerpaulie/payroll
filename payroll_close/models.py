"""
Payroll close-off domain models.

PayrollRun   — the close-off event for a PayrollCycle; triggers generation
               of all payslips and the consolidated paysheet.
Payslip      — one employee's itemised earnings for the cycle.
PayslipLine  — one row of a Payslip (regular hours, overtime, holiday, deduction).
PaysheetLine — a single-row summary per employee on the full paysheet; computed
               from Payslip totals and stored for reporting/printing.
"""

from decimal import Decimal

from django.db import models

from employees.models import Employee
from scheduling.models import PayrollCycle


class PayrollRun(models.Model):
    """
    Records the close-off of a PayrollCycle. Once created, the cycle is
    considered closed and its shifts become immutable for pay purposes.
    """

    cycle = models.OneToOneField(
        PayrollCycle,
        on_delete=models.PROTECT,
        related_name="payroll_run",
    )
    run_date = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Payroll Run"
        verbose_name_plural = "Payroll Runs"

    def __str__(self):
        return f"Payroll Run — {self.cycle} on {self.run_date}"


class Payslip(models.Model):
    """
    One employee's payslip for a PayrollRun. Stores pre-computed totals so
    the payslip can be reprinted without re-calculating from raw attendance.
    """

    run = models.ForeignKey(
        PayrollRun,
        on_delete=models.CASCADE,
        related_name="payslips",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="payslips",
    )

    # Snapshot of the rate at the time of close (rate may change later).
    pay_rate_snapshot = models.DecimalField(max_digits=8, decimal_places=2)

    # Computed totals
    regular_hours = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0"))
    overtime_hours = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0"))
    holiday_hours = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0"))
    gross_pay = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    net_pay = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))

    class Meta:
        unique_together = [("run", "employee")]
        ordering = ["employee__last_name", "employee__first_name"]
        verbose_name = "Payslip"
        verbose_name_plural = "Payslips"

    def __str__(self):
        return f"Payslip — {self.employee} | {self.run}"


class PayslipLine(models.Model):
    """
    Itemised line on a Payslip — one line per shift, showing the date,
    hours worked, rate applied, and line total.
    """

    class LineType(models.TextChoices):
        REGULAR = "regular", "Regular"
        OVERTIME = "overtime", "Overtime"
        HOLIDAY = "holiday", "Holiday"
        DEDUCTION = "deduction", "Deduction"

    payslip = models.ForeignKey(
        Payslip,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    line_type = models.CharField(max_length=10, choices=LineType.choices)
    date = models.DateField()
    hours = models.DecimalField(max_digits=6, decimal_places=2)
    rate = models.DecimalField(max_digits=8, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["date", "line_type"]
        verbose_name = "Payslip Line"
        verbose_name_plural = "Payslip Lines"

    def __str__(self):
        return f"{self.date} | {self.line_type} | {self.hours}h @ {self.rate} = {self.amount}"
