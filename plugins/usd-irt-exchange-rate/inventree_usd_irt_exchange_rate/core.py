"""USD to Iranian toman currency exchange plugin for InvenTree."""

import decimal
import logging
from functools import wraps
from typing import ClassVar

import requests
from common.settings import get_global_setting
from django.core.exceptions import ValidationError
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _
from lxml import etree, html
from part.models import Part
from plugin import InvenTreePlugin
from plugin.mixins import (
    AppMixin,
    CurrencyExchangeMixin,
    ScheduleMixin,
    SettingsMixin,
    UrlsMixin,
    UserInterfaceMixin,
)
from users.permissions import check_user_permission

from . import PLUGIN_VERSION

logger = logging.getLogger("inventree")


def install_dynamic_part_pricing_currency_choices():
    """Keep InvenTree's exceptional part-override choices current."""
    from common.currency import currency_code_mappings  # noqa: PLC0415
    from part.serializers import PartPricingSerializer  # noqa: PLC0415

    marker = "_usd_irt_dynamic_currency_choices"
    if getattr(PartPricingSerializer, marker, False):
        return

    original_get_fields = PartPricingSerializer.get_fields

    @wraps(original_get_fields)
    def get_fields(serializer):
        """Refresh override currencies when the serializer is instantiated."""
        fields = original_get_fields(serializer)
        choices = currency_code_mappings()

        for field_name in ("override_min_currency", "override_max_currency"):
            fields[field_name].choices = choices

        return fields

    PartPricingSerializer.get_fields = get_fields
    setattr(PartPricingSerializer, marker, True)


def validate_positive_finite_rate(value):
    """Validate a rate which can safely be used for currency conversion."""
    try:
        rate = decimal.Decimal(str(value))
    except (decimal.InvalidOperation, TypeError, ValueError):
        rate = decimal.Decimal(0)

    if not rate.is_finite() or rate <= 0:
        raise ValidationError(
            _("Enter a positive, finite USD to IRT rate"), code="invalid"
        )


