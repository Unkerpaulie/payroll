"""
Custom User model for the payroll system.

Extending AbstractUser from the start gives us full control over the user
model without requiring a data migration later. Currently only an Admin user
type is in use; additional roles (Manager, Employee) will be added as future
iterations define their permissions and access patterns.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Project-wide user. Inherits all standard Django auth fields (username,
    email, first_name, last_name, is_staff, is_active, etc.) and adds a
    ``user_type`` field for future role-based access control.
    """

    class UserType(models.TextChoices):
        ADMIN = "admin", "Admin"
        # Future roles — uncomment as they are implemented:
        # MANAGER = "manager", "Manager"
        # EMPLOYEE = "employee", "Employee"

    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.ADMIN,
    )

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_user_type_display()})"

    @property
    def is_admin(self):
        """Convenience check — expand when additional roles are introduced."""
        return self.user_type == self.UserType.ADMIN
