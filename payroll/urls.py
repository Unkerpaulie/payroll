"""
Project URL configuration. Per rules.md §13, root URLs are owned by the core
app; domain apps are mounted under their own prefixes as they are introduced.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls", namespace="core")),
]
