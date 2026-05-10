from django.contrib import admin

from .models import GlobalSettings


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
        ("Deductions", {
            "fields": ("deduction_percentage",),
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
