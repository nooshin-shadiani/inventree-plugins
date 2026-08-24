"""Localize plugin-owned backend strings with an English fallback."""

from django.utils.functional import lazy
from django.utils.translation import get_language

PERSIAN_MESSAGES: dict[str, str] = {
    "Enter a positive, finite USD to IRT rate": (
        "یک نرخ مثبت و متناهی برای تبدیل دلار به تومان وارد کنید"
    ),
    "Iranian Currency Exchange": "نرخ تبدیل دلار و تومان",
    "Manual or TGJU-provided USD to IRT exchange rates": (
        "نرخ تبدیل دلار آمریکا به تومان، به‌صورت دستی یا از TGJU"
    ),
    "Enable TGJU USD rate consumer": "دریافت خودکار نرخ دلار از TGJU",
    "Fetch the free-market USD to IRT rate from TGJU using XPath instead of using the manual rate": (
        "دریافت نرخ آزاد دلار به تومان از TGJU با XPath به‌جای نرخ دستی"
    ),
    "Manual USD to IRT rate": "نرخ دستی دلار به تومان",
    "Iranian tomans per one US dollar": "تومان ایران به ازای یک دلار آمریکا",
    "IRT per USD": "تومان به ازای دلار",
    "Saved USD / IRT Prices": "قیمت‌های ذخیره‌شدهٔ دلار و تومان",
    "USD and IRT values frozen when each source price was saved": (
        "مقادیر دلار و تومان که هنگام ذخیرهٔ هر قیمت ثابت شده‌اند"
    ),
    "Part view permission is required.": (
        "برای مشاهدهٔ این اطلاعات، دسترسی مشاهدهٔ قطعه لازم است."
    ),
    "Purchase order view permission is required.": (
        "برای مشاهدهٔ این اطلاعات، دسترسی مشاهدهٔ سفارش خرید لازم است."
    ),
    "Stock item view permission is required.": (
        "برای مشاهدهٔ این اطلاعات، دسترسی مشاهدهٔ موجودی لازم است."
    ),
    "Supplier price": "قیمت تأمین‌کننده",
    "Purchase order line": "ردیف سفارش خرید",
    "Stock item": "موجودی",
    "Sale price": "قیمت فروش",
    "Internal price": "قیمت داخلی",
    "Part pricing": "قیمت‌گذاری قطعه",
    "Price": "قیمت",
    "Purchase price": "قیمت خرید",
    "Minimum override": "حداقل قیمت دستی",
    "Maximum override": "حداکثر قیمت دستی",
    "{label} at quantity {quantity}": "{label} برای تعداد {quantity}",
}


def is_persian(locale: str | None = None) -> bool:
    """Return whether the active locale is Persian."""
    language = (locale or get_language() or "en").replace("_", "-")
    return language.split("-", maxsplit=1)[0].lower() == "fa"


def translate(message: str) -> str:
    """Translate a plugin-owned message, falling back to English."""
    return PERSIAN_MESSAGES.get(message, message) if is_persian() else message


translate_lazy = lazy(translate, str)
