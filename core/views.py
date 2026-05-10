import datetime
from decimal import Decimal

from django.views.generic import TemplateView

from core.models import GlobalSettings
from scheduling.models import PayrollCycle, ScheduledShift
from attendance.models import ActualShift
from scheduling.forms import AdHocShiftForm


class HomeView(TemplateView):
    """
    Dashboard home. Computes today's KPIs from live attendance data:
      - Employees currently on shift (clocked in, not yet clocked out)
      - Employees currently on lunch (lunch started, not ended)
      - Total paid hours worked today (completed shifts only)
      - Total wage cost today (paid_hours × employee pay_rate)

    Also passes:
      - show_close_payroll  — True only on the configured close day
      - adhoc_form          — AdHocShiftForm for the quick-add modal
      - active_cycle        — the open PayrollCycle (or None)
    """

    template_name = "pages/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = datetime.date.today()
        settings = GlobalSettings.get()

        # ── Active cycle ────────────────────────────────────────────────
        try:
            cycle = PayrollCycle.objects.get(status=PayrollCycle.Status.OPEN)
        except (PayrollCycle.DoesNotExist, PayrollCycle.MultipleObjectsReturned):
            cycle = None

        # ── Attendance queries for today ─────────────────────────────────
        todays_actuals = (
            ActualShift.objects
            .filter(scheduled_shift__date=today)
            .select_related(
                "scheduled_shift__employee",
                "scheduled_shift__employee__group",
            )
        )

        # Clocked in but not yet clocked out.
        on_shift_qs = todays_actuals.filter(
            clock_in__isnull=False,
            clock_out__isnull=True,
        )
        on_shift = [a.scheduled_shift.employee for a in on_shift_qs]

        # Lunch started but not yet ended.
        on_lunch_qs = todays_actuals.filter(
            lunch_start__isnull=False,
            lunch_end__isnull=True,
        )
        on_lunch = [a.scheduled_shift.employee for a in on_lunch_qs]

        # Completed shifts: compute paid hours + wage cost in Python.
        completed = todays_actuals.filter(clock_out__isnull=False)
        total_hours = Decimal("0")
        total_cost = Decimal("0")
        for actual in completed:
            hours = actual.paid_hours()
            if hours:
                total_hours += hours
                total_cost += hours * actual.scheduled_shift.employee.pay_rate

        # ── Show "Close Payroll" button? ─────────────────────────────────
        show_close_payroll = False
        if cycle:
            in_correct_week = False
            week2_start = cycle.schedule_start + datetime.timedelta(days=7)
            if settings.payroll_close_week == 1:
                in_correct_week = cycle.schedule_start <= today < week2_start
            else:
                in_correct_week = week2_start <= today <= cycle.schedule_end

            show_close_payroll = (
                in_correct_week
                and today.weekday() == settings.payroll_close_weekday
            )

        ctx.update({
            "today": today,
            "active_cycle": cycle,
            "on_shift": on_shift,
            "on_lunch": on_lunch,
            "total_hours": total_hours,
            "total_cost": total_cost,
            "show_close_payroll": show_close_payroll,
            "adhoc_form": AdHocShiftForm(),
        })
        return ctx
