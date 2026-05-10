from django.urls import path

from .views import (
    AdHocShiftCreateView,
    CycleListView, CycleCreateView, CycleDetailView,
    ScheduleBuilderView,
    ShiftCreateView, ShiftDeleteView,
)

app_name = "scheduling"

urlpatterns = [
    # Cycles
    path("", CycleListView.as_view(), name="cycle_list"),
    path("new/", CycleCreateView.as_view(), name="cycle_create"),
    path("<int:pk>/", CycleDetailView.as_view(), name="cycle_detail"),

    # Schedule builder
    path("schedule/<int:schedule_pk>/", ScheduleBuilderView.as_view(), name="builder"),

    # Shifts (AJAX)
    path("shift/add/", ShiftCreateView.as_view(), name="shift_create"),
    path("shift/<int:pk>/delete/", ShiftDeleteView.as_view(), name="shift_delete"),

    # Ad-hoc (dashboard)
    path("shifts/adhoc/", AdHocShiftCreateView.as_view(), name="adhoc_shift_create"),
]
