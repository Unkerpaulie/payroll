"""
Core models. Holds project-wide concerns that don't belong to a specific
domain app. The GlobalSettings model (overtime/holiday rates, deductions,
default lunch duration, week start day, schedule and payroll cycle anchors)
will be added in Phase 2.
"""

from django.db import models  # noqa: F401
