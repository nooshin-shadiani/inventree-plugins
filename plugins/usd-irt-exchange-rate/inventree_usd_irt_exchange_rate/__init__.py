"""InvenTree USD to Iranian toman exchange rate plugin."""

from moneyed import CURRENCIES, add_currency

PLUGIN_VERSION = "1.2.1"

if "IRT" not in CURRENCIES:
    add_currency(code="IRT", numeric=None, name="Iranian toman")
