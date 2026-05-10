from django.contrib import admin

from .models import Deduction, GlobalSettings


@admin.register(Deduction)
class DeductionAdmin(admin.ModelAdmin):
    list_display = ("name", "deduction_type", "display_amount", "is_active")
    list_filter = ("deduction_type", "is_active")
    search_fields = ("name",)
    list_editable = ("is_active",)


@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    """
    Singleton admin — prevents adding a second record and hides the delete action.
    """

    fieldsets = (
        ("Pay Multipliers", {
            "fields": (
                "overtime_rate_multiplier",
                "overtime_threshold_hours",
                "holiday_rate_multiplier",
            ),
        }),
        ("Scheduling Defaults", {
            "fields": ("default_lunch_duration_minutes", "week_start_day"),
        }),
        ("Payroll Close Day", {
            "fields": ("payroll_close_weekday", "payroll_close_week"),
            "description": (
                "Defines which day the 'Close Payroll' button appears on the dashboard. "
                "E.g. Thursday of Week 2."
            ),
        }),
        ("Cycle Anchors", {
            "fields": ("schedule_cycle_start", "payroll_cycle_offset_days"),
        }),
    )

    def has_add_permission(self, request):
        return not GlobalSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
