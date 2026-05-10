from django.contrib import admin

from .models import Employee, Group, Unavailability


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


class UnavailabilityInline(admin.TabularInline):
    model = Unavailability
    extra = 1
    fields = ("start_date", "end_date", "reason")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "group", "pay_rate", "status", "hire_date")
    list_filter = ("status", "group")
    search_fields = ("last_name", "first_name", "email")
    inlines = [UnavailabilityInline]
    fieldsets = (
        ("Personal", {"fields": ("first_name", "last_name", "email", "phone")}),
        ("Employment", {"fields": ("group", "pay_rate", "status", "hire_date", "notes")}),
    )


@admin.register(Unavailability)
class UnavailabilityAdmin(admin.ModelAdmin):
    list_display = ("employee", "start_date", "end_date", "reason")
    list_filter = ("employee",)
    search_fields = ("employee__last_name", "employee__first_name")
