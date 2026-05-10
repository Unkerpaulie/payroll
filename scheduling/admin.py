from django.contrib import admin

from .models import Day, PayrollCycle, Schedule, ScheduledShift, Week


class ScheduleInline(admin.TabularInline):
    model = Schedule
    extra = 0
    fields = ("group", "notes")
    show_change_link = True


@admin.register(PayrollCycle)
class PayrollCycleAdmin(admin.ModelAdmin):
    list_display = ("__str__", "schedule_start", "schedule_end", "pay_date", "status")
    list_filter = ("status",)
    inlines = [ScheduleInline]


class WeekInline(admin.TabularInline):
    model = Week
    extra = 0
    fields = ("week_number", "start_date")
    show_change_link = True


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("cycle", "group")
    list_filter = ("group", "cycle__status")
    inlines = [WeekInline]


class DayInline(admin.TabularInline):
    model = Day
    extra = 0
    fields = ("date", "is_holiday", "holiday_name")
    show_change_link = True


@admin.register(Week)
class WeekAdmin(admin.ModelAdmin):
    list_display = ("schedule", "week_number", "start_date", "end_date")
    inlines = [DayInline]


class ScheduledShiftInline(admin.TabularInline):
    model = ScheduledShift
    extra = 0
    fields = ("employee", "start_time", "end_time", "include_lunch", "is_adhoc")


@admin.register(Day)
class DayAdmin(admin.ModelAdmin):
    list_display = ("date", "week", "is_holiday", "holiday_name")
    list_filter = ("is_holiday", "week__schedule__cycle", "week__schedule__group")
    date_hierarchy = "date"
    inlines = [ScheduledShiftInline]


@admin.register(ScheduledShift)
class ScheduledShiftAdmin(admin.ModelAdmin):
    list_display = ("employee", "get_date", "start_time", "end_time", "include_lunch", "is_adhoc")
    list_filter = ("day__week__schedule__cycle", "day__week__schedule__group")
    search_fields = ("employee__last_name", "employee__first_name")

    @admin.display(description="Date", ordering="day__date")
    def get_date(self, obj):
        return obj.day.date
