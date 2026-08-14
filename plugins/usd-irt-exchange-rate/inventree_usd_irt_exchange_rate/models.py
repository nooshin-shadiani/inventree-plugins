"""Persistent historical exchange snapshots for part prices."""

from django.contrib.contenttypes.models import ContentType
from django.db import models


class PriceExchangeSnapshot(models.Model):
    """Store immutable USD and IRT values for one saved part price."""

    class ConversionStatus(models.TextChoices):
        """Result of converting the original price."""

        CONVERTED = "converted", "Converted"
        MISSING_RATE = "missing_rate", "Missing exchange rate"
        UNSUPPORTED_CURRENCY = "unsupported_currency", "Unsupported currency"

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="+",
    )
    object_id = models.PositiveBigIntegerField()
    price_field = models.CharField(max_length=50)
    part_id = models.PositiveBigIntegerField(db_index=True)
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=5,
        blank=True,
        null=True,
    )
    original_amount = models.DecimalField(max_digits=19, decimal_places=6)
    original_currency = models.CharField(max_length=10)
    usd_to_irt_rate = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        blank=True,
        null=True,
    )
    amount_usd = models.DecimalField(
        max_digits=39,
        decimal_places=12,
        blank=True,
        null=True,
    )
    amount_irt = models.DecimalField(
        max_digits=39,
        decimal_places=12,
        blank=True,
        null=True,
    )
    source_updated_at = models.DateTimeField(blank=True, null=True)
    rate_updated_at = models.DateTimeField(blank=True, null=True)
    captured_at = models.DateTimeField(auto_now_add=True)
    conversion_status = models.CharField(
        max_length=30,
        choices=ConversionStatus.choices,
    )

    class Meta:
        """Define stable ordering and lookup indexes."""

        ordering = ("-captured_at", "-pk")
        indexes = (
            models.Index(
                fields=("part_id", "captured_at"),
                name="irt_snap_part_time_idx",
            ),
            models.Index(
                fields=(
                    "content_type",
                    "object_id",
                    "price_field",
                    "captured_at",
                ),
                name="irt_snap_source_time_idx",
            ),
        )

    def __str__(self):
        """Return a concise description of the captured price."""
        return (
            f"{self.content_type}:{self.object_id}.{self.price_field} "
            f"{self.original_amount} {self.original_currency}"
        )
