"""InvenTree USD to Iranian toman exchange rate plugin."""

from moneyed import CURRENCIES, add_currency

PLUGIN_VERSION = "1.3.0"

if "IRT" not in CURRENCIES:
    add_currency(code="IRT", numeric=None, name="Iranian toman")
