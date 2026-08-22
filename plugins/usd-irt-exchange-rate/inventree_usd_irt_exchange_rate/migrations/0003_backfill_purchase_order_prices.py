"""Freeze USD and IRT pairs for existing purchase-order line prices."""

from decimal import Decimal
from typing import ClassVar

from django.db import migrations


def _price_value(instance):
    """Return a historical purchase price as an amount and currency code."""
    value = getattr(instance, "purchase_price", None)
    if value is None:
        return None

    amount = Decimal(str(getattr(value, "amount", value)))
    currency = getattr(value, "currency", None)
    if currency is None:
        currency = getattr(instance, "purchase_price_currency", "")

    return amount, str(currency)


def backfill_purchase_order_prices(apps, schema_editor):
    """Capture existing purchase-order unit prices using the applied rate."""
    database = schema_editor.connection.alias
    snapshot_model = apps.get_model(
        "inventree_usd_irt_exchange_rate", "PriceExchangeSnapshot"
    )
    content_type_model = apps.get_model("contenttypes", "ContentType")
    line_model = apps.get_model("order", "PurchaseOrderLineItem")
    supplier_part_model = apps.get_model("company", "SupplierPart")
    exchange_backend_model = apps.get_model("exchange", "ExchangeBackend")
    rate_model = apps.get_model("exchange", "Rate")

    backend = (
        exchange_backend_model.objects.using(database)
        .filter(name="InvenTreeExchange", base_currency="USD")
        .first()
    )
    rate = None
    rate_updated_at = None
    if backend is not None:
        rate_row = (
            rate_model.objects.using(database)
            .filter(backend_id=backend.pk, currency="IRT")
            .first()
        )
        if rate_row is not None and rate_row.value.is_finite() and rate_row.value > 0:
            rate = rate_row.value
            rate_updated_at = backend.last_update

    content_type, _ = content_type_model.objects.using(database).get_or_create(
        app_label="order",
        model="purchaseorderlineitem",
    )
    existing = set(
        snapshot_model.objects.using(database)
        .filter(content_type_id=content_type.pk, price_field="purchase_price")
        .values_list("object_id", flat=True)
    )
    supplier_part_ids = dict(
        supplier_part_model.objects.using(database).values_list("pk", "part_id")
    )
    pending = []

    for line in line_model.objects.using(database).all().iterator(chunk_size=500):
        if line.pk in existing:
            continue

        part_id = supplier_part_ids.get(line.part_id)
        price = _price_value(line)
        if part_id is None or price is None:
            continue

        original_amount, original_currency = price
        amount_usd = None
        amount_irt = None

        if rate is None:
            conversion_status = "missing_rate"
        elif original_currency == "USD":
            amount_usd = original_amount
            amount_irt = original_amount * rate
            conversion_status = "converted"
        elif original_currency == "IRT":
            amount_usd = original_amount / rate
            amount_irt = original_amount
            conversion_status = "converted"
        else:
            conversion_status = "unsupported_currency"

        pending.append(
            snapshot_model(
                content_type_id=content_type.pk,
                object_id=line.pk,
                price_field="purchase_price",
                part_id=part_id,
                quantity=line.quantity,
                original_amount=original_amount,
                original_currency=original_currency,
                usd_to_irt_rate=rate,
                amount_usd=amount_usd,
                amount_irt=amount_irt,
                rate_updated_at=rate_updated_at,
                conversion_status=conversion_status,
            )
        )

    snapshot_model.objects.using(database).bulk_create(pending, batch_size=500)


class Migration(migrations.Migration):
    """Backfill purchase-order prices without deleting history on rollback."""

    dependencies: ClassVar[list] = [
        ("inventree_usd_irt_exchange_rate", "0002_backfill_saved_price_snapshots"),
        ("order", "0121_add_line_item_discount"),
        ("exchange", "0001_initial"),
    ]

    operations: ClassVar[list] = [
        migrations.RunPython(
            backfill_purchase_order_prices,
            reverse_code=migrations.RunPython.noop,
        )
    ]
