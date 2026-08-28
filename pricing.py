"""Compatibility pricing facade retained for the existing API contract."""
from __future__ import annotations


class PricingCalculator:
    """Placeholder-compatible facade; pricing policy remains configuration-owned."""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
