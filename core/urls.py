from django.urls import path

from .views import (
    HomeView, KpiView, SettingsView,
    DeductionListView, DeductionCreateView, DeductionUpdateView, DeductionDeleteView,
)

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("kpi/", KpiView.as_view(), name="kpi"),
    path("settings/", SettingsView.as_view(), name="settings"),

    # Deductions
    path("settings/deductions/", DeductionListView.as_view(), name="deductions"),
    path("settings/deductions/add/", DeductionCreateView.as_view(), name="deduction_create"),
    path("settings/deductions/<int:pk>/edit/", DeductionUpdateView.as_view(), name="deduction_update"),
    path("settings/deductions/<int:pk>/delete/", DeductionDeleteView.as_view(), name="deduction_delete"),
]
