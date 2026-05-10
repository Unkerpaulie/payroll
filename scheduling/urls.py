from django.urls import path

from .views import AdHocShiftCreateView

app_name = "scheduling"

urlpatterns = [
    path("shifts/adhoc/", AdHocShiftCreateView.as_view(), name="adhoc_shift_create"),
]
