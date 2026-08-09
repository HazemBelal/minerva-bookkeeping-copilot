from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from itertools import combinations
from typing import Any

DUPLICATE_WINDOW_DAYS = 2
ROUND_AMOUNT_FLOOR = 500.0
SAME_DAY_REPEAT_THRESHOLD = 3

FLAG_LABELS = {
    "duplicate_charge": "Possible duplicate charge",
    "repeat_merchant_same_day": "Several charges from one merchant on one day",
    "round_amount": "Large round-number amount",
    "unidentified_merchant": "Merchant could not be identified",
}


@dataclass
class Flag:
    code: str
    row_ids: list[int]
    detail: str


def _parse_date(value: str) -> date | None:
    try:
        year, month, day = (int(part) for part in value.split("-"))
        return date(year, month, day)
    except (ValueError, AttributeError):
        return None


def find_anomalies(rows: list[dict[str, Any]]) -> list[Flag]:
    """Deterministic anomaly detection.

    Deliberately not an LLM call. A hallucinated fraud flag in an accounting
    product is worse than no flag at all, so every rule here is explicit,
    inspectable, and reproducible.
    """
    flags: list[Flag] = []

    for a, b in combinations(rows, 2):
        if a["merchant_key"] != b["merchant_key"] or a["amount"] != b["amount"]:
            continue
        da, db = _parse_date(a.get("date", "")), _parse_date(b.get("date", ""))
        if da is None or db is None:
            continue
        if abs((da - db).days) <= DUPLICATE_WINDOW_DAYS:
            flags.append(
                Flag(
                    "duplicate_charge",
                    [a["id"], b["id"]],
                    f"{a['amount']:.2f} charged twice within {DUPLICATE_WINDOW_DAYS} days",
                )
            )

    by_merchant_day: dict[tuple[str, str], list[int]] = defaultdict(list)
    for row in rows:
        if row.get("date"):
            by_merchant_day[(row["merchant_key"], row["date"])].append(row["id"])
    for (merchant, day), ids in by_merchant_day.items():
        if len(ids) >= SAME_DAY_REPEAT_THRESHOLD:
            flags.append(
                Flag(
                    "repeat_merchant_same_day",
                    sorted(ids),
                    f"{len(ids)} charges from {merchant} on {day}",
                )
            )

    for row in rows:
        amount = abs(row.get("amount") or 0.0)
        # "Round" = a whole-dollar amount (no cents) at/above the floor.
        # NOTE: the brief's sample used `amount % 100 == 0`, but that fails
        # the brief's own test (-1250.00 is not a multiple of 100). See
        # task-8a-report.md self-review for the deviation rationale.
        is_whole_dollar = abs(amount - round(amount)) < 1e-9
        if amount >= ROUND_AMOUNT_FLOOR and is_whole_dollar:
            flags.append(
                Flag("round_amount", [row["id"]], f"Exactly {amount:.2f}")
            )
        if row.get("status") == "needs_review":
            flags.append(
                Flag(
                    "unidentified_merchant",
                    [row["id"]],
                    "The agent could not verify this merchant",
                )
            )

    return flags