class IranianCurrencyExchange(  # pyrefly: ignore [inconsistent-inheritance]
    AppMixin,
    ScheduleMixin,
    CurrencyExchangeMixin,
    SettingsMixin,
    UrlsMixin,
    UserInterfaceMixin,
    InvenTreePlugin,
):
    """Provide a USD to IRT rate from manual configuration or TGJU."""

    NAME = "InvenTreeUSDIRTExchangeRate"
    SLUG = "inventree-usd-irt-exchange-rate"
    AUTHOR = "Nooshin Shadiani"
    TITLE = _("Iranian Currency Exchange")
    DESCRIPTION = _("Manual or TGJU-provided USD to IRT exchange rates")
    VERSION = PLUGIN_VERSION
    LICENSE = "MIT"
    MIN_VERSION = "1.6.0"
    MAX_VERSION = "1.6.99"
    WEBSITE = "https://github.com/nooshin-shadiani/inventree-plugins/tree/main/plugins/usd-irt-exchange-rate"

    TGJU_CURRENCY_URL = "https://www.tgju.org/currency"
    TGJU_PROFILE_URL = "https://www.tgju.org/profile/price_dollar_rl"
    REQUEST_TIMEOUT = 10
    REQUEST_HEADERS: ClassVar[dict[str, str]] = {
        "Accept": "text/html",
        "User-Agent": f"InvenTree USD IRT Exchange Rate/{PLUGIN_VERSION}",
    }
    TGJU_SOURCES = (
        (
            TGJU_CURRENCY_URL,
            (
                "string((//tr[@data-market-row='price_dollar_rl']/@data-price)[1])",
                "string((//*[@id='l-price_dollar_rl']//*[contains(concat(' ', normalize-space(@class), ' '), ' info-price ')])[1])",
            ),
        ),
        (
            TGJU_PROFILE_URL,
            (
                "string((//*[@data-target='profile-tour-current_rate']//*[@data-col='info.last_trade.PDrCotVal'])[1])",
            ),
        ),
    )

    SCHEDULED_TASKS: ClassVar[  # pyrefly: ignore [bad-override]
        dict[str, dict[str, str | int]]
    ] = {
        "refresh_usd_irt": {"func": "refresh_usd_irt", "schedule": "I", "minutes": 180}
    }

    SETTINGS: ClassVar[  # pyrefly: ignore [bad-override]
        dict[str, dict[str, object]]
    ] = {
        "API_ENABLED": {
            "name": _("Enable TGJU USD rate consumer"),
            "description": _(
                "Fetch the free-market USD to IRT rate from TGJU using XPath instead of using the manual rate"
            ),
            "validator": bool,
            "default": False,
        },
        "USD_IRT_RATE": {
            "name": _("Manual USD to IRT rate"),
            "description": _("Iranian tomans per one US dollar"),
            "units": _("IRT per USD"),
            "validator": [float, validate_positive_finite_rate],
        },
    }

    def __init__(self):
        """Initialize the plugin and align every part-price currency field."""
        super().__init__()
        install_dynamic_part_pricing_currency_choices()

    def setup_urls(self):
        """Expose read-only historical prices to the plugin UI."""
        from .views import PartPriceSnapshotView  # noqa: PLC0415

        return [
            path(
                "part/<int:part_id>/prices/",
                PartPriceSnapshotView.as_view(),
                name="part-prices",
            )
        ]

    def get_ui_panels(self, request, context, **kwargs):
        """Show current and saved USD/IRT prices on each part page."""
        if context.get("target_model") != "part" or not check_user_permission(
            request.user, Part, "view"
        ):
            return []

        try:
            part_id = int(context.get("target_id"))
        except (TypeError, ValueError):
            return []

        if not Part.objects.filter(pk=part_id).exists():
            return []

        return [
            {
                "key": "usd-irt-pricing",
                "title": _("USD / IRT Pricing"),
                "description": _(
                    "Current part pricing and immutable saved-price conversions"
                ),
                "icon": "ti:currency-dollar:outline",
                "source": self.plugin_static_file("dual_currency_pricing.js"),
                "context": {
                    "pricing_url": reverse("api-part-pricing", kwargs={"pk": part_id}),
                    "exchange_url": reverse("api-currency-exchange"),
                    "history_url": reverse(
                        f"plugin:{self.slug}:part-prices",
                        kwargs={"part_id": part_id},
                    ),
                },
            }
        ]

    _DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

    @classmethod
    def _parse_rate(cls, value) -> decimal.Decimal:
        """Parse and validate a positive exchange rate."""
        text = str(value).translate(cls._DIGIT_TRANSLATION)
        text = text.replace(",", "").replace("٬", "").replace("،", "").strip()
        rate = decimal.Decimal(text)

        if not rate.is_finite() or rate <= 0:
            raise ValueError("Exchange rate must be a positive finite number")

        return rate

    def _manual_rate(self) -> decimal.Decimal | None:
        """Return the configured manual rate, if valid."""
        try:
            return self._parse_rate(self.get_setting("USD_IRT_RATE"))
        except (decimal.InvalidOperation, TypeError, ValueError):
            pass

        try:
            legacy_irr_rate = self._parse_rate(self.get_setting("USD_IRR_RATE"))
            return legacy_irr_rate / decimal.Decimal(10)
        except (decimal.InvalidOperation, TypeError, ValueError):
            logger.warning("Manual USD to IRT exchange rate is not valid")
            return None

    @classmethod
    def _extract_tgju_rate(cls, content, xpaths) -> decimal.Decimal | None:
        """Extract the first valid IRR rate from TGJU HTML using XPath."""
        try:
            document = html.fromstring(content)
        except (etree.ParserError, TypeError, ValueError):
            return None

        for xpath in xpaths:
            try:
                return cls._parse_rate(document.xpath(xpath))
            except (decimal.InvalidOperation, TypeError, ValueError):
                continue

        return None

    def _tgju_rate(self) -> decimal.Decimal | None:
        """Fetch TGJU's IRR quote and convert it to Iranian tomans."""
        for url, xpaths in self.TGJU_SOURCES:
            try:
                response = requests.get(
                    url, headers=self.REQUEST_HEADERS, timeout=self.REQUEST_TIMEOUT
                )
                response.raise_for_status()
            except requests.RequestException:
                continue

            if rate := self._extract_tgju_rate(response.content, xpaths):
                return rate / decimal.Decimal(10)

        logger.warning("TGJU returned no valid USD to IRT exchange rate")
        return None

    def refresh_usd_irt(self):
        """Refresh the selected TGJU exchange rate on the plugin schedule."""
        if not self.get_setting("API_ENABLED"):
            return

        selected_plugin = get_global_setting(
            "CURRENCY_UPDATE_PLUGIN", create=False, cache=False
        )

        if selected_plugin != self.slug:
            return

        from InvenTree.tasks import update_exchange_rates  # noqa: PLC0415

        update_exchange_rates(force=True)

    def update_exchange_rates(self, base_currency: str, symbols: list[str]) -> dict:
        """Return USD-based rates for the supported USD and IRT scope."""
        base_currency = base_currency.upper()
        requested = {symbol.upper() for symbol in symbols}
        supported = {"USD", "IRT"}

        # django-money stores only six decimal places for exchange rates. Using IRT
        # as the base would round the reciprocal USD rate too aggressively.
        if base_currency != "USD":
            logger.warning(
                "Iranian currency exchange plugin requires USD base currency"
            )
            return {}

        if requested != supported:
            logger.warning("Iranian currency exchange plugin requires USD and IRT")
            return {}

        rate = (
            self._tgju_rate()
            if self.get_setting("API_ENABLED")
            else self._manual_rate()
        )

        if rate is None:
            return {}

        return {"USD": decimal.Decimal(1), "IRT": rate}
