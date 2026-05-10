from django.contrib import messages
from django.http import JsonResponse
from django.views.generic.edit import FormView
from django.urls import reverse_lazy

from .forms import AdHocShiftForm


class AdHocShiftCreateView(FormView):
    """
    POST-only view that creates an ad-hoc (unscheduled) shift and returns a
    JSON response so the dashboard modal can close without a full page reload.
    On success the dashboard JS reloads the page to reflect the new shift in
    the time-keeping quick actions.
    """

    form_class = AdHocShiftForm
    # Fallback for non-JS submissions.
    success_url = reverse_lazy("core:home")

    def form_valid(self, form):
        try:
            shift = form.save()
        except Exception as exc:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)

        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "ok": True,
                "message": (
                    f"Ad-hoc shift added for {shift.employee.full_name} on {shift.date}."
                ),
            })
        messages.success(
            self.request,
            f"Ad-hoc shift added for {shift.employee.full_name} on {shift.date}.",
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            errors = {
                field: list(errs) for field, errs in form.errors.items()
            }
            return JsonResponse({"ok": False, "errors": errors}, status=400)
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)
