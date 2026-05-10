from django.urls import path

from .views import HomeView, KpiView, SettingsView

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("kpi/", KpiView.as_view(), name="kpi"),
    path("settings/", SettingsView.as_view(), name="settings"),
]
