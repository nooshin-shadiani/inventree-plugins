"""Parse, validate, preview, and apply XLSX stock adjustments."""

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from zipfile import BadZipFile

import tablib
from common.settings import get_global_setting
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from importer.operations import load_data_file
from importer.validators import (
    IMPORTER_MAX_COLS,
    IMPORTER_MAX_FILE_SIZE,
    IMPORTER_MAX_ROWS,
)
from InvenTree.tasks import batch_offload_tasks
from openpyxl.utils.exceptions import InvalidFileException
from plugin.base.event.events import batch_events
from rest_framework import serializers
from stock.models import StockItem, batch_tracking_entries

from .localization import translate as _

REQUIRED_COLUMNS = ("stock_item_id", "operation", "quantity")
OPTIONAL_COLUMNS = ("notes",)
ALL_COLUMNS = (*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS)
OPERATIONS = ("add", "remove", "count")


class SpreadsheetRowSerializer(serializers.Serializer):
    """Validate one normalized spreadsheet row."""

    stock_item_id = serializers.IntegerField(min_value=1)
    operation = serializers.ChoiceField(choices=OPERATIONS)
    quantity = serializers.DecimalField(
        max_digits=15, decimal_places=5, min_value=Decimal(0)
    )
    notes = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=512
    )

    def validate(self, attrs):
        """Require a positive delta for add and remove operations."""
        if attrs["operation"] in {"add", "remove"} and attrs["quantity"] <= 0:
            raise serializers.ValidationError(
                {
                    "quantity": _(
                        "Quantity must be greater than zero for add and remove operations."
                    )
                }
            )

        return attrs


def _flatten_errors(errors) -> list[str]:
    """Flatten serializer errors into short row-level messages."""
    messages = []

    if isinstance(errors, dict):
        for key, value in errors.items():
            for message in _flatten_errors(value):
                messages.append(f"{key}: {message}")
    elif isinstance(errors, (list, tuple)):
        for value in errors:
            messages.extend(_flatten_errors(value))
    else:
        messages.append(str(errors))

    return messages


def _display_decimal(value: Decimal | None) -> str | None:
    """Render a decimal without unnecessary trailing zeroes."""
    if value is None:
        return None

    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _normalize_integer(value):
    """Accept integral numeric cells emitted by spreadsheet readers."""
    if isinstance(value, bool):
        return ""

    if isinstance(value, (float, Decimal)) and value == int(value):
        return int(value)

    return value


@dataclass
class AdjustmentRow:
    """A parsed spreadsheet row and its validation result."""

    line: int
    stock_item_id: int | None = None
    operation: str = ""
    quantity: Decimal | None = None
    notes: str = ""
    errors: list[str] = field(default_factory=list)
    item: StockItem | None = None
    current_quantity: Decimal | None = None
    resulting_quantity: Decimal | None = None

    def as_dict(self) -> dict:
        """Return the public preview representation."""
        item = self.item

        return {
            "line": self.line,
            "stock_item_id": self.stock_item_id,
            "part": item.part.full_name if item else None,
            "location": str(item.location) if item and item.location else None,
            "operation": self.operation,
            "quantity": _display_decimal(self.quantity),
            "current_quantity": _display_decimal(self.current_quantity),
            "resulting_quantity": _display_decimal(self.resulting_quantity),
            "notes": self.notes,
            "valid": not self.errors,
            "errors": self.errors,
        }


def _load_dataset(upload) -> tablib.Dataset:
    """Load an XLSX upload after applying InvenTree's importer limits."""
    if Path(upload.name).suffix.lower() != ".xlsx":
        raise serializers.ValidationError({"file": [_("Upload an .xlsx file.")]})

    if upload.size > IMPORTER_MAX_FILE_SIZE:
        raise serializers.ValidationError(
            {"file": [_("Data file exceeds the maximum size limit.")]}
        )

    try:
        dataset = load_data_file(upload, file_format="xlsx")
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"file": exc.messages}) from exc
    except (
        BadZipFile,
        InvalidFileException,
        KeyError,
        OSError,
        SyntaxError,
        ValueError,
    ) as exc:
        raise serializers.ValidationError(
            {"file": [_("Could not read the XLSX file.")]}
        ) from exc

    if not dataset.headers:
        raise serializers.ValidationError(
            {"file": [_("Data file contains no headers.")]}
        )

    if len(dataset.headers) > IMPORTER_MAX_COLS:
        raise serializers.ValidationError(
            {"file": [_("Data file has too many columns.")]}
        )

    if len(dataset) > IMPORTER_MAX_ROWS:
        raise serializers.ValidationError({"file": [_("Data file has too many rows.")]})

    return dataset


