from django.contrib import admin

from .models import ActualShift


@admin.register(ActualShift)
class ActualShiftAdmin(admin.ModelAdmin):
    list_display = (
        "scheduled_shift",
        "clock_in",
        "lunch_start",
        "lunch_end",
        "clock_out",
        "paid_hours",
    )
    search_fields = (
        "scheduled_shift__employee__last_name",
        "scheduled_shift__employee__first_name",
    )
    readonly_fields = ("paid_hours",)

    @admin.display(description="Paid Hours")
    def paid_hours(self, obj):
        hours = obj.paid_hours()
        return f"{hours:.2f}" if hours is not None else "—"
