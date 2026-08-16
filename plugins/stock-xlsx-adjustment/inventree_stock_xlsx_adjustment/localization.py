"""Localize plugin-owned backend strings without changing XLSX contracts."""

from django.utils.functional import lazy
from django.utils.translation import get_language

PERSIAN_MESSAGES: dict[str, str] = {
    "Stock XLSX Adjustment": "تعدیل گروهی موجودی با اکسل",
    "Preview and apply logged stock adjustments from XLSX files": (
        "پیش‌نمایش و اعمال ثبت‌شدهٔ تغییرات موجودی از فایل اکسل"
    ),
    "Preview and apply stock movements from an XLSX file": (
        "پیش‌نمایش و اعمال تغییرات موجودی از فایل اکسل"
    ),
    "Stock item change permission is required.": (
        "برای انجام این عملیات، دسترسی تغییر موجودی لازم است."
    ),
    "An XLSX file is required.": "انتخاب فایل اکسل الزامی است.",
    "Quantity must be greater than zero for add and remove operations.": (
        "برای عملیات افزایش و کاهش، مقدار باید بیشتر از صفر باشد."
    ),
    "Upload an .xlsx file.": "یک فایل با پسوند «.xlsx» بارگذاری کنید.",
    "Data file exceeds the maximum size limit.": ("حجم فایل از حداکثر مجاز بیشتر است."),
    "Could not read the XLSX file.": "خواندن فایل اکسل ممکن نبود.",
    "Data file contains no headers.": "فایل اکسل سطر عنوان ندارد.",
    "Data file has too many columns.": "تعداد ستون‌های فایل بیش از حد مجاز است.",
    "Data file has too many rows.": "تعداد ردیف‌های فایل بیش از حد مجاز است.",
    "Duplicate column: {column}": "ستون تکراری است: {column}",
    "Missing required column: {column}": "ستون الزامی وجود ندارد: {column}",
    "Data file contains no adjustment rows.": (
        "فایل اکسل هیچ ردیفی برای تغییر موجودی ندارد."
    ),
    "Stock item appears more than once; combine it into one row.": (
        "یک رکورد موجودی بیش از یک بار آمده است؛ آن را در یک ردیف ادغام کنید."
    ),
    "Serialized stock items only support a count operation with quantity 1.": (
        "برای موجودی سریال‌دار فقط عملیات شمارش با مقدار یک مجاز است."
    ),
    "Removal quantity exceeds available stock.": (
        "مقدار کسرشده از موجودی فعلی بیشتر است."
    ),
    "Resulting quantity exceeds the supported stock precision.": (
        "دقت مقدار نهایی از دقت پشتیبانی‌شدهٔ موجودی بیشتر است."
    ),
    "Stock item does not exist.": "رکورد موجودی وجود ندارد.",
    "Stock item is not currently in stock.": "این رکورد در حال حاضر موجود نیست.",
}


def is_persian(locale: str | None = None) -> bool:
    """Return whether the active locale is Persian."""
    language = (locale or get_language() or "en").replace("_", "-")
    return language.split("-", maxsplit=1)[0].lower() == "fa"


def translate(message: str) -> str:
    """Translate a plugin-owned message, falling back to English."""
    return PERSIAN_MESSAGES.get(message, message) if is_persian() else message


translate_lazy = lazy(translate, str)
