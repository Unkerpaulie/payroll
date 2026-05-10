from django.views.generic import TemplateView


class HomeView(TemplateView):
    """Landing dashboard. Placeholder until Phase 3 wires real widgets."""

    template_name = "pages/home.html"
