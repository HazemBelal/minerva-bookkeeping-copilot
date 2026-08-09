from app.categories import CATEGORIES, normalize_category


def test_exact_canonical_name_passes_through():
    assert normalize_category("Software & Subscriptions") == "Software & Subscriptions"


def test_matching_is_case_and_whitespace_insensitive():
    assert normalize_category("  software & subscriptions ") == "Software & Subscriptions"


def test_common_llm_phrasings_map_to_canonical_names():
    assert normalize_category("SaaS") == "Software & Subscriptions"
    assert normalize_category("software") == "Software & Subscriptions"
    assert normalize_category("meals and entertainment") == "Meals & Entertainment"
    assert normalize_category("bank fees") == "Bank & Payment Fees"


def test_unknown_category_falls_back_rather_than_inventing_one():
    assert normalize_category("Interdimensional Freight") == "Uncategorized"
    assert normalize_category("") == "Uncategorized"


def test_fallback_is_itself_a_canonical_category():
    assert "Uncategorized" in CATEGORIES
