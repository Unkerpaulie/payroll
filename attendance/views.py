"""
Attendance views.

TimeRecordingView  — today's shift board (GET).
ClockActionView    — single AJAX endpoint for clock-in / lunch / clock-out (POST).
"""

import datetime

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.generic import View

from attendance.models import ActualShift
from scheduling.forms import AdHocShiftForm
from scheduling.models import PayrollCycle, ScheduledShift


# ── State helper ──────────────────────────────────────────────────────────────

def _shift_state(shift, actual):
    """
    Return a string token describing where in the clock sequence a shift is.

    Tokens
    ------
    not_started  — no ActualShift yet, or clock_in is blank
    clocked_in   — clocked in; lunch not yet started (or shift has no lunch)
    on_lunch     — lunch_start recorded, lunch_end not yet recorded
    post_lunch   — both lunch timestamps recorded; not yet clocked out
    completed    — clock_out recorded
    """
    if actual is None or not actual.clock_in:
        return "not_started"
    if actual.clock_out:
        return "completed"
    if actual.lunch_start and not actual.lunch_end:
        return "on_lunch"
    if actual.lunch_start and actual.lunch_end:
        return "post_lunch"
    return "clocked_in"


# ── Time Recording board ──────────────────────────────────────────────────────

class TimeRecordingView(LoginRequiredMixin, View):
    template_name = "attendance/time_recording.html"

    def get(self, request):
        today = datetime.date.today()

        try:
            cycle = PayrollCycle.objects.get(status=PayrollCycle.Status.OPEN)
        except (PayrollCycle.DoesNotExist, PayrollCycle.MultipleObjectsReturned):
            cycle = None

        rows = []
        if cycle:
            shifts = (
                ScheduledShift.objects
                .filter(day__date=today)
                .select_related("employee", "employee__group", "day")
                .order_by("start_time", "employee__last_name", "employee__first_name")
            )
            for shift in shifts:
                try:
                    actual = shift.actual_shift
                except ActualShift.DoesNotExist:
                    actual = None
                rows.append({
                    "shift": shift,
                    "actual": actual,
                    "state": _shift_state(shift, actual),
                })

        return render(request, self.template_name, {
            "today": today,
            "cycle": cycle,
            "rows": rows,
            "adhoc_form": AdHocShiftForm(),
        })


# ── Clock action (AJAX POST) ──────────────────────────────────────────────────

class ClockActionView(LoginRequiredMixin, View):
    """
    Accept a single clock action and advance the ActualShift state machine.

    POST body: scheduled_shift_id=<pk>  action=<clock_in|lunch_start|lunch_end|clock_out>
    Returns JSON: { ok, shift_id, state, action, time } on success.
    """

    VALID_ACTIONS = {"clock_in", "lunch_start", "lunch_end", "clock_out"}

    def post(self, request):
        action = request.POST.get("action", "")
        if action not in self.VALID_ACTIONS:
            return JsonResponse({"ok": False, "error": "Unknown action."}, status=400)

        shift = get_object_or_404(ScheduledShift, pk=request.POST.get("scheduled_shift_id"))
        actual, _ = ActualShift.objects.get_or_create(scheduled_shift=shift)

        # Round to the nearest minute — no seconds in time recording.
        now = datetime.datetime.now().time().replace(second=0, microsecond=0)

        error = self._apply(action, shift, actual, now)
        if error:
            return JsonResponse({"ok": False, "error": error}, status=400)

        actual.save()
        return JsonResponse({
            "ok":      True,
            "shift_id": shift.pk,
            "state":   _shift_state(shift, actual),
            "action":  action,
            "time":    now.strftime("%H:%M"),
        })

    # ── action dispatcher ─────────────────────────────────────────────────────

    @staticmethod
    def _apply(action, shift, actual, now):
        """Mutate actual for the given action. Return an error string or None."""
        if action == "clock_in":
            if actual.clock_in:
                return "Already clocked in."
            actual.clock_in = now

        elif action == "lunch_start":
            if not actual.clock_in:
                return "Must clock in before starting lunch."
            if not shift.include_lunch:
                return "This shift does not include a lunch break."
            if actual.lunch_start:
                return "Lunch already started."
            actual.lunch_start = now

        elif action == "lunch_end":
            if not actual.lunch_start:
                return "Lunch has not been started."
            if actual.lunch_end:
                return "Lunch already ended."
            actual.lunch_end = now

        elif action == "clock_out":
            if not actual.clock_in:
                return "Must clock in first."
            if actual.clock_out:
                return "Already clocked out."
            actual.clock_out = now

        return None
