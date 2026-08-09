from __future__ import annotations

from pydantic import BaseModel

from .categories import CATEGORIES, normalize_category
from .llm import structured_completion
from .statement import Txn

SYSTEM_PROMPT = """You are a senior bookkeeper triaging a bank statement.

For each distinct merchant key you are given, decide ONE of:
  - needs_research = false: you recognise this merchant with high confidence
    from general knowledge (large, unambiguous brands such as Amazon, Uber,
    Stripe, Google). Give the category and a one-line reason.
  - needs_research = true: the descriptor is ambiguous, obscure, or you are
    not confident. A browser agent will look it up.

A descriptor that is abbreviated, truncated, or carries a billing/processor
code (e.g. "sqsp", "sp", "amzn", "tst", store numbers, invoice IDs) must be
needs_research = true even if you believe you can decode which brand it
refers to -- confirm it by research rather than pattern-matching the
abbreviation. Reserve needs_research = false only for descriptors that spell
out a globally-recognized brand name in full (e.g. "GOOGLE", "UBER",
"STARBUCKS").

Prefer needs_research = true when you are unsure. A wrong confident answer is
far worse than a slower correct one.

Choose category ONLY from this list:
{categories}

Set confidence to exactly one of: high, medium, low.
"""


class MerchantPlan(BaseModel):
    key: str
    display: str
    needs_research: bool
    category: str
    confidence: str
    reason: str


class _PlanResponse(BaseModel):
    merchants: list[MerchantPlan]


async def plan_merchants(txns: list[Txn], goal: str) -> list[MerchantPlan]:
    seen: dict[str, str] = {}
    for txn in txns:
        seen.setdefault(txn.merchant_key, txn.description)

    listing = "\n".join(f"- key={k!r} example_descriptor={v!r}" for k, v in seen.items())

    parsed = await structured_completion(
        system=SYSTEM_PROMPT.format(categories="\n".join(CATEGORIES)),
        user=f"User goal: {goal}\n\nDistinct merchant keys:\n{listing}",
        schema=_PlanResponse,
    )
    plans = parsed.merchants if parsed else []

    by_key = {p.key: p for p in plans}
    result: list[MerchantPlan] = []
    for key, example in seen.items():
        plan = by_key.get(key)
        if plan is None:
            # The model omitted a merchant. Do not silently drop the row.
            result.append(
                MerchantPlan(
                    key=key,
                    display=example,
                    needs_research=True,
                    category="Uncategorized",
                    confidence="low",
                    reason="Planner did not return this merchant, routing to research",
                )
            )
            continue
        plan.category = normalize_category(plan.category)
        if plan.confidence not in {"high", "medium", "low"}:
            plan.confidence = "low"
        result.append(plan)
    return result
