from __future__ import annotations

CATEGORIES = [
    "Software & Subscriptions",
    "Advertising & Marketing",
    "Meals & Entertainment",
    "Travel",
    "Office Supplies",
    "Professional Services",
    "Bank & Payment Fees",
    "Utilities & Telecom",
    "Contractors & Payroll",
    "Shipping & Postage",
    "Equipment & Hardware",
    "Income / Transfer In",
    "Uncategorized",
]

FALLBACK = "Uncategorized"

_ALIASES = {
    "saas": "Software & Subscriptions",
    "software": "Software & Subscriptions",
    "subscriptions": "Software & Subscriptions",
    "software and subscriptions": "Software & Subscriptions",
    "advertising": "Advertising & Marketing",
    "marketing": "Advertising & Marketing",
    "ads": "Advertising & Marketing",
    "meals": "Meals & Entertainment",
    "meals and entertainment": "Meals & Entertainment",
    "food": "Meals & Entertainment",
    "restaurants": "Meals & Entertainment",
    "travel and lodging": "Travel",
    "transportation": "Travel",
    "office": "Office Supplies",
    "supplies": "Office Supplies",
    "professional fees": "Professional Services",
    "legal": "Professional Services",
    "accounting": "Professional Services",
    "consulting": "Professional Services",
    "bank fees": "Bank & Payment Fees",
    "payment processing": "Bank & Payment Fees",
    "merchant fees": "Bank & Payment Fees",
    "utilities": "Utilities & Telecom",
    "telecom": "Utilities & Telecom",
    "internet": "Utilities & Telecom",
    "payroll": "Contractors & Payroll",
    "contractors": "Contractors & Payroll",
    "wages": "Contractors & Payroll",
    "shipping": "Shipping & Postage",
    "postage": "Shipping & Postage",
    "hardware": "Equipment & Hardware",
    "equipment": "Equipment & Hardware",
    "furniture": "Equipment & Hardware",
    "income": "Income / Transfer In",
    "transfer in": "Income / Transfer In",
    "deposit": "Income / Transfer In",
    "revenue": "Income / Transfer In",
}

_CANONICAL_BY_NORMALIZED = {c.lower(): c for c in CATEGORIES}
_CANONICAL_BY_NORMALIZED.update(
    {c.lower().replace("&", "and"): c for c in CATEGORIES}
)


def normalize_category(raw: str) -> str:
    """Map a model's free-text category onto the fixed chart of accounts.

    An accountant needs a stable vocabulary. Letting the model invent category
    names would make the ledger unusable and the CSV export unmergeable.
    """
    if not raw:
        return FALLBACK
    key = " ".join(raw.strip().lower().split())
    return (
        _CANONICAL_BY_NORMALIZED.get(key)
        or _ALIASES.get(key)
        or _ALIASES.get(key.replace("&", "and"))
        or FALLBACK
    )
