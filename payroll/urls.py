"""
Project URL configuration. Per rules.md §13, root URLs are owned by the core
app; domain apps are mounted under their own prefixes as they are introduced.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("scheduling/", include("scheduling.urls", namespace="scheduling")),
    path("employees/", include("employees.urls", namespace="employees")),
    path("", include("core.urls", namespace="core")),
]
