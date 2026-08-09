from __future__ import annotations

import re
from dataclasses import dataclass

# Payment processors and card networks that prefix the real merchant name.
_PROCESSOR_PREFIXES = (
    "sq", "tst", "sp", "paddlenet", "paypal", "pp", "pos", "posdebit",
    "debitcard", "checkcard", "visa", "mc", "ach", "recur", "web",
)
_NOISE_WORDS = {"inc", "llc", "ltd", "co", "corp", "the", "com", "net", "www", "http", "https"}

_DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), lambda m: f"{m[1]}-{m[2]}-{m[3]}"),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"), lambda m: f"{m[3]}-{int(m[1]):02d}-{int(m[2]):02d}"),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2})\b"), lambda m: f"20{m[3]}-{int(m[1]):02d}-{int(m[2]):02d}"),
]

_AMOUNT_TOKEN_RE = re.compile(r"\(?-?[$€£]?\s?-?\d[\d,]*\.\d{2}\)?-?")


@dataclass
class Txn:
    id: int
    date: str
    description: str
    amount: float
    merchant_key: str


def merchant_key(description: str) -> str:
    """Collapse a noisy bank descriptor to a stable research key.

    'AMZN MKTP US*2K4L9RT31' and 'AMZN MKTP US' must produce the same key so
    the agent researches that merchant once rather than once per row.
    """
    text = description.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [t for t in text.split() if t]

    if tokens and tokens[0] in _PROCESSOR_PREFIXES:
        tokens = tokens[1:]

    cleaned: list[str] = []
    for token in tokens:
        if token in _NOISE_WORDS:
            continue
        if any(ch.isdigit() for ch in token):
            continue  # store numbers, invoice ids, auth codes
        cleaned.append(token)

    return " ".join(cleaned[:3]) or re.sub(r"[^a-z0-9]+", " ", description.lower()).strip()


def _extract_date(line: str) -> tuple[str, str]:
    for pattern, fmt in _DATE_PATTERNS:
        match = pattern.search(line)
        if match:
            return fmt(match), line.replace(match.group(0), " ", 1)
    return "", line


def _extract_amount(text: str) -> tuple[float, str]:
    # Search the whole remainder for an amount token rather than splitting on
    # commas first: a thousands separator inside "$1,250.00" must stay glued
    # to its number instead of being cut apart by a naive column split.
    matches = list(_AMOUNT_TOKEN_RE.finditer(text))
    if not matches:
        return 0.0, re.sub(r"[,\t;|]+", " ", text)

    match = matches[-1]
    candidate = match.group(0)
    negative = candidate.startswith("(") or "-" in candidate
    digits = re.sub(r"[^\d.]", "", candidate)
    try:
        value = float(digits)
    except ValueError:
        return 0.0, re.sub(r"[,\t;|]+", " ", text)

    remainder = text[: match.start()] + text[match.end() :]
    remainder = re.sub(r"[,\t;|]+", " ", remainder)
    return (-value if negative else value), remainder


def parse_statement(text: str) -> list[Txn]:
    txns: list[Txn] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^\s*date\b", line, flags=re.I) and "amount" in line.lower():
            continue  # header row
        date, rest = _extract_date(line)
        amount, description = _extract_amount(rest)
        description = re.sub(r"\s{2,}", " ", description).strip(" ,\t")
        if not description:
            continue
        txns.append(
            Txn(
                id=len(txns),
                date=date,
                description=description,
                amount=amount,
                merchant_key=merchant_key(description),
            )
        )
    return txns
