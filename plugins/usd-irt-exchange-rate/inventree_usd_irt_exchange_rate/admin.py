"""Read-only administration for historical price snapshots."""

from django.contrib import admin

from .models import PriceExchangeSnapshot


@admin.register(PriceExchangeSnapshot)
class PriceExchangeSnapshotAdmin(admin.ModelAdmin):
    """Expose captured prices without allowing history to be rewritten."""

    list_display = (
        "captured_at",
        "part_id",
        "price_field",
        "original_amount",
        "original_currency",
        "usd_to_irt_rate",
        "amount_usd",
        "amount_irt",
        "conversion_status",
    )
    list_filter = ("conversion_status", "original_currency", "price_field")
    search_fields = ("=part_id", "=object_id")
    ordering = ("-captured_at",)
    date_hierarchy = "captured_at"
    readonly_fields = (
        "content_type",
        "object_id",
        "price_field",
        "part_id",
        "quantity",
        "original_amount",
        "original_currency",
        "usd_to_irt_rate",
        "amount_usd",
        "amount_irt",
        "source_updated_at",
        "rate_updated_at",
        "captured_at",
        "conversion_status",
    )

    def has_add_permission(self, request):
        """Prevent manually creating historical records."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent rewriting historical records."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deleting historical records."""
        return False
