from django.urls import path
from . import views

app_name = "employees"

urlpatterns = [
    # Employee CRUD
    path("", views.EmployeeListView.as_view(), name="list"),
    path("add/", views.EmployeeCreateView.as_view(), name="create"),
    path("<int:pk>/", views.EmployeeDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.EmployeeUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.EmployeeDeleteView.as_view(), name="delete"),

    # Unavailability (AJAX)
    path("<int:employee_pk>/unavailability/add/", views.UnavailabilityCreateView.as_view(), name="unavailability_create"),
    path("unavailability/<int:pk>/delete/", views.UnavailabilityDeleteView.as_view(), name="unavailability_delete"),

    # Groups
    path("groups/", views.GroupListView.as_view(), name="groups"),
    path("groups/add/", views.GroupCreateView.as_view(), name="group_create"),
    path("groups/<int:pk>/edit/", views.GroupUpdateView.as_view(), name="group_update"),
    path("groups/<int:pk>/delete/", views.GroupDeleteView.as_view(), name="group_delete"),

    # Deduction Exemptions (AJAX)
    path("<int:employee_pk>/exemptions/add/", views.ExemptionCreateView.as_view(), name="exemption_create"),
    path("exemptions/<int:pk>/delete/", views.ExemptionDeleteView.as_view(), name="exemption_delete"),
]
