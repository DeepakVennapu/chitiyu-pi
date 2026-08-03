"""
Tests for finance CSV import module.
"""
import json
import os
import pytest
from pathlib import Path

from domains.finance.csv_import import (
    apply_transform,
    import_csv_file,
    load_transform,
    _parse_amount,
    _parse_date,
)
from domains.finance.db import list_transactions


# ── Unit tests for helpers ─────────────────────────────────────────────────────

def test_parse_amount_negative():
    assert _parse_amount("-45.00") == pytest.approx(-45.00)


def test_parse_amount_with_dollar_sign():
    assert _parse_amount("$45.00") == pytest.approx(45.00)


def test_parse_amount_with_comma():
    assert _parse_amount("1,200.50") == pytest.approx(1200.50)


def test_parse_amount_parentheses_negative():
    assert _parse_amount("(45.00)") == pytest.approx(-45.00)


def test_parse_date_iso():
    assert _parse_date("2026-08-01") == "2026-08-01"


def test_parse_date_slash_us():
    assert _parse_date("08/01/2026") == "2026-08-01"


def test_parse_date_slash_short_year():
    assert _parse_date("08/01/26") == "2026-08-01"


# ── apply_transform ────────────────────────────────────────────────────────────

def test_apply_transform_renames_columns():
    mapping = {"Transaction Date": "date", "Amount": "amount", "Description": "description"}
    row = {"Transaction Date": "2026-08-01", "Amount": "-45.00",
           "Description": "Whole Foods", "Post Date": "2026-08-02"}
    result = apply_transform(row, mapping)
    assert result["date"] == "2026-08-01"
    assert result["amount"] == "-45.00"
    assert result["description"] == "Whole Foods"
    assert "Post Date" not in result  # unmapped columns are dropped


def test_apply_transform_preserves_existing_canonical():
    mapping = {"Transaction Date": "date"}
    row = {"Transaction Date": "2026-08-01", "amount": "-45.00", "description": "Test"}
    result = apply_transform(row, mapping)
    assert result["date"] == "2026-08-01"
    assert result["amount"] == "-45.00"   # kept from original row


def test_apply_transform_merchant_wins_over_description():
    """Apple Card: Merchant column should override Description when both are mapped."""
    mapping = {
        "Transaction Date": "date",
        "Description": "description",
        "Merchant": "description",   # maps last — overrides
        "Amount (USD)": "amount",
    }
    row = {
        "Transaction Date": "2026-08-01",
        "Description": "APPLE.COM/BILL",
        "Merchant": "Apple",
        "Amount (USD)": "-9.99",
    }
    result = apply_transform(row, mapping)
    assert result["description"] == "Apple"


# ── load_transform ─────────────────────────────────────────────────────────────

def test_load_transform_chase():
    """Chase transform file must exist and map the expected columns."""
    mapping = load_transform("chase")
    assert "Transaction Date" in mapping
    assert mapping["Transaction Date"] == "date"
    assert "Amount" in mapping
    assert mapping["Amount"] == "amount"
    assert "Description" in mapping


def test_load_transform_apple_card():
    """Apple Card transform file must exist and map the expected columns."""
    mapping = load_transform("apple-card")
    assert "Transaction Date" in mapping
    assert mapping["Transaction Date"] == "date"
    assert "Amount (USD)" in mapping
    assert mapping["Amount (USD)"] == "amount"


def test_load_transform_nonexistent():
    with pytest.raises(FileNotFoundError, match="not found"):
        load_transform("nonexistent-bank-xyz")


# ── import_csv_file ────────────────────────────────────────────────────────────

CANONICAL_CSV = """\
date,amount,description,category,account
2026-08-01,-45.00,Whole Foods,groceries,chase-checking
2026-08-02,-30.00,Chick-fil-A,dining,chase-checking
2026-08-15,2000.00,Paycheck,income,chase-checking
"""


