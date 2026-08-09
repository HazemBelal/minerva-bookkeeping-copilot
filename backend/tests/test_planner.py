"""Coverage for plan_merchants' reconciliation logic: the category-normalization
gate, confidence coercion, and never-drop-merchant guarantee. No live LLM --
`app.planner.structured_completion` is monkeypatched to return controlled fake
responses (or None, to simulate total LLM failure)."""

from __future__ import annotations

import pytest

from app import planner as planner_module
from app.categories import CATEGORIES
from app.planner import MerchantPlan, _PlanResponse, plan_merchants
from app.statement import Txn


def _txn(id: int, key: str, description: str) -> Txn:
    return Txn(id=id, date="2026-07-01", description=description, amount=-10.0, merchant_key=key)


TXNS = [
    _txn(0, "amzn mktp us", "AMZN MKTP US*2K4L9RT31"),
    _txn(1, "grain cafe", "TST* GRAIN CAFE 4471"),
    _txn(2, "sqsp inv", "SQSP* INV 8823941"),
]


@pytest.mark.asyncio
async def test_off_list_category_is_normalized_into_the_canonical_list(monkeypatch):
    fake = _PlanResponse(
        merchants=[
            MerchantPlan(
                key="amzn mktp us",
                display="AMZN MKTP US",
                needs_research=False,
                category="Software and Services",  # not in CATEGORIES, no alias either
                confidence="high",
                reason="looks like software",
            ),
            MerchantPlan(
                key="grain cafe",
                display="GRAIN CAFE",
                needs_research=True,
                category="ignored",
                confidence="low",
                reason="unclear",
            ),
            MerchantPlan(
                key="sqsp inv",
                display="SQSP INV",
                needs_research=True,
                category="ignored",
                confidence="low",
                reason="unclear",
            ),
        ]
    )

    async def fake_structured_completion(system, user, schema):
        return fake

    monkeypatch.setattr(planner_module, "structured_completion", fake_structured_completion)

    result = await plan_merchants(TXNS, "Categorize these transactions.")

    amzn = next(p for p in result if p.key == "amzn mktp us")
    # Never emit the model's raw off-list string -- gated through normalize_category.
    assert amzn.category != "Software and Services"
    assert amzn.category in CATEGORIES


@pytest.mark.asyncio
async def test_invalid_confidence_is_coerced_to_low(monkeypatch):
    fake = _PlanResponse(
        merchants=[
            MerchantPlan(
                key="amzn mktp us",
                display="AMZN MKTP US",
                needs_research=False,
                category="Shipping & Postage",
                confidence="very high",  # not one of high/medium/low
                reason="confident",
            ),
            MerchantPlan(
                key="grain cafe",
                display="GRAIN CAFE",
                needs_research=False,
                category="Meals & Entertainment",
                confidence="",  # empty string, also invalid
                reason="confident",
            ),
            MerchantPlan(
                key="sqsp inv",
                display="SQSP INV",
                needs_research=False,
                category="Software & Subscriptions",
                confidence="medium",  # valid, must pass through unchanged
                reason="confident",
            ),
        ]
    )

    async def fake_structured_completion(system, user, schema):
        return fake

    monkeypatch.setattr(planner_module, "structured_completion", fake_structured_completion)

    result = await plan_merchants(TXNS, "Categorize these transactions.")
    by_key = {p.key: p for p in result}

    assert by_key["amzn mktp us"].confidence == "low"
    assert by_key["grain cafe"].confidence == "low"
    assert by_key["sqsp inv"].confidence == "medium"  # untouched, was already valid


@pytest.mark.asyncio
async def test_merchant_omitted_by_the_model_is_never_dropped(monkeypatch):
    # The model only returns one of the three distinct merchants.
    fake = _PlanResponse(
        merchants=[
            MerchantPlan(
                key="amzn mktp us",
                display="AMZN MKTP US",
                needs_research=False,
                category="Shipping & Postage",
                confidence="high",
                reason="known brand",
            ),
        ]
    )

    async def fake_structured_completion(system, user, schema):
        return fake

    monkeypatch.setattr(planner_module, "structured_completion", fake_structured_completion)

    result = await plan_merchants(TXNS, "Categorize these transactions.")

    assert {p.key for p in result} == {"amzn mktp us", "grain cafe", "sqsp inv"}
    by_key = {p.key: p for p in result}
    for omitted_key in ("grain cafe", "sqsp inv"):
        plan = by_key[omitted_key]
        assert plan.needs_research is True
        assert plan.confidence == "low"
        assert plan.category in CATEGORIES


@pytest.mark.asyncio
async def test_total_llm_failure_routes_every_merchant_to_research_without_dropping(monkeypatch):
    # structured_completion returning None simulates the .parse() path AND
    # the JSON-mode fallback both failing (e.g. bad LLM_API_KEY, unreachable
    # LLM_BASE_URL, the demo's Cloudflare tunnel dropping).
    async def fake_structured_completion(system, user, schema):
        return None

    monkeypatch.setattr(planner_module, "structured_completion", fake_structured_completion)

    result = await plan_merchants(TXNS, "Categorize these transactions.")

    assert {p.key for p in result} == {"amzn mktp us", "grain cafe", "sqsp inv"}
    assert all(p.needs_research is True for p in result)
    assert all(p.confidence == "low" for p in result)
    assert all(p.category in CATEGORIES for p in result)
