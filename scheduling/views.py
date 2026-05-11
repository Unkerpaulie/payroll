import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, ListView, View
from django.views.generic.edit import FormView

from core.models import GlobalSettings
from employees.models import Employee, Group, Unavailability
from .forms import AdHocShiftForm, CycleCreateForm, ShiftForm
from .models import Day, PayrollCycle, Schedule, ScheduledShift, Week


# ── Cycle list ────────────────────────────────────────────────────────────────

class CycleListView(LoginRequiredMixin, ListView):
    model = PayrollCycle
    template_name = "scheduling/cycle_list.html"
    context_object_name = "cycles"
    ordering = ["-schedule_start"]


# ── New cycle ─────────────────────────────────────────────────────────────────

class CycleCreateView(LoginRequiredMixin, FormView):
    form_class = CycleCreateForm
    template_name = "scheduling/cycle_form.html"

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _next_valid_start(anchor, today=None):
        """Return the next bi-weekly start date on or after tomorrow."""
        if anchor is None:
            return None
        today = today or datetime.date.today()
        days_since = (today - anchor).days
        if days_since < 0:
            return anchor
        cycle_num = days_since // 14
        candidate = anchor + datetime.timedelta(days=(cycle_num + 1) * 14)
        return candidate

    @staticmethod
    def _compute_pay_date(payroll_end, pay_weekday_django):
        """Return the next occurrence of pay_weekday_django after payroll_end."""
        # Both use the same scale: 0=Mon … 6=Sun
        days_ahead = (pay_weekday_django - payroll_end.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7          # Never pay on payroll_end itself; always at least 1 day ahead
        return payroll_end + datetime.timedelta(days=days_ahead)

    # ── context ───────────────────────────────────────────────────────────────

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cfg = GlobalSettings.get()
        anchor = cfg.schedule_cycle_start
        # Django 0=Mon…6=Sun  →  JS Date.getDay() 0=Sun…6=Sat
        week_start_day_js = (cfg.week_start_day + 1) % 7
        next_start = self._next_valid_start(anchor)
        ctx.update({
            "anchor_date": anchor.isoformat() if anchor else "",
            "week_start_day_js": week_start_day_js,
            "next_valid_start": next_start.isoformat() if next_start else "",
            "has_anchor": bool(anchor),
            "offset_days": cfg.payroll_cycle_offset_days,
        })
        return ctx

    # ── save ──────────────────────────────────────────────────────────────────

    def form_valid(self, form):
        cfg = GlobalSettings.get()
        schedule_start = form.cleaned_data["schedule_start"]

        # If a cycle already exists for this period, navigate to it — never duplicate.
        existing = PayrollCycle.objects.filter(schedule_start=schedule_start).first()
        if existing:
            messages.info(
                self.request,
                f"A payroll cycle for {schedule_start} already exists."
            )
            return redirect(reverse("scheduling:cycle_detail", kwargs={"pk": existing.pk}))

        schedule_end   = schedule_start + datetime.timedelta(days=13)
        offset         = cfg.payroll_cycle_offset_days
        payroll_start  = schedule_start - datetime.timedelta(days=offset)
        payroll_end    = schedule_end   - datetime.timedelta(days=offset)
        pay_date       = self._compute_pay_date(payroll_end, cfg.pay_weekday)

        # If another cycle is currently open, create this one as Pending so
        # users can build the schedule in advance without closing the open cycle.
        has_open = PayrollCycle.objects.filter(status=PayrollCycle.Status.OPEN).exists()
        new_status = PayrollCycle.Status.PENDING if has_open else PayrollCycle.Status.OPEN

        cycle = PayrollCycle.objects.create(
            schedule_start=schedule_start,
            schedule_end=schedule_end,
            payroll_start=payroll_start,
            payroll_end=payroll_end,
            pay_date=pay_date,
            status=new_status,
        )

        groups = Group.objects.filter(
            employees__status=Employee.Status.ACTIVE
        ).distinct().order_by("name")
        for group in groups:
            sched = Schedule.objects.create(cycle=cycle, group=group)
            Week.objects.create(schedule=sched, week_number=1, start_date=schedule_start)
            Week.objects.create(schedule=sched, week_number=2,
                                start_date=schedule_start + datetime.timedelta(days=7))

        if new_status == PayrollCycle.Status.PENDING:
            messages.success(
                self.request,
                f"Payroll cycle created as Pending: {cycle}. "
                f"You can build the schedule now and activate it when the current cycle closes."
            )
        else:
            messages.success(self.request, f"Payroll cycle opened: {cycle}")
        return redirect(reverse("scheduling:cycle_detail", kwargs={"pk": cycle.pk}))


# ── Cycle detail ──────────────────────────────────────────────────────────────

class CycleDetailView(LoginRequiredMixin, DetailView):
    model = PayrollCycle
    template_name = "scheduling/cycle_detail.html"
    context_object_name = "cycle"

    def get_queryset(self):
        return PayrollCycle.objects.prefetch_related(
            "schedules__group", "schedules__weeks"
        )


# ── Activate pending cycle ────────────────────────────────────────────────────

class CycleActivateView(LoginRequiredMixin, View):
    """Promote a Pending cycle to Open.  Guards against activating while another cycle is Open."""

    def post(self, request, pk):
        cycle = get_object_or_404(PayrollCycle, pk=pk)

        if not cycle.is_pending:
            messages.error(request, "Only a Pending cycle can be activated.")
            return redirect(reverse("scheduling:cycle_detail", kwargs={"pk": pk}))

        open_cycles = PayrollCycle.objects.filter(status=PayrollCycle.Status.OPEN)
        if open_cycles.exists():
            existing = open_cycles.first()
            messages.error(
                request,
                f"Cannot activate: there is already an open cycle "
                f"({existing.schedule_start} – {existing.schedule_end}). "
                f"Close it first."
            )
            return redirect(reverse("scheduling:cycle_detail", kwargs={"pk": pk}))

        cycle.status = PayrollCycle.Status.OPEN
        cycle.save()
        messages.success(request, f"Payroll cycle activated: {cycle}")
        return redirect(reverse("scheduling:cycle_detail", kwargs={"pk": pk}))


# ── Schedule builder ──────────────────────────────────────────────────────────

class ScheduleBuilderView(LoginRequiredMixin, View):
    template_name = "scheduling/builder.html"

    def get(self, request, schedule_pk):
        from django.shortcuts import render
        schedule = get_object_or_404(
            Schedule.objects.select_related("cycle", "group"),
            pk=schedule_pk,
        )
        week_num = int(request.GET.get("week", 1))
        week = get_object_or_404(Week, schedule=schedule, week_number=week_num)
        other_week_num = 2 if week_num == 1 else 1

        settings = GlobalSettings.get()
        lunch_min = settings.default_lunch_duration_minutes

        # All 7 dates in this week
        dates = [week.start_date + datetime.timedelta(days=i) for i in range(7)]

        # Existing Day objects for this week (keyed by date)
        days_by_date = {d.date: d for d in week.days.prefetch_related("shifts__employee")}

        # All shifts in this week keyed by (employee_pk, date)
        shift_map = {}
        for day_obj in days_by_date.values():
            for shift in day_obj.shifts.all():
                shift_map[(shift.employee_id, day_obj.date)] = shift

        employees = (
            Employee.objects.filter(group=schedule.group, status=Employee.Status.ACTIVE)
            .order_by("last_name", "first_name")
        )

        # Build a set of (employee_id, date) pairs unavailable within this week.
        unavail_records = Unavailability.objects.filter(
            employee__group=schedule.group,
            start_date__lte=dates[-1],
            end_date__gte=dates[0],
        ).values_list("employee_id", "start_date", "end_date")

        unavailable_set = set()
        for emp_id, u_start, u_end in unavail_records:
            for d in dates:
                if u_start <= d <= u_end:
                    unavailable_set.add((emp_id, d))

        employee_rows = []
        for emp in employees:
            weekly_hours = Decimal("0")
            day_cells = []
            for date in dates:
                shift = shift_map.get((emp.pk, date))
                if shift:
                    weekly_hours += shift.gross_hours(lunch_min)
                day_cells.append({
                    "date": date,
                    "day_obj": days_by_date.get(date),
                    "shift": shift,
                    "is_unavailable": not shift and (emp.pk, date) in unavailable_set,
                })
            employee_rows.append({"employee": emp, "total_hours": weekly_hours, "days": day_cells})

        return render(request, self.template_name, {
            "schedule": schedule,
            "week": week,
            "week_num": week_num,
            "other_week_num": other_week_num,
            "dates": dates,
            "employee_rows": employee_rows,
            "shift_create_url": reverse("scheduling:shift_create"),
        })


# ── Shift create (AJAX) ───────────────────────────────────────────────────────

class ShiftCreateView(LoginRequiredMixin, View):
    def post(self, request):
        week_pk  = request.POST.get("week_pk")
        date_str = request.POST.get("date")
        week     = get_object_or_404(Week, pk=week_pk)
        try:
            date = datetime.date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return JsonResponse({"ok": False, "error": "Invalid date."}, status=400)

        form = ShiftForm(request.POST, group=week.schedule.group, date=date)
        if not form.is_valid():
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)

        # Check duplicate
        emp = form.cleaned_data["employee"]
        if ScheduledShift.objects.filter(employee=emp, day__date=date).exists():
            return JsonResponse(
                {"ok": False, "error": f"{emp.full_name} already has a shift on {date}."},
                status=400,
            )

        day, _ = Day.objects.get_or_create(week=week, date=date)
        shift = ScheduledShift.objects.create(
            day=day,
            employee=emp,
            start_time=form.cleaned_data["start_time"],
            end_time=form.cleaned_data["end_time"],
            include_lunch=form.cleaned_data.get("include_lunch", False),
        )
        settings = GlobalSettings.get()
        hours = float(shift.gross_hours(settings.default_lunch_duration_minutes))
        return JsonResponse({
            "ok": True,
            "shift_id": shift.pk,
            "employee_id": emp.pk,
            "employee_name": emp.full_name,
            "start_time": shift.start_time.strftime("%H:%M"),
            "end_time": shift.end_time.strftime("%H:%M"),
            "include_lunch": shift.include_lunch,
            "hours": round(hours, 2),
            "delete_url": reverse("scheduling:shift_delete", kwargs={"pk": shift.pk}),
            "edit_url":   reverse("scheduling:shift_update",  kwargs={"pk": shift.pk}),
        })