def test_import_canonical_csv(conn, user_id):
    count, errors = import_csv_file(conn, user_id, CANONICAL_CSV)
    assert errors == []
    assert count == 3
    txns = list_transactions(conn, user_id)
    assert len(txns) == 3
    descriptions = {t["description"] for t in txns}
    assert "Whole Foods" in descriptions
    assert "Paycheck" in descriptions


def test_import_canonical_csv_amounts(conn, user_id):
    import_csv_file(conn, user_id, CANONICAL_CSV)
    txns = list_transactions(conn, user_id)
    amounts = {t["description"]: t["amount"] for t in txns}
    assert amounts["Whole Foods"] == pytest.approx(-45.00)
    assert amounts["Paycheck"] == pytest.approx(2000.00)


def test_import_canonical_csv_creates_account(conn, user_id):
    import_csv_file(conn, user_id, CANONICAL_CSV)
    from domains.finance.db import get_account_by_name
    acct = get_account_by_name(conn, user_id, "chase-checking")
    assert acct is not None


def test_import_csv_with_chase_transform(conn, user_id):
    chase_csv = """\
Transaction Date,Post Date,Description,Category,Type,Amount,Memo
08/01/2026,08/02/2026,WHOLEFDS #123,Groceries,Sale,-45.00,
08/02/2026,08/03/2026,CHICK-FIL-A,Food & Drink,Sale,-12.50,
"""
    count, errors = import_csv_file(conn, user_id, chase_csv, transform_name="chase")
    assert errors == []
    assert count == 2
    txns = list_transactions(conn, user_id)
    descriptions = {t["description"] for t in txns}
    assert "WHOLEFDS #123" in descriptions


def test_import_csv_with_apple_card_transform(conn, user_id):
    apple_csv = """\
Transaction Date,Clearing Date,Description,Merchant,Category,Type,Amount (USD)
08/01/2026,08/02/2026,WHOLE FOODS,Whole Foods Market,Groceries,Purchase,-45.00
08/03/2026,08/04/2026,NETFLIX.COM,Netflix,Entertainment,Purchase,-15.49
"""
    count, errors = import_csv_file(conn, user_id, apple_csv, transform_name="apple-card")
    assert errors == []
    assert count == 2
    txns = list_transactions(conn, user_id)
    descriptions = {t["description"] for t in txns}
    # Merchant column wins over Description for Apple Card
    assert "Whole Foods Market" in descriptions or "WHOLE FOODS" in descriptions


def test_import_csv_missing_required_field(conn, user_id):
    bad_csv = """\
date,category,account
2026-08-01,groceries,chase-checking
"""
    count, errors = import_csv_file(conn, user_id, bad_csv)
    assert count == 0
    assert len(errors) == 1
    assert "missing required columns" in errors[0]


def test_import_csv_bad_amount(conn, user_id):
    bad_csv = """\
date,amount,description,category
2026-08-01,not-a-number,Whole Foods,groceries
"""
    count, errors = import_csv_file(conn, user_id, bad_csv)
    assert count == 0
    assert len(errors) == 1
    assert "invalid amount" in errors[0]


def test_import_csv_empty_description(conn, user_id):
    bad_csv = """\
date,amount,description,category
2026-08-01,-45.00,,groceries
"""
    count, errors = import_csv_file(conn, user_id, bad_csv)
    assert count == 0
    assert "description is empty" in errors[0]


def test_import_csv_partial_errors(conn, user_id):
    mixed_csv = """\
date,amount,description,category
2026-08-01,-45.00,Whole Foods,groceries
2026-08-02,bad,Trader Joe's,groceries
2026-08-03,-30.00,Chick-fil-A,dining
"""
    count, errors = import_csv_file(conn, user_id, mixed_csv)
    assert count == 2
    assert len(errors) == 1
    assert "invalid amount" in errors[0]


def test_import_csv_user_isolation(conn):
    import_csv_file(conn, 1, CANONICAL_CSV)
    txns = list_transactions(conn, 2)
    assert txns == []
