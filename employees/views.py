"""
Views for the employees app.
"""

import json
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    ListView, CreateView, DetailView, UpdateView, DeleteView, View,
)

from .models import Employee, Group, Unavailability
from .forms import EmployeeForm, GroupForm, UnavailabilityForm


# ── Employee ──────────────────────────────────────────────────────────────────

class EmployeeListView(LoginRequiredMixin, ListView):
    model = Employee
    template_name = "employees/list.html"
    context_object_name = "employees"

    def get_queryset(self):
        return Employee.objects.select_related("group").order_by("last_name", "first_name")


class EmployeeCreateView(LoginRequiredMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "employees/form.html"

    def get_success_url(self):
        return reverse("employees:detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = "Add Employee"
        ctx["cancel_url"] = reverse_lazy("employees:list")
        return ctx


class EmployeeDetailView(LoginRequiredMixin, DetailView):
    model = Employee
    template_name = "employees/detail.html"
    context_object_name = "employee"

    def get_queryset(self):
        return Employee.objects.select_related("group").prefetch_related("unavailabilities")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["unavailability_form"] = UnavailabilityForm()
        return ctx


class EmployeeUpdateView(LoginRequiredMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "employees/form.html"

    def get_success_url(self):
        return reverse("employees:detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = f"Edit – {self.object.full_name}"
        ctx["cancel_url"] = reverse("employees:detail", kwargs={"pk": self.object.pk})
        return ctx


class EmployeeDeleteView(LoginRequiredMixin, DeleteView):
    model = Employee
    success_url = reverse_lazy("employees:list")

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except ProtectedError:
            emp = self.get_object()
            return redirect(reverse("employees:detail", kwargs={"pk": emp.pk}))


# ── Unavailability (AJAX) ─────────────────────────────────────────────────────

class UnavailabilityCreateView(LoginRequiredMixin, View):
    def post(self, request, employee_pk):
        employee = get_object_or_404(Employee, pk=employee_pk)
        form = UnavailabilityForm(request.POST)
        if form.is_valid():
            unav = form.save(commit=False)
            unav.employee = employee
            unav.save()
            return JsonResponse({
                "ok": True,
                "id": unav.pk,
                "start_date": unav.start_date.strftime("%b %d, %Y"),
                "end_date": unav.end_date.strftime("%b %d, %Y"),
                "reason": unav.reason,
            })
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)


class UnavailabilityDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        unav = get_object_or_404(Unavailability, pk=pk)
        unav.delete()
        return JsonResponse({"ok": True})


# ── Groups ────────────────────────────────────────────────────────────────────

class GroupListView(LoginRequiredMixin, ListView):
    model = Group
    template_name = "employees/groups.html"
    context_object_name = "groups"

    def get_queryset(self):
        return Group.objects.prefetch_related("employees")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["group_form"] = GroupForm()
        return ctx


class GroupCreateView(LoginRequiredMixin, View):
    def post(self, request):
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save()
            return JsonResponse({"ok": True, "id": group.pk, "name": group.name, "description": group.description})
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)


class GroupUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        group = get_object_or_404(Group, pk=pk)
        form = GroupForm(request.POST, instance=group)
        if form.is_valid():
            group = form.save()
            return JsonResponse({"ok": True, "id": group.pk, "name": group.name, "description": group.description})
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)


class GroupDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        group = get_object_or_404(Group, pk=pk)
        try:
            group.delete()
            return JsonResponse({"ok": True})
        except ProtectedError:
            return JsonResponse({"ok": False, "error": "This group has employees assigned and cannot be deleted."}, status=400)
