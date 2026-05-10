from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Extends Django's built-in UserAdmin with the custom user_type field."""

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Role", {"fields": ("user_type",)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Role", {"fields": ("user_type",)}),
    )
    list_display = ("username", "email", "first_name", "last_name", "user_type", "is_staff")
    list_filter = ("user_type", "is_staff", "is_active")
