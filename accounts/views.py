from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy


class LoginView(auth_views.LoginView):
    """Login page using the SB Admin 2 auth layout."""

    template_name = "accounts/login.html"
    redirect_authenticated_user = True
    next_page = reverse_lazy("core:home")


class LogoutView(auth_views.LogoutView):
    """POST-only logout; redirects to login page."""

    next_page = reverse_lazy("accounts:login")
