import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import TemplateView, UpdateView, View

from core.models import GlobalSettings
from core.forms import GlobalSettingsForm
from scheduling.models import PayrollCycle, ScheduledShift
from attendance.models import ActualShift
from scheduling.forms import AdHocShiftForm


class HomeView(LoginRequiredMixin, TemplateView):
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
            .filter(scheduled_shift__day__date=today)
            .select_related(
                "scheduled_shift__day",
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


# ---------------------------------------------------------------------------
# KPI JSON endpoint — called by the dashboard every 60 s
# ---------------------------------------------------------------------------

def _compute_live_kpis():
    """
    Return (total_hours, total_cost) including shifts currently in progress.

    Rules:
    - Completed shifts (clock_out set):   use paid_hours() — fixed value.
    - In-progress shifts (clock_in set, clock_out None):
        * Employee is on lunch (lunch_start set, lunch_end None):
          count only clock_in → lunch_start (time frozen during break).
        * Otherwise: count clock_in → now.
        * If a full lunch was already taken (both timestamps set) and
          include_lunch is True, deduct that completed lunch window.
    - Employees on lunch do NOT accumulate hours/cost during the break.
    """
    today = datetime.date.today()
    now_time = datetime.datetime.now().time()
    ref = today  # used only to combine with TimeField values

    todays_actuals = (
        ActualShift.objects
        .filter(scheduled_shift__day__date=today)
        .select_related(
            "scheduled_shift__day",
            "scheduled_shift__employee",
        )
    )

    total_hours = Decimal("0")
    total_cost = Decimal("0")

    for actual in todays_actuals:
        if not actual.clock_in:
            continue

        emp = actual.scheduled_shift.employee

        if actual.clock_out:
            # ── Completed shift — use the authoritative paid_hours() ──────
            h = actual.paid_hours()
            if h:
                total_hours += h
                total_cost += h * emp.pay_rate
        else:
            # ── In-progress shift ─────────────────────────────────────────
            on_lunch = actual.lunch_start and not actual.lunch_end

            if on_lunch:
                # Time stopped at lunch start
                end_for_calc = actual.lunch_start
            else:
                end_for_calc = now_time

            start_dt = datetime.datetime.combine(ref, actual.clock_in)
            end_dt   = datetime.datetime.combine(ref, end_for_calc)
            gross = Decimal((end_dt - start_dt).seconds) / Decimal(3600)

            # Deduct a *completed* lunch window already taken this shift
            if (actual.scheduled_shift.include_lunch
                    and actual.lunch_start and actual.lunch_end):
                ls = datetime.datetime.combine(ref, actual.lunch_start)
                le = datetime.datetime.combine(ref, actual.lunch_end)
                gross -= Decimal((le - ls).seconds) / Decimal(3600)

            h = max(gross, Decimal("0"))
            total_hours += h
            total_cost += h * emp.pay_rate

    return total_hours, total_cost


class KpiView(LoginRequiredMixin, View):
    """Return live hours-worked and wage-cost as JSON for the dashboard poll."""

    def get(self, request):
        total_hours, total_cost = _compute_live_kpis()
        return JsonResponse({
            "total_hours": str(round(total_hours, 2)),
            "total_cost":  str(round(total_cost, 2)),
        })


# ---------------------------------------------------------------------------
# Settings (singleton GlobalSettings)
# ---------------------------------------------------------------------------

class SettingsView(LoginRequiredMixin, UpdateView):
    """
    Edit the singleton GlobalSettings record.
    get_object() always fetches (or creates) pk=1 so no URL pk is needed.
    """

    model = GlobalSettings
    form_class = GlobalSettingsForm
    template_name = "pages/settings.html"
    success_url = reverse_lazy("core:settings")

    def get_object(self, queryset=None):
        return GlobalSettings.get()

    def form_valid(self, form):
        messages.success(self.request, "Settings saved successfully.")
        return super().form_valid(form)
