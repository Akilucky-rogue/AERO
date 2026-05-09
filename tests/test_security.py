"""
tests/test_security.py — Security-focused unit tests.

Tests the formula injection sanitizer, path traversal guard,
and bcrypt-based password hashing introduced by the audit remediation.
Pure functions / no Streamlit, no network.
"""

import os
import pytest

from aero.data.excel_store import _sanitize_cell, _sanitize_df
from aero.data.station_store import _sanitize_cell as ss_sanitize_cell, _safe_path
from aero.auth.service import _hash_password, _verify_password, _needs_rehash

import pandas as pd


# ---------------------------------------------------------------------------
# Formula injection sanitizer — SEC-006
# ---------------------------------------------------------------------------

class TestSanitizeCell:

    @pytest.mark.parametrize("bad_char", ["=", "+", "-", "@", "|", "%"])
    def test_prefixes_formula_start_chars(self, bad_char):
        value = f"{bad_char}CMD()"
        result = _sanitize_cell(value)
        assert result.startswith("'")
        assert result == f"'{bad_char}CMD()"

    def test_safe_string_unchanged(self):
        assert _sanitize_cell("Station A") == "Station A"

    def test_empty_string_unchanged(self):
        assert _sanitize_cell("") == ""

    def test_none_unchanged(self):
        assert _sanitize_cell(None) is None

    def test_integer_unchanged(self):
        assert _sanitize_cell(42) == 42

    def test_float_unchanged(self):
        assert _sanitize_cell(3.14) == 3.14

    def test_normal_negative_number_string_not_found(self):
        # A string like "-5.0" starts with "-" — gets prefixed
        result = _sanitize_cell("-5.0")
        assert result == "'-5.0"

    # station_store uses its own copy — test it too
    def test_station_store_sanitizer(self):
        assert ss_sanitize_cell("=MALICIOUS()") == "'=MALICIOUS()"


class TestSanitizeDf:

    def test_dangerous_cells_in_object_columns_are_escaped(self):
        df = pd.DataFrame({
            "name": ["=FORMULA", "Normal", "+PLUS"],
            "value": [100, 200, 300],
        })
        result = _sanitize_df(df)
        assert result["name"].iloc[0] == "'=FORMULA"
        assert result["name"].iloc[1] == "Normal"
        assert result["name"].iloc[2] == "'+PLUS"
        # Numeric column untouched
        assert result["value"].tolist() == [100, 200, 300]

    def test_original_df_not_mutated(self):
        df = pd.DataFrame({"col": ["=BAD"]})
        _sanitize_df(df)
        assert df["col"].iloc[0] == "=BAD"


# ---------------------------------------------------------------------------
# Path traversal guard — SEC-007
# ---------------------------------------------------------------------------

class TestSafePath:

    def test_raises_on_traversal(self):
        from aero import DATA_DIR
        traversal = os.path.join(DATA_DIR, "..", "..", "etc", "passwd")
        with pytest.raises(ValueError, match="path traversal"):
            _safe_path(traversal)

    def test_accepts_valid_data_dir_path(self):
        from aero import DATA_DIR
        valid = os.path.join(DATA_DIR, "some_station.xlsx")
        # Should not raise
        result = _safe_path(valid)
        assert DATA_DIR in result


# ---------------------------------------------------------------------------
# Password hashing — SEC-003
# ---------------------------------------------------------------------------

class TestPasswordHashing:

    def test_hash_is_bcrypt_format(self):
        h = _hash_password("TestPassword123!")
        assert h.startswith("$2b$")

    def test_verify_correct_password(self):
        h = _hash_password("MySecurePass")
        assert _verify_password("MySecurePass", h) is True

    def test_reject_wrong_password(self):
        h = _hash_password("CorrectPass")
        assert _verify_password("WrongPass", h) is False

    def test_bcrypt_hash_not_needs_rehash(self):
        h = _hash_password("SomePassword")
        assert _needs_rehash(h) is False

    def test_legacy_sha256_needs_rehash(self):
        import hashlib
        legacy = hashlib.sha256(b"OldPassword").hexdigest()
        assert _needs_rehash(legacy) is True

    def test_legacy_sha256_still_verifies(self):
        # Ensure existing SHA-256 hashed users are not locked out during migration
        import hashlib
        plain = "LegacyPassword"
        legacy = hashlib.sha256(plain.encode()).hexdigest()
        assert _verify_password(plain, legacy) is True

    def test_unique_salts_produce_different_hashes(self):
        h1 = _hash_password("SamePassword")
        h2 = _hash_password("SamePassword")
        assert h1 != h2  # Different salts each time
