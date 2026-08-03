"""
Finance CSV import module.

Canonical CSV format expected by Chitiyu:
    date, amount, description, category, account
    2026-08-01, -45.00, Whole Foods, groceries, chase-checking

Rules:
- date: YYYY-MM-DD
- amount: negative = expense, positive = income
- description: merchant or description text
- category: one of the standard categories (or 'other' if blank)
- account: account name string (optional — creates account if not seen before)

Per-bank transforms live in transforms/<name>.json. Transform files are plain
JSON dicts mapping source column names → canonical column names. Keys that
start with '_' are metadata (description, source_columns) and are ignored.
"""
import csv
import io
import json
import sqlite3
from pathlib import Path

# Canonical column names (required subset)
_REQUIRED = {"date", "amount", "description"}
_OPTIONAL = {"category", "account"}
_ALL_CANONICAL = _REQUIRED | _OPTIONAL

# Path to transforms directory relative to chitiyu-pi project root
_TRANSFORMS_DIR = Path(__file__).parent.parent.parent.parent / "transforms"


def load_transform(name: str) -> dict[str, str]:
    """Load a bank transform JSON file by name (without .json extension).
    Returns a dict mapping source column name → canonical column name.
    Metadata keys (starting with '_') are excluded."""
    path = _TRANSFORMS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Transform '{name}' not found. Expected: {path}\n"
            f"Available: {[p.stem for p in _TRANSFORMS_DIR.glob('*.json')]}"
        )
    raw = json.loads(path.read_text())
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def apply_transform(row: dict, mapping: dict[str, str]) -> dict:
    """Apply a column name mapping to a single CSV row dict.
    Source column names are mapped to canonical names.
    Unmapped columns are dropped. Canonical columns already present are kept."""
    result: dict = {}
    # First pass: apply mapping
    for src_col, canonical_col in mapping.items():
        if src_col in row:
            result[canonical_col] = row[src_col]
    # Second pass: keep any canonical columns already in the row that weren't mapped
    for col in _ALL_CANONICAL:
        if col in row and col not in result:
            result[col] = row[col]
    return result


def _parse_amount(raw: str) -> float:
    """Parse a raw amount string to float. Handles '$', commas, parentheses for negatives."""
    s = raw.strip().replace(",", "").replace("$", "").replace(" ", "")
    if s.startswith("(") and s.endswith(")"):
        # Parentheses format for negatives: (45.00) → -45.00
        s = "-" + s[1:-1]
    return float(s)


def _parse_date(raw: str) -> str:
    """Normalize date strings to YYYY-MM-DD. Handles MM/DD/YYYY and YYYY-MM-DD."""
    s = raw.strip()
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 3:
            # MM/DD/YYYY or MM/DD/YY
            m, d, y = parts
            if len(y) == 2:
                y = "20" + y
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return s  # Already YYYY-MM-DD or will fail on insert


def import_csv_file(conn: sqlite3.Connection, user_id: int,
                    csv_text: str,
                    transform_name: str | None = None) -> tuple[int, list[str]]:
    """Import a CSV string into the transactions table.

    Args:
        conn: DB connection.
        user_id: Owning user.
        csv_text: Raw CSV content as string.
        transform_name: Optional name of a bank transform to apply first
                        (e.g. 'chase', 'apple-card').

    Returns:
        (imported_count, error_messages)
    """
    from domains.finance.db import get_account_by_name, insert_account, insert_transaction

    mapping: dict[str, str] = {}
    if transform_name:
        mapping = load_transform(transform_name)

    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    if reader.fieldnames is None:
        return 0, ["CSV appears empty or has no header row."]

    # Strip whitespace from field names (some bank exports add padding)
    reader.fieldnames = [f.strip() for f in reader.fieldnames]

    imported = 0
    errors: list[str] = []

    for i, raw_row in enumerate(reader, start=2):  # start=2 because row 1 is header
        # Strip whitespace from all values
        row = {k.strip(): v.strip() for k, v in raw_row.items() if k is not None}

        # Apply transform if provided
        if mapping:
            row = apply_transform(row, mapping)

        # Validate required fields
        missing = _REQUIRED - set(row.keys())
        if missing:
            errors.append(f"Row {i}: missing required columns: {missing}. Row: {row}")
            continue

        # Parse fields
        try:
            amount = _parse_amount(row["amount"])
        except (ValueError, KeyError) as e:
            errors.append(f"Row {i}: invalid amount '{row.get('amount')}': {e}")
            continue

        try:
            date = _parse_date(row["date"])
        except Exception as e:
            errors.append(f"Row {i}: invalid date '{row.get('date')}': {e}")
            continue

        description = row.get("description", "").strip()
        if not description:
            errors.append(f"Row {i}: description is empty.")
            continue

        category = (row.get("category") or "other").strip().lower()
        account_name = row.get("account", "").strip()

        # Resolve account_id if account name was provided
        account_id: int | None = None
        if account_name:
            acct = get_account_by_name(conn, user_id, account_name)
            if acct:
                account_id = acct["id"]
            else:
                # Auto-create account as 'checking' (user can update type later)
                account_id = insert_account(conn, user_id, account_name, "checking")

        try:
            insert_transaction(conn, user_id, date, amount, category,
                               description, source="csv", account_id=account_id)
            imported += 1
        except Exception as e:
            errors.append(f"Row {i}: DB insert failed: {e}")

    return imported, errors
