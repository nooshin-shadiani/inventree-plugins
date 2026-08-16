"""Behavior tests for the Iranian currency exchange plugin."""

import decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from moneyed import CURRENCIES

from inventree_usd_irt_exchange_rate import core

TGJU_TABLE_HTML = """
<html>
  <head><meta charset="UTF-8"></head>
  <body>
    <table>
      <tr data-market-row="price_dollar_rl" data-price="\u06f1\u066c\u06f8\u06f7\u06f8\u066c\u06f0\u06f0\u06f0"></tr>
    </table>
  </body>
</html>
""".encode()

TGJU_STICKY_HTML = b"""
<html>
  <body>
    <li id="l-price_dollar_rl">
      <span><span class="info-price">1,878,000</span></span>
    </li>
  </body>
</html>
"""

TGJU_PROFILE_HTML = b"""
<html>
  <body>
    <div data-target="profile-tour-current_rate">
      <span class="price" data-col="info.last_trade.PDrCotVal">1,878,000</span>
    </div>
  </body>
</html>
"""


class IranianCurrencyExchangeTests(SimpleTestCase):
    """Test the standalone currency exchange plugin interface."""

    def setUp(self):
        """Create a currency exchange plugin instance."""
        self.plugin = core.IranianCurrencyExchange()

    def plugin_settings(self, *, api_enabled=False, manual_rate=0, legacy_rate=0):
        """Return deterministic plugin settings for a test."""
        values = {
            "API_ENABLED": api_enabled,
            "USD_IRT_RATE": manual_rate,
            "USD_IRR_RATE": legacy_rate,
        }

        return mock.patch.object(
            self.plugin, "get_setting", side_effect=lambda key: values[key]
        )

    def test_plugin_metadata_and_settings(self):
        """Expose stable package metadata and the two operator settings."""
        self.assertEqual(self.plugin.AUTHOR, "Nooshin Shadiani")
        self.assertEqual(self.plugin.SLUG, "inventree-usd-irt-exchange-rate")
        self.assertIn("API_ENABLED", self.plugin.SETTINGS)
        self.assertIn("USD_IRT_RATE", self.plugin.SETTINGS)
        self.assertNotIn("USD_IRR_RATE", self.plugin.SETTINGS)
        self.assertNotIn("API_KEY", self.plugin.SETTINGS)

    def test_registers_iranian_toman_currency(self):
        """Register IRT so InvenTree accepts it as a supported currency."""
        self.assertIn("IRT", CURRENCIES)
        self.assertEqual(CURRENCIES["IRT"].name, "Iranian toman")

    def test_manual_rate_setting_requires_positive_finite_value(self):
        """Reject manual rates which cannot be used for conversion."""
        validators = self.plugin.SETTINGS["USD_IRT_RATE"]["validator"]
        self.assertIsInstance(validators, list)
        validator = validators[-1]
        self.assertTrue(callable(validator))

        for value in [0, -1, float("nan"), float("inf")]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validator(value)

        validator(187_800)

    def test_manual_rate_never_calls_tgju(self):
        """Use the configured IRT-per-USD value without a network request."""
        with (
            self.plugin_settings(
                api_enabled=False, manual_rate=187_800, legacy_rate=9_999_990
            ),
            mock.patch.object(self.plugin, "_tgju_rate") as tgju_rate,
        ):
            rates = self.plugin.update_exchange_rates("USD", ["USD", "IRT"])

        tgju_rate.assert_not_called()
        self.assertEqual(
            rates,
            {"USD": decimal.Decimal(1), "IRT": decimal.Decimal("187800")},
        )

    def test_legacy_manual_irr_rate_is_converted_to_irt(self):
        """Preserve version 1.0 manual rates while upgrading to IRT."""
        with (
            self.plugin_settings(manual_rate=None, legacy_rate=1_878_000),
            mock.patch.object(self.plugin, "_tgju_rate") as tgju_rate,
        ):
            rates = self.plugin.update_exchange_rates("USD", ["USD", "IRT"])

        tgju_rate.assert_not_called()
        self.assertEqual(
            rates,
            {"USD": decimal.Decimal(1), "IRT": decimal.Decimal("187800")},
        )

    @mock.patch.object(core.requests, "get")
    def test_currency_page_semantic_xpath(self, request_get):
        """Convert TGJU's rial quote to toman from the semantic table row."""
        request_get.return_value.content = TGJU_TABLE_HTML

        with self.plugin_settings(api_enabled=True):
            rates = self.plugin.update_exchange_rates("USD", ["USD", "IRT"])

        request_get.assert_called_once_with(
            "https://www.tgju.org/currency",
            headers={
                "Accept": "text/html",
                "User-Agent": "InvenTree USD IRT Exchange Rate/1.3.2",
            },
            timeout=10,
        )
        self.assertEqual(
            rates,
            {"USD": decimal.Decimal(1), "IRT": decimal.Decimal("187800")},
        )

    @mock.patch.object(core.requests, "get")
    def test_currency_page_legacy_xpath(self, request_get):
        """Support the TGJU price element used by dollar-tomans-api."""
        request_get.return_value.content = TGJU_STICKY_HTML

        with self.plugin_settings(api_enabled=True):
            rates = self.plugin.update_exchange_rates("USD", ["USD", "IRT"])

        self.assertEqual(request_get.call_count, 1)
        self.assertEqual(
            rates,
            {"USD": decimal.Decimal(1), "IRT": decimal.Decimal("187800")},
        )

    @mock.patch.object(core.requests, "get")
    def test_profile_page_xpath_fallback(self, request_get):
        """Fall back to TGJU's USD profile when the currency page changes."""
        request_get.side_effect = [
            mock.Mock(content=b"<html></html>"),
            mock.Mock(content=TGJU_PROFILE_HTML),
        ]

        with self.plugin_settings(api_enabled=True):
            rates = self.plugin.update_exchange_rates("USD", ["USD", "IRT"])

        self.assertEqual(
            [call.args[0] for call in request_get.call_args_list],
            [
                "https://www.tgju.org/currency",
                "https://www.tgju.org/profile/price_dollar_rl",
            ],
        )
        self.assertEqual(
            rates,
            {"USD": decimal.Decimal(1), "IRT": decimal.Decimal("187800")},
        )

    def test_requires_usd_base_and_exact_usd_irt_symbols(self):
        """Reject configurations which could erase or round the IRT rate."""
        with self.plugin_settings(manual_rate=200_000):
            self.assertEqual(
                self.plugin.update_exchange_rates("IRT", ["IRT", "USD"]), {}
            )
            self.assertEqual(self.plugin.update_exchange_rates("USD", ["USD"]), {})
            self.assertEqual(
                self.plugin.update_exchange_rates("USD", ["USD", "IRT", "EUR"]),
                {},
            )

    @mock.patch.object(core.requests, "get")
    def test_invalid_tgju_html_returns_no_update(self, request_get):
        """Return no update when neither TGJU page contains a valid rate."""
        request_get.return_value.content = b"<html></html>"

        with self.plugin_settings(api_enabled=True):
            rates = self.plugin.update_exchange_rates("USD", ["USD", "IRT"])

        self.assertEqual(request_get.call_count, 2)
        self.assertEqual(rates, {})

    def test_schedule_runs_every_three_hours(self):
        """Register the TGJU refresh with InvenTree's Django-Q2 scheduler."""
        self.assertEqual(
            self.plugin.get_scheduled_tasks(),
            {
                "refresh_usd_irt": {
                    "func": "refresh_usd_irt",
                    "schedule": "I",
                    "minutes": 180,
                }
            },
        )

    @mock.patch("InvenTree.tasks.update_exchange_rates")
    def test_scheduled_refresh_exits_when_api_disabled(self, update_rates):
        """Do not invoke an exchange update while TGJU consumption is disabled."""
        with self.plugin_settings(api_enabled=False):
            self.plugin.refresh_usd_irt()

        update_rates.assert_not_called()

    @mock.patch("InvenTree.tasks.update_exchange_rates")
    def test_scheduled_refresh_updates_selected_plugin(self, update_rates):
        """Force an update when the enabled plugin is selected."""
        with (
            self.plugin_settings(api_enabled=True),
            mock.patch.object(
                core, "get_global_setting", return_value=self.plugin.slug
            ),
        ):
            self.plugin.refresh_usd_irt()

        update_rates.assert_called_once_with(force=True)
