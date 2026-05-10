from django.contrib import admin

from .models import PayrollRun, Payslip, PayslipLine


class PayslipLineInline(admin.TabularInline):
    model = PayslipLine
    extra = 0
    fields = ("date", "line_type", "hours", "rate", "amount", "description")
    readonly_fields = ("date", "line_type", "hours", "rate", "amount", "description")
    can_delete = False


class PayslipInline(admin.TabularInline):
    model = Payslip
    extra = 0
    fields = ("employee", "pay_rate_snapshot", "regular_hours", "overtime_hours", "gross_pay", "deductions", "net_pay")
    readonly_fields = fields
    can_delete = False
    show_change_link = True


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = ("cycle", "run_date")
    readonly_fields = ("run_date",)
    inlines = [PayslipInline]


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ("employee", "run", "regular_hours", "overtime_hours", "gross_pay", "deductions", "net_pay")
    list_filter = ("run",)
    search_fields = ("employee__last_name", "employee__first_name")
    inlines = [PayslipLineInline]
    readonly_fields = ("run", "employee", "pay_rate_snapshot")
