from django.urls import path

from .views import ClockActionView, TimeRecordingView

app_name = "attendance"

urlpatterns = [
    path("", TimeRecordingView.as_view(), name="time_recording"),
    path("clock/", ClockActionView.as_view(), name="clock_action"),
]
