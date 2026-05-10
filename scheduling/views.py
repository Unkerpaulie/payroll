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
from employees.models import Employee, Group
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

    def form_valid(self, form):
        settings = GlobalSettings.get()
        schedule_start = form.cleaned_data["schedule_start"]
        schedule_end   = schedule_start + datetime.timedelta(days=13)
        offset         = settings.payroll_cycle_offset_days
        payroll_start  = schedule_start - datetime.timedelta(days=offset)
        payroll_end    = schedule_end   - datetime.timedelta(days=offset)
        pay_date       = form.cleaned_data["pay_date"]

        cycle = PayrollCycle.objects.create(
            schedule_start=schedule_start,
            schedule_end=schedule_end,
            payroll_start=payroll_start,
            payroll_end=payroll_end,
            pay_date=pay_date,
            status=PayrollCycle.Status.OPEN,
        )

        # Create a Schedule + two Weeks for every group that has active employees.
        groups = Group.objects.filter(
            employees__status=Employee.Status.ACTIVE
        ).distinct().order_by("name")
        for group in groups:
            sched = Schedule.objects.create(cycle=cycle, group=group)
            Week.objects.create(schedule=sched, week_number=1, start_date=schedule_start)
            Week.objects.create(schedule=sched, week_number=2,
                                start_date=schedule_start + datetime.timedelta(days=7))

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

        employee_rows = []
        for emp in employees:
            weekly_hours = Decimal("0")
            day_cells = []
            for date in dates:
                shift = shift_map.get((emp.pk, date))
                if shift:
                    weekly_hours += shift.gross_hours(lunch_min)
                day_cells.append({"date": date, "day_obj": days_by_date.get(date), "shift": shift})
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

        form = ShiftForm(request.POST, group=week.schedule.group)
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
