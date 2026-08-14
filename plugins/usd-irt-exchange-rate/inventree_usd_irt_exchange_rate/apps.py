"""Django application configuration for the exchange-rate plugin."""

from django.apps import AppConfig


class USDIRTExchangeRateConfig(AppConfig):
    """Register the plugin models and price snapshot signals."""

    default_auto_field = "django.db.models.AutoField"
    name = "inventree_usd_irt_exchange_rate"
    verbose_name = "USD / IRT Exchange Rate"

    def ready(self):
        """Connect price snapshot receivers after Django loads all models."""
        from . import signals  # noqa: F401, PLC0415