# ── Shift update (AJAX) ───────────────────────────────────────────────────────

class ShiftUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        shift = get_object_or_404(ScheduledShift, pk=pk)
        cfg   = GlobalSettings.get()

        # Parse times
        try:
            start_time = datetime.time.fromisoformat(request.POST.get("start_time", ""))
            end_time   = datetime.time.fromisoformat(request.POST.get("end_time", ""))
        except ValueError:
            return JsonResponse({"ok": False, "error": "Invalid time format."}, status=400)

        if end_time <= start_time:
            return JsonResponse(
                {"ok": False, "error": "End time must be after start time."}, status=400
            )

        old_hours = float(shift.gross_hours(cfg.default_lunch_duration_minutes))

        shift.start_time    = start_time
        shift.end_time      = end_time
        shift.include_lunch = "include_lunch" in request.POST
        shift.save()

        new_hours = float(shift.gross_hours(cfg.default_lunch_duration_minutes))

        return JsonResponse({
            "ok":           True,
            "shift_id":     shift.pk,
            "employee_id":  shift.employee_id,
            "start_time":   shift.start_time.strftime("%H:%M"),
            "end_time":     shift.end_time.strftime("%H:%M"),
            "include_lunch": shift.include_lunch,
            "old_hours":    round(old_hours, 2),
            "new_hours":    round(new_hours, 2),
            "delete_url":   reverse("scheduling:shift_delete", kwargs={"pk": shift.pk}),
            "edit_url":     reverse("scheduling:shift_update", kwargs={"pk": shift.pk}),
        })


# ── Shift delete (AJAX) ───────────────────────────────────────────────────────

class ShiftDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        shift = get_object_or_404(ScheduledShift, pk=pk)
        employee_id = shift.employee_id
        date = shift.day.date
        settings = GlobalSettings.get()
        hours = float(shift.gross_hours(settings.default_lunch_duration_minutes))
        shift.delete()
        return JsonResponse({"ok": True, "employee_id": employee_id,
                             "date": date.isoformat(), "hours": hours})


# ── Ad-hoc shift (dashboard) ──────────────────────────────────────────────────

class AdHocShiftCreateView(FormView):
    form_class = AdHocShiftForm
    success_url = reverse_lazy("core:home")

    def form_valid(self, form):
        try:
            shift = form.save()
        except Exception as exc:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": True,
                                 "message": f"Ad-hoc shift added for {shift.employee.full_name}."})
        messages.success(self.request, f"Ad-hoc shift added for {shift.employee.full_name}.")
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False,
                                 "errors": {f: list(e) for f, e in form.errors.items()}},
                                status=400)
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)