def _parse_rows(upload) -> list[AdjustmentRow]:
    """Parse and validate spreadsheet cell values without accessing stock."""
    dataset = _load_dataset(upload)
    normalized_headers = [str(value or "").strip().lower() for value in dataset.headers]

    duplicates = sorted(
        {
            header
            for header in normalized_headers
            if normalized_headers.count(header) > 1
        }
    )
    if duplicates:
        raise serializers.ValidationError(
            {
                "file": [
                    _("Duplicate column: {column}").format(column=header)
                    for header in duplicates
                ]
            }
        )

    missing = [
        column for column in REQUIRED_COLUMNS if column not in normalized_headers
    ]
    if missing:
        raise serializers.ValidationError(
            {
                "file": [
                    _("Missing required column: {column}").format(column=column)
                    for column in missing
                ]
            }
        )

    indexes = {
        name: normalized_headers.index(name)
        for name in ALL_COLUMNS
        if name in normalized_headers
    }
    rows = []

    for line, source_row in enumerate(dataset, start=2):
        raw = {name: source_row[indexes[name]] for name in indexes}

        if all(value is None or str(value).strip() == "" for value in raw.values()):
            continue

        raw["stock_item_id"] = _normalize_integer(raw.get("stock_item_id"))
        raw["operation"] = str(raw.get("operation") or "").strip().lower()
        raw["notes"] = "" if raw.get("notes") is None else raw["notes"]

        serializer = SpreadsheetRowSerializer(data=raw)
        adjustment = AdjustmentRow(line=line)

        if serializer.is_valid():
            adjustment.stock_item_id = serializer.validated_data["stock_item_id"]
            adjustment.operation = serializer.validated_data["operation"]
            adjustment.quantity = serializer.validated_data["quantity"]
            adjustment.notes = serializer.validated_data["notes"]
        else:
            adjustment.errors.extend(_flatten_errors(serializer.errors))

        rows.append(adjustment)

    if not rows:
        raise serializers.ValidationError(
            {"file": [_("Data file contains no adjustment rows.")]}
        )

    first_rows = {}
    for row in rows:
        if row.stock_item_id is None or row.errors:
            continue

        if first := first_rows.get(row.stock_item_id):
            message = _("Stock item appears more than once; combine it into one row.")
            if message not in first.errors:
                first.errors.append(message)
            row.errors.append(message)
        else:
            first_rows[row.stock_item_id] = row

    return rows


def _calculate_result(row: AdjustmentRow, item: StockItem) -> None:
    """Validate operation-specific rules and set the projected quantity."""
    if item.serialized:
        if row.operation == "count" and row.quantity == Decimal(1):
            row.resulting_quantity = Decimal(1)
        else:
            row.errors.append(
                _(
                    "Serialized stock items only support a count operation with quantity 1."
                )
            )
        return

    if row.operation == "add":
        row.resulting_quantity = item.quantity + row.quantity
    elif row.operation == "remove":
        if row.quantity > item.quantity:
            row.errors.append(_("Removal quantity exceeds available stock."))
        else:
            row.resulting_quantity = item.quantity - row.quantity
    else:
        row.resulting_quantity = row.quantity

    if row.resulting_quantity is None:
        return

    try:
        StockItem._meta.get_field("quantity").clean(row.resulting_quantity, item)
    except DjangoValidationError:
        row.errors.append(
            _("Resulting quantity exceeds the supported stock precision.")
        )


def _attach_stock_items(rows: list[AdjustmentRow], lock: bool) -> None:
    """Attach stock records and calculate the result of each valid adjustment."""
    ids = sorted(
        {row.stock_item_id for row in rows if row.stock_item_id and not row.errors}
    )
    queryset = StockItem.objects.filter(pk__in=ids)

    if lock:
        queryset = queryset.select_for_update()
    else:
        queryset = queryset.select_related("part", "location")

    items = {item.pk: item for item in queryset.order_by("pk")}
    allow_out_of_stock = get_global_setting(
        "STOCK_ALLOW_OUT_OF_STOCK_TRANSFER", backup_value=False, cache=False
    )

    for row in rows:
        if row.stock_item_id is None or row.errors:
            continue

        item = items.get(row.stock_item_id)
        if item is None:
            row.errors.append(_("Stock item does not exist."))
            continue

        row.item = item
        row.current_quantity = item.quantity

        if not allow_out_of_stock and not item.is_in_stock(
            check_status=False, check_quantity=False, check_in_production=False
        ):
            row.errors.append(_("Stock item is not currently in stock."))
            continue

        _calculate_result(row, item)


def _result(rows: list[AdjustmentRow], applied: bool = False) -> dict:
    """Build the API response for a preview or completed import."""
    valid_rows = [row for row in rows if not row.errors]
    operation_counts = {
        operation: sum(row.operation == operation for row in valid_rows)
        for operation in OPERATIONS
    }

    return {
        "total_rows": len(rows),
        "valid_rows": len(valid_rows),
        "error_rows": len(rows) - len(valid_rows),
        "operation_counts": operation_counts,
        "can_apply": bool(rows) and len(valid_rows) == len(rows),
        "applied": applied,
        "rows": [row.as_dict() for row in rows],
    }


def preview_adjustments(upload) -> dict:
    """Validate an upload and return its projected stock quantities."""
    rows = _parse_rows(upload)
    _attach_stock_items(rows, lock=False)
    return _result(rows)


def apply_adjustments(upload, user) -> dict:
    """Validate and atomically apply every adjustment in an upload."""
    with (
        transaction.atomic(),
        batch_events(),
        batch_tracking_entries(),
        batch_offload_tasks(),
    ):
        rows = _parse_rows(upload)
        _attach_stock_items(rows, lock=True)
        preview = _result(rows)

        if not preview["can_apply"]:
            return preview

        for row in rows:
            item = row.item

            if row.operation == "add":
                item.add_stock(row.quantity, user, notes=row.notes)
            elif row.operation == "remove":
                item.take_stock(row.quantity, user, notes=row.notes)
            else:
                item.stocktake(row.quantity, user, notes=row.notes)

    return _result(rows, applied=True)


def template_workbook() -> bytes:
    """Return a small XLSX workbook demonstrating the supported contract."""
    dataset = tablib.Dataset(headers=list(ALL_COLUMNS))
    dataset.append([42, "add", 10, "Received into stock"])
    dataset.append([51, "remove", 3, "Damaged components"])
    dataset.append([63, "count", 25, "Physical stocktake"])
    return dataset.export("xlsx")
