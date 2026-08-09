from app.anomalies import find_anomalies


def row(id, date, key, amount, status="done"):
    return {
        "id": id, "date": date, "merchant_key": key,
        "amount": amount, "status": status,
    }


def codes(rows):
    return {f.code for f in find_anomalies(rows)}


def test_flags_identical_charges_within_two_days():
    rows = [row(0, "2026-07-03", "amzn", -42.19), row(1, "2026-07-04", "amzn", -42.19)]
    flags = find_anomalies(rows)
    assert [f.code for f in flags] == ["duplicate_charge"]
    assert sorted(flags[0].row_ids) == [0, 1]


def test_does_not_flag_identical_charges_far_apart():
    rows = [row(0, "2026-07-03", "amzn", -42.19), row(1, "2026-07-28", "amzn", -42.19)]
    assert "duplicate_charge" not in codes(rows)


def test_does_not_flag_same_merchant_with_different_amounts():
    rows = [row(0, "2026-07-03", "amzn", -42.19), row(1, "2026-07-03", "amzn", -11.00)]
    assert "duplicate_charge" not in codes(rows)


def test_flags_three_or_more_charges_from_one_merchant_on_one_day():
    rows = [row(i, "2026-07-03", "uber eats", -10.0 - i) for i in range(3)]
    assert "repeat_merchant_same_day" in codes(rows)


def test_flags_large_round_amounts():
    assert "round_amount" in codes([row(0, "2026-07-06", "ramp card payment", -1250.00)])
    assert "round_amount" not in codes([row(0, "2026-07-06", "ramp", -1250.37)])
    assert "round_amount" not in codes([row(0, "2026-07-06", "ramp", -300.00)])


def test_flags_rows_the_agent_could_not_identify():
    rows = [row(0, "2026-07-06", "sp cordless desk", -412.00, status="needs_review")]
    assert "unidentified_merchant" in codes(rows)


def test_clean_statement_produces_no_flags():
    rows = [row(0, "2026-07-02", "sqsp", -18.00), row(1, "2026-07-05", "grain cafe", -63.40)]
    assert find_anomalies(rows) == []


def test_rows_without_dates_do_not_crash_the_pass():
    rows = [row(0, "", "amzn", -42.19), row(1, "", "amzn", -42.19)]
    find_anomalies(rows)
