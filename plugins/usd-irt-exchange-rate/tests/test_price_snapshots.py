"""Behavior tests for historical part-price exchange snapshots."""

from decimal import Decimal
from unittest import mock

import company.models
import part.models
import stock.models
from django.contrib.contenttypes.models import ContentType
from django.db import OperationalError
from djmoney.contrib.exchange.models import ExchangeBackend, Rate
from djmoney.money import Money
from InvenTree.unit_test import InvenTreeTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from inventree_usd_irt_exchange_rate import core as _currency_registration  # noqa: F401
from inventree_usd_irt_exchange_rate import signals, views
from inventree_usd_irt_exchange_rate.models import PriceExchangeSnapshot


class PriceExchangeSnapshotTests(InvenTreeTestCase):
    """Test immutable USD and IRT values captured when part prices are saved."""

    def setUp(self):
        """Create a supplier part whose prices can be captured."""
        super().setUp()

        self.part = part.models.Part.objects.create(
            name="Snapshot Part",
            description="Part used to test historical exchange snapshots",
        )
        self.supplier = company.models.Company.objects.create(
            name="Snapshot Supplier", is_supplier=True
        )
        self.supplier_part = company.models.SupplierPart.objects.create(
            supplier=self.supplier,
            part=self.part,
            SKU="SNAPSHOT-SKU",
        )

    def create_applied_rate(self, value=Decimal("187800")):
        """Create the USD-based rate currently applied by InvenTree."""
        backend = ExchangeBackend.objects.create(
            name="InvenTreeExchange", base_currency="USD"
        )
        Rate.objects.create(backend=backend, currency="USD", value=Decimal("1"))
        Rate.objects.create(backend=backend, currency="IRT", value=value)
        return backend

    def snapshots_for(self, price_break):
        """Return snapshots for one price field in capture order."""
        return PriceExchangeSnapshot.objects.filter(
            content_type=ContentType.objects.get_for_model(price_break),
            object_id=price_break.pk,
            price_field="price",
        ).order_by("captured_at", "pk")

    def test_supplier_usd_price_captures_applied_usd_to_irt_rate(self):
        """Lock USD and IRT equivalents using the applied database rate."""
        backend = self.create_applied_rate()

        price_break = company.models.SupplierPriceBreak.objects.create(
            part=self.supplier_part,
            quantity=5,
            price=Money("10", "USD"),
        )

        snapshot = self.snapshots_for(price_break).get()
        self.assertEqual(snapshot.part_id, self.part.pk)
        self.assertEqual(snapshot.quantity, Decimal("5"))
        self.assertEqual(snapshot.original_amount, Decimal("10"))
        self.assertEqual(snapshot.original_currency, "USD")
        self.assertEqual(snapshot.usd_to_irt_rate, Decimal("187800"))
        self.assertEqual(snapshot.amount_usd, Decimal("10"))
        self.assertEqual(snapshot.amount_irt, Decimal("1878000"))
        self.assertEqual(snapshot.source_updated_at, price_break.updated)
        self.assertEqual(snapshot.rate_updated_at, backend.last_update)
        self.assertEqual(snapshot.conversion_status, "converted")

    def test_stock_item_purchase_price_captures_applied_rate(self):
        """Freeze the unit purchase price saved on a physical stock item."""
        backend = self.create_applied_rate()

        item = stock.models.StockItem.objects.create(
            part=self.part,
            quantity=7,
            purchase_price=Money("12", "USD"),
        )

        snapshot = PriceExchangeSnapshot.objects.get(
            content_type=ContentType.objects.get_for_model(item),
            object_id=item.pk,
            price_field="purchase_price",
        )
        self.assertEqual(snapshot.part_id, self.part.pk)
        self.assertEqual(snapshot.quantity, Decimal("7"))
        self.assertEqual(snapshot.original_amount, Decimal("12"))
        self.assertEqual(snapshot.original_currency, "USD")
        self.assertEqual(snapshot.usd_to_irt_rate, Decimal("187800"))
        self.assertEqual(snapshot.amount_usd, Decimal("12"))
        self.assertEqual(snapshot.amount_irt, Decimal("2253600"))
        self.assertEqual(snapshot.source_updated_at, item.updated)
        self.assertEqual(snapshot.rate_updated_at, backend.last_update)
        self.assertEqual(snapshot.conversion_status, "converted")

        item.quantity = Decimal("5")
        item.save()
        self.assertEqual(
            PriceExchangeSnapshot.objects.filter(
                content_type=ContentType.objects.get_for_model(item),
                object_id=item.pk,
                price_field="purchase_price",
            ).count(),
            1,
        )

    def test_stock_item_price_endpoint_returns_its_frozen_pair(self):
        """Return only the saved purchase-price pair for the requested item."""
        self.create_applied_rate()
        item = stock.models.StockItem.objects.create(
            part=self.part,
            quantity=4,
            purchase_price=Money("15", "USD"),
        )
        other_item = stock.models.StockItem.objects.create(
            part=self.part,
            quantity=2,
            purchase_price=Money("20", "USD"),
        )
        self.user.is_superuser = True
        self.user.save()
        request = APIRequestFactory().get("/")
        force_authenticate(request, user=self.user)

        response = views.StockItemPriceSnapshotView.as_view()(
            request,
            stock_item_id=item.pk,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["stock_item"], item.pk)
        self.assertEqual(len(response.data["results"]), 1)
        result = response.data["results"][0]
        self.assertEqual(result["source"], f"Stock item #{item.pk} at quantity 4")
        self.assertEqual(result["original_amount"], "15.000000")
        self.assertEqual(result["original_currency"], "USD")
        self.assertEqual(result["amount_usd"], "15.000000000000")
        self.assertEqual(result["amount_irt"], "2817000.000000000000")
        self.assertNotEqual(response.data["stock_item"], other_item.pk)

    def test_price_and_rate_changes_append_without_rewriting_history(self):
        """Keep the first conversion immutable when a later price is saved."""
        backend = self.create_applied_rate()
        price_break = company.models.SupplierPriceBreak.objects.create(
            part=self.supplier_part,
            quantity=1,
            price=Money("10", "USD"),
        )

        original_snapshot = self.snapshots_for(price_break).get()

        Rate.objects.filter(backend=backend, currency="IRT").update(
            value=Decimal("200000")
        )
        backend.save()
        backend.refresh_from_db()

        price_break.price = Money("12", "USD")
        price_break.save()

        snapshots = list(self.snapshots_for(price_break))
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[0].pk, original_snapshot.pk)
        self.assertEqual(snapshots[0].original_amount, Decimal("10"))
        self.assertEqual(snapshots[0].usd_to_irt_rate, Decimal("187800"))
        self.assertEqual(snapshots[0].amount_usd, Decimal("10"))
        self.assertEqual(snapshots[0].amount_irt, Decimal("1878000"))
        self.assertEqual(snapshots[1].original_amount, Decimal("12"))
        self.assertEqual(snapshots[1].usd_to_irt_rate, Decimal("200000"))
        self.assertEqual(snapshots[1].amount_usd, Decimal("12"))
        self.assertEqual(snapshots[1].amount_irt, Decimal("2400000"))
        self.assertEqual(snapshots[1].rate_updated_at, backend.last_update)

        original_snapshot.refresh_from_db()
        self.assertEqual(original_snapshot.original_amount, Decimal("10"))
        self.assertEqual(original_snapshot.usd_to_irt_rate, Decimal("187800"))
        self.assertEqual(original_snapshot.amount_irt, Decimal("1878000"))

    def test_irt_price_captures_inverse_usd_value(self):
        """Divide an IRT price by the applied rate to lock its USD value."""
        self.create_applied_rate()

        price_break = company.models.SupplierPriceBreak.objects.create(
            part=self.supplier_part,
            quantity=10,
            price=Money("1878000", "IRT"),
        )

        snapshot = self.snapshots_for(price_break).get()
        self.assertEqual(snapshot.original_amount, Decimal("1878000"))
        self.assertEqual(snapshot.original_currency, "IRT")
        self.assertEqual(snapshot.usd_to_irt_rate, Decimal("187800"))
        self.assertEqual(snapshot.amount_usd, Decimal("10"))
        self.assertEqual(snapshot.amount_irt, Decimal("1878000"))
        self.assertEqual(snapshot.conversion_status, "converted")

    def test_unchanged_price_save_does_not_duplicate_snapshot(self):
        """Ignore saves which do not change the price amount or currency."""
        self.create_applied_rate()
        price_break = company.models.SupplierPriceBreak.objects.create(
            part=self.supplier_part,
            quantity=1,
            price=Money("10", "USD"),
        )

        first_snapshot = self.snapshots_for(price_break).get()
        price_break.save()

        snapshots = self.snapshots_for(price_break)
        self.assertEqual(snapshots.count(), 1)
        self.assertEqual(snapshots.get().pk, first_snapshot.pk)

    def test_delayed_receiver_cannot_append_an_older_price_last(self):
        """Refresh the locked source before a delayed receiver captures it."""
        self.create_applied_rate()
        price_break = company.models.SupplierPriceBreak.objects.create(
            part=self.supplier_part,
            quantity=1,
            price=Money("10", "USD"),
        )
        stale_instance = company.models.SupplierPriceBreak.objects.get(
            pk=price_break.pk
        )

        price_break.price = Money("12", "USD")
        price_break.save()

        signals.capture_price_break(
            company.models.SupplierPriceBreak,
            stale_instance,
        )

        snapshots = list(self.snapshots_for(price_break))
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[-1].original_amount, Decimal("12"))

    def test_missing_rate_preserves_original_price_without_blocking_save(self):
        """Record an unconverted original value when no applied rate exists."""
        price_break = company.models.SupplierPriceBreak.objects.create(
            part=self.supplier_part,
            quantity=3,
            price=Money("25", "USD"),
        )

        snapshot = self.snapshots_for(price_break).get()
        self.assertEqual(snapshot.original_amount, Decimal("25"))
        self.assertEqual(snapshot.original_currency, "USD")
        self.assertIsNone(snapshot.usd_to_irt_rate)
        self.assertIsNone(snapshot.amount_usd)
        self.assertIsNone(snapshot.amount_irt)
        self.assertIsNone(snapshot.rate_updated_at)
        self.assertEqual(snapshot.conversion_status, "missing_rate")

    def test_unsupported_currency_preserves_original_price(self):
        """Do not invent USD or IRT values for a legacy third-currency price."""
        self.create_applied_rate()
        price_break = company.models.SupplierPriceBreak.objects.create(
            part=self.supplier_part,
            quantity=1,
            price=Money("7", "EUR"),
        )

        snapshot = self.snapshots_for(price_break).get()
        self.assertEqual(snapshot.original_amount, Decimal("7"))
        self.assertEqual(snapshot.original_currency, "EUR")
        self.assertEqual(snapshot.usd_to_irt_rate, Decimal("187800"))
        self.assertIsNone(snapshot.amount_usd)
        self.assertIsNone(snapshot.amount_irt)
        self.assertEqual(snapshot.conversion_status, "unsupported_currency")

    def test_snapshot_database_failure_does_not_block_price_save(self):
        """Keep core price entry available if auxiliary snapshot storage fails."""
        self.create_applied_rate()

        with (
            self.assertLogs("inventree", level="ERROR") as logs,
            mock.patch.object(
                PriceExchangeSnapshot.objects,
                "create",
                side_effect=OperationalError("snapshot table unavailable"),
            ),
        ):
            price_break = company.models.SupplierPriceBreak.objects.create(
                part=self.supplier_part,
                quantity=1,
                price=Money("9", "USD"),
            )

        self.assertTrue(
            company.models.SupplierPriceBreak.objects.filter(pk=price_break.pk).exists()
        )
        self.assertIn("Could not capture price snapshot", logs.output[0])

    def test_sale_and_internal_price_breaks_are_captured(self):
        """Capture both direct sale-price fields associated with a part."""
        self.create_applied_rate()

        sale_price = part.models.PartSellPriceBreak.objects.create(
            part=self.part,
            quantity=2,
            price=Money("15", "USD"),
        )
        internal_price = part.models.PartInternalPriceBreak.objects.create(
            part=self.part,
            quantity=4,
            price=Money("20", "USD"),
        )

        sale_snapshot = self.snapshots_for(sale_price).get()
        internal_snapshot = self.snapshots_for(internal_price).get()
        self.assertEqual(sale_snapshot.part_id, self.part.pk)
        self.assertEqual(sale_snapshot.quantity, Decimal("2"))
        self.assertEqual(sale_snapshot.amount_irt, Decimal("2817000"))
        self.assertEqual(internal_snapshot.part_id, self.part.pk)
        self.assertEqual(internal_snapshot.quantity, Decimal("4"))
        self.assertEqual(internal_snapshot.amount_irt, Decimal("3756000"))

    def test_part_pricing_overrides_are_captured_separately(self):
        """Capture the two user-entered part pricing override fields."""
        self.create_applied_rate()
        pricing = self.part.pricing
        pricing.override_min = Money("8", "USD")
        pricing.override_max = Money("11", "USD")
        pricing.save()

        content_type = ContentType.objects.get_for_model(pricing)
        snapshots = PriceExchangeSnapshot.objects.filter(
            content_type=content_type,
            object_id=pricing.pk,
        )

        minimum = snapshots.get(price_field="override_min")
        maximum = snapshots.get(price_field="override_max")
        self.assertEqual(minimum.part_id, self.part.pk)
        self.assertIsNone(minimum.quantity)
        self.assertEqual(minimum.amount_usd, Decimal("8"))
        self.assertEqual(minimum.amount_irt, Decimal("1502400"))
        self.assertEqual(maximum.part_id, self.part.pk)
        self.assertIsNone(maximum.quantity)
        self.assertEqual(maximum.amount_usd, Decimal("11"))
        self.assertEqual(maximum.amount_irt, Decimal("2065800"))
