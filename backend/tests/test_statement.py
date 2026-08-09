from app.statement import Txn, merchant_key, parse_statement


def test_parses_iso_date_comma_format():
    txns = parse_statement("2026-07-02, SQSP* INV 8823941, -18.00")
    assert txns == [
        Txn(id=0, date="2026-07-02", description="SQSP* INV 8823941",
            amount=-18.00, merchant_key=txns[0].merchant_key)
    ]


def test_parses_us_slash_dates_and_tab_separators():
    txns = parse_statement("07/03/2026\tAMZN MKTP US*2K4L9\t42.19")
    assert txns[0].date == "2026-07-03"
    assert txns[0].amount == 42.19


def test_parses_currency_symbols_parens_and_thousands():
    txns = parse_statement("2026-07-06, RAMP* CARD PAYMENT, ($1,250.00)")
    assert txns[0].amount == -1250.00


def test_skips_blank_lines_and_a_header_row():
    text = "Date,Description,Amount\n\n2026-07-02, SQSP* INV, -18.00\n"
    assert len(parse_statement(text)) == 1


def test_assigns_sequential_ids():
    text = "2026-07-02, A CO, -1.00\n2026-07-03, B CO, -2.00"
    assert [t.id for t in parse_statement(text)] == [0, 1]


def test_unparseable_line_is_kept_with_a_zero_amount_not_dropped():
    txns = parse_statement("total for the month was large")
    assert len(txns) == 1
    assert txns[0].amount == 0.0
    assert txns[0].date == ""


def test_merchant_key_collapses_processor_prefixes_and_trailing_ids():
    assert merchant_key("AMZN MKTP US*2K4L9RT31") == merchant_key("AMZN MKTP US")
    assert merchant_key("TST* GRAIN CAFE 4471") == merchant_key("TST*GRAIN CAFE")
    assert merchant_key("SQ *BLUE BOTTLE") == merchant_key("SQ*BLUE BOTTLE 992")


def test_merchant_key_keeps_genuinely_different_merchants_apart():
    assert merchant_key("SQSP* INV") != merchant_key("STRIPE TRANSFER")


def test_merchant_key_only_strips_starred_processor_prefixes():
    # A bare generic-prefix word with no "*" pattern is a real merchant name
    # (e.g. McDonald's), not a processor prefix -- must not be stripped down
    # to just "donalds".
    assert "mc" in merchant_key("MC DONALDS 4471").split()
    # A genuinely starred processor prefix still strips as before.
    assert "sq" not in merchant_key("SQ*BLUE BOTTLE").split()


def test_merchant_key_is_lowercase_and_has_no_punctuation():
    key = merchant_key("PADDLE.NET* FIGMA")
    assert key == key.lower()
    assert all(c.isalnum() or c == " " for c in key)
