"""Freeze USD and IRT pairs for prices which predate snapshot support."""

from decimal import Decimal
from typing import ClassVar

from django.db import migrations


def _price_value(instance, field_name):
    """Return a historical money field as an amount and currency code."""
    value = getattr(instance, field_name, None)
    if value is None:
        return None

    amount = Decimal(str(getattr(value, "amount", value)))
    currency = getattr(value, "currency", None)
    if currency is None:
        currency = getattr(instance, f"{field_name}_currency", "")

    return amount, str(currency)


def backfill_saved_price_snapshots(apps, schema_editor):  # noqa: PLR0915
    """Capture every existing user-entered price using the applied rate."""
    database = schema_editor.connection.alias
    snapshot_model = apps.get_model(
        "inventree_usd_irt_exchange_rate", "PriceExchangeSnapshot"
    )
    content_type_model = apps.get_model("contenttypes", "ContentType")
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

    existing = set(
        snapshot_model.objects.using(database).values_list(
            "content_type_id", "object_id", "price_field"
        )
    )
    pending = []

    def capture_sources(*, app_label, model_name, price_fields, part_id_for_source):
        model = apps.get_model(app_label, model_name)
        content_type, _ = content_type_model.objects.using(database).get_or_create(
            app_label=app_label,
            model=model_name.lower(),
        )

        for source in model.objects.using(database).all().iterator(chunk_size=500):
            part_id = part_id_for_source(source)
            if part_id is None:
                continue

            for price_field in price_fields:
                source_key = (content_type.pk, source.pk, price_field)
                if source_key in existing:
                    continue

                price = _price_value(source, price_field)
                if price is None:
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
                        object_id=source.pk,
                        price_field=price_field,
                        part_id=part_id,
                        quantity=getattr(source, "quantity", None),
                        original_amount=original_amount,
                        original_currency=original_currency,
                        usd_to_irt_rate=rate,
                        amount_usd=amount_usd,
                        amount_irt=amount_irt,
                        source_updated_at=getattr(source, "updated", None),
                        rate_updated_at=rate_updated_at,
                        conversion_status=conversion_status,
                    )
                )
                existing.add(source_key)

    supplier_part_model = apps.get_model("company", "SupplierPart")
    supplier_part_ids = dict(
        supplier_part_model.objects.using(database).values_list("pk", "part_id")
    )
    capture_sources(
        app_label="company",
        model_name="SupplierPriceBreak",
        price_fields=("price",),
        part_id_for_source=lambda source: supplier_part_ids.get(source.part_id),
    )
    capture_sources(
        app_label="part",
        model_name="PartSellPriceBreak",
        price_fields=("price",),
        part_id_for_source=lambda source: source.part_id,
    )
    capture_sources(
        app_label="part",
        model_name="PartInternalPriceBreak",
        price_fields=("price",),
        part_id_for_source=lambda source: source.part_id,
    )
    capture_sources(
        app_label="part",
        model_name="PartPricing",
        price_fields=("override_min", "override_max"),
        part_id_for_source=lambda source: source.part_id,
    )

    snapshot_model.objects.using(database).bulk_create(pending, batch_size=500)


class Migration(migrations.Migration):
    """Backfill immutable pairs without deleting history on rollback."""

    dependencies: ClassVar[list] = [
        ("inventree_usd_irt_exchange_rate", "0001_price_exchange_snapshot"),
        ("company", "0052_alter_supplierpricebreak_updated"),
        ("part", "0119_auto_20231120_0457"),
        ("exchange", "0001_initial"),
    ]

    operations: ClassVar[list] = [
        migrations.RunPython(
            backfill_saved_price_snapshots,
            reverse_code=migrations.RunPython.noop,
        )
    ]
