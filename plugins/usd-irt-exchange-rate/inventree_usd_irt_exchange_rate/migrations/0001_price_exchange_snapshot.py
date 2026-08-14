"""Create immutable historical part-price exchange snapshots."""

from typing import ClassVar

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Create the initial plugin-owned price snapshot table."""

    initial = True

    dependencies: ClassVar[list] = [
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations: ClassVar[list] = [
        migrations.CreateModel(
            name="PriceExchangeSnapshot",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("object_id", models.PositiveBigIntegerField()),
                ("price_field", models.CharField(max_length=50)),
                ("part_id", models.PositiveBigIntegerField(db_index=True)),
                (
                    "quantity",
                    models.DecimalField(
                        blank=True,
                        decimal_places=5,
                        max_digits=15,
                        null=True,
                    ),
                ),
                (
                    "original_amount",
                    models.DecimalField(decimal_places=6, max_digits=19),
                ),
                ("original_currency", models.CharField(max_length=10)),
                (
                    "usd_to_irt_rate",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=20,
                        null=True,
                    ),
                ),
                (
                    "amount_usd",
                    models.DecimalField(
                        blank=True,
                        decimal_places=12,
                        max_digits=39,
                        null=True,
                    ),
                ),
                (
                    "amount_irt",
                    models.DecimalField(
                        blank=True,
                        decimal_places=12,
                        max_digits=39,
                        null=True,
                    ),
                ),
                ("source_updated_at", models.DateTimeField(blank=True, null=True)),
                ("rate_updated_at", models.DateTimeField(blank=True, null=True)),
                ("captured_at", models.DateTimeField(auto_now_add=True)),
                (
                    "conversion_status",
                    models.CharField(
                        choices=[
                            ("converted", "Converted"),
                            ("missing_rate", "Missing exchange rate"),
                            ("unsupported_currency", "Unsupported currency"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="contenttypes.contenttype",
                    ),
                ),
            ],
            options={
                "ordering": ("-captured_at", "-pk"),
                "indexes": (
                    models.Index(
                        fields=["part_id", "captured_at"],
                        name="irt_snap_part_time_idx",
                    ),
                    models.Index(
                        fields=[
                            "content_type",
                            "object_id",
                            "price_field",
                            "captured_at",
                        ],
                        name="irt_snap_source_time_idx",
                    ),
                ),
            },
        ),
    ]
