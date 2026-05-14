"""
AERO Authentication Service.

Manages user authentication against an Excel-based credential store.
Supports five roles: Facility, Gateway, Services, Leadership, Operations.

Security notes
--------------
* Passwords are hashed with bcrypt (per-user salt, work factor 12).
* Legacy SHA-256 hashes are accepted on login and transparently upgraded
  to bcrypt so existing users are never locked out.
* First-run credential seeding reads from environment variables only —
  no credentials are stored in source code.
"""

import logging
import os

import bcrypt  # type: ignore
import pandas as pd
import streamlit as st

from aero import DATA_DIR

logger = logging.getLogger(__name__)

USERS_DB_PATH = os.path.join(DATA_DIR, "AERO_USERS.xlsx")

VALID_ROLES: set[str] = {"Facility", "Gateway", "Services", "Leadership", "Operations"}


# ---------------------------------------------------------------------------
# Password hashing — bcrypt with per-user salt (SEC-003)
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    """Return a bcrypt hash string for *password*."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, stored: str) -> bool:
    """Verify *plain* against *stored* hash.

    Supports both new bcrypt hashes ($2b$/$2a$/$2y$) and legacy SHA-256
    hashes (64-char hex strings) so existing users are not locked out.
    A SHA-256 match triggers a transparent re-hash on the next write.
    """
    # --- bcrypt path (new standard) ---
    if stored.startswith(("$2b$", "$2a$", "$2y$")):
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False

    # --- legacy SHA-256 path ---
    import hashlib
    legacy_hash = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    return legacy_hash == stored


def _needs_rehash(stored: str) -> bool:
    """Return True if *stored* is a legacy SHA-256 hash that needs upgrading."""
    return not stored.startswith(("$2b$", "$2a$", "$2y$"))


# ---------------------------------------------------------------------------
# First-run user seeding from environment variables (SEC-001)
# ---------------------------------------------------------------------------

def seed_users() -> None:
    """Create AERO_USERS.xlsx from environment variables if it does not exist.

    Reads up to 10 user slots.  Each slot uses:
        AERO_SEED_USER_<N>_ID    — login user ID   (required)
        AERO_SEED_USER_<N>_PASS  — plaintext pass  (required)
        AERO_SEED_USER_<N>_ROLE  — role string     (required, must be in VALID_ROLES)
        AERO_SEED_USER_<N>_NAME  — display name    (optional, defaults to user ID)

    If no seed variables are set, seeding is silently skipped (app runs in
    zero-user mode until an admin creates AERO_USERS.xlsx manually).
    If AERO_USERS.xlsx already exists this function is a no-op.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(USERS_DB_PATH):
        return

    rows = []
    for n in range(1, 11):
        uid  = os.getenv(f"AERO_SEED_USER_{n}_ID",   "").strip()
        pwd  = os.getenv(f"AERO_SEED_USER_{n}_PASS", "").strip()
        role = os.getenv(f"AERO_SEED_USER_{n}_ROLE", "").strip()
        name = os.getenv(f"AERO_SEED_USER_{n}_NAME", uid).strip()

        if not uid or not pwd or not role:
            continue
        if role not in VALID_ROLES:
            logger.warning(
                "seed_users: unknown role '%s' for user '%s', skipping.", role, uid
            )
            continue

        rows.append({
            "user_id":       uid,
            "display_name":  name or uid,
            "role":          role,
            "password_hash": _hash_password(pwd),
            "is_active":     True,
        })

    if not rows:
        logger.info(
            "seed_users: no AERO_SEED_USER_* env variables found; "
            "skipping automatic seed.  Create data/AERO_USERS.xlsx manually "
            "or set AERO_SEED_USER_1_ID / _PASS / _ROLE in .env."
        )
        return

    try:
        df = pd.DataFrame(rows)
        # Ensure proper data types
        df["user_id"] = df["user_id"].astype(str)
        df["display_name"] = df["display_name"].astype(str)
        df["role"] = df["role"].astype(str)
        df["password_hash"] = df["password_hash"].astype(str)
        df["is_active"] = df["is_active"].astype(bool)
        
        df.to_excel(USERS_DB_PATH, index=False, sheet_name="Users")
        logger.info("seed_users: created %s with %d user(s).", USERS_DB_PATH, len(rows))
    except Exception as exc:
        logger.error("seed_users: failed to create AERO_USERS.xlsx: %s", exc)
        raise


# ---------------------------------------------------------------------------
# User management  (create / update users at runtime)
# ---------------------------------------------------------------------------

def upsert_user(
    user_id: str,
    password: str,
    role: str,
    display_name: str = "",
) -> tuple[bool, str]:
    """Create or update a user record in AERO_USERS.xlsx.

    Returns ``(True, message)`` on success, ``(False, error_message)`` on failure.
    Existing records are matched on *user_id* — all fields are updated when a
    match is found. A new row is appended when no match exists.
    """
    user_id = user_id.strip()
    password = password.strip()
    role = role.strip()
    display_name = (display_name.strip() or user_id)

    if not user_id:
        return False, "User ID must not be empty."
    if not password:
        return False, "Password must not be empty."
    if role not in VALID_ROLES:
        return False, f"Role '{role}' is not valid. Choose from: {sorted(VALID_ROLES)}."

    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(USERS_DB_PATH):
            df = pd.read_excel(USERS_DB_PATH, sheet_name="Users")
            # Ensure proper data types on read
            df = df.astype(str).map(lambda x: x.strip() if isinstance(x, str) else x)
        else:
            df = pd.DataFrame(
                columns=["user_id", "display_name", "role", "password_hash", "is_active"]
            )

        hashed = _hash_password(password)

        # Case-insensitive lookup
        user_id_lower = user_id.lower()
        existing_match = df[df["user_id"].str.lower() == user_id_lower]
        
        if not existing_match.empty:
            mask = df["user_id"].str.lower() == user_id_lower
            df.loc[mask, "user_id"]       = user_id
            df.loc[mask, "display_name"]  = display_name
            df.loc[mask, "role"]          = role
            df.loc[mask, "password_hash"] = hashed
            df.loc[mask, "is_active"]     = True
            action = "updated"
        else:
            new_row = pd.DataFrame([{
                "user_id":       user_id,
                "display_name":  display_name,
                "role":          role,
                "password_hash": hashed,
                "is_active":     True,
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            action = "created"

        # Ensure proper data types before writing
        df["user_id"] = df["user_id"].astype(str)
        df["display_name"] = df["display_name"].astype(str)
        df["role"] = df["role"].astype(str)
        df["password_hash"] = df["password_hash"].astype(str)
        df["is_active"] = df["is_active"].astype(bool)
        
        df.to_excel(USERS_DB_PATH, index=False, sheet_name="Users")
        logger.info("upsert_user: %s user '%s' with role '%s'.", action, user_id, role)
        return True, f"User '{user_id}' {action} successfully with role '{role}'."

    except Exception as exc:
        logger.exception("upsert_user failed: %s", exc)
        return False, f"Failed to save user: {exc}"


def list_users() -> pd.DataFrame:
    """Return the users dataframe (without password hashes) for admin display."""
    if not os.path.exists(USERS_DB_PATH):
        return pd.DataFrame(columns=["user_id", "display_name", "role", "is_active"])
    try:
        df = pd.read_excel(USERS_DB_PATH, sheet_name="Users")
        return df.drop(columns=["password_hash"], errors="ignore")
    except Exception as exc:
        logger.warning("list_users: %s", exc)
        return pd.DataFrame(columns=["user_id", "display_name", "role", "is_active"])


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate(user_id: str, password: str) -> dict | None:
    """Validate credentials. Returns a user dict on success, None on failure."""
    seed_users()

    try:
        df = pd.read_excel(USERS_DB_PATH, sheet_name="Users")
    except Exception as exc:
        logger.error("authenticate: failed to read users file: %s", exc)
        return None

    if df.empty:
        logger.warning("authenticate: AERO_USERS.xlsx is empty")
        return None

    # Ensure all columns are strings and stripped of whitespace
    df = df.astype(str).applymap(lambda x: x.strip() if isinstance(x, str) else x)
    
    # Case-insensitive user lookup
    user_id_clean = user_id.strip().lower()
    match = df[df["user_id"].str.lower() == user_id_clean]
    
    if match.empty:
        logger.debug("authenticate: user '%s' not found in AERO_USERS.xlsx", user_id)
        return None

    row = match.iloc[0]

    # Check if user is active
    is_active = row.get("is_active", "True")
    if isinstance(is_active, str):
        is_active = is_active.lower() in ("true", "1", "yes")
    
    if not is_active:
        logger.warning("authenticate: user '%s' is not active", user_id)
        return None

    stored_hash = str(row.get("password_hash", "")).strip()
    if not stored_hash:
        logger.error("authenticate: user '%s' has no password hash", user_id)
        return None

    # Verify password
    if not _verify_password(password, stored_hash):
        logger.warning("authenticate: invalid password for user '%s'", user_id)
        return None

    # Transparently upgrade legacy SHA-256 hash to bcrypt on successful login
    if _needs_rehash(stored_hash):
        _upgrade_password_hash(row["user_id"], password, df)

    logger.info("authenticate: successful login for user '%s' (role: %s)", 
                row.get("user_id"), row.get("role"))
    
    return {
        "user_id":      str(row.get("user_id", "")).strip(),
        "display_name": str(row.get("display_name", "")).strip(),
        "role":         str(row.get("role", "")).strip(),
    }


def _upgrade_password_hash(user_id: str, plain_password: str, df: pd.DataFrame) -> None:
    """Re-hash a legacy SHA-256 password to bcrypt and persist to disk."""
    try:
        mask = df["user_id"].str.strip().str.lower() == user_id.strip().lower()
        df.loc[mask, "password_hash"] = _hash_password(plain_password)
        df.to_excel(USERS_DB_PATH, index=False, sheet_name="Users")
        logger.info(
            "_upgrade_password_hash: upgraded hash for user '%s' to bcrypt.", user_id
        )
    except Exception as exc:
        logger.warning(
            "_upgrade_password_hash: could not upgrade hash for '%s': %s", user_id, exc
        )


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def login_user(user: dict) -> None:
    st.session_state["aero_authenticated"] = True
    st.session_state["aero_user"] = user


def logout_user() -> None:
    st.session_state["aero_authenticated"] = False
    st.session_state.pop("aero_user", None)


def get_current_user() -> dict | None:
    if st.session_state.get("aero_authenticated"):
        return st.session_state.get("aero_user")
    return None


def is_authenticated() -> bool:
    return st.session_state.get("aero_authenticated", False)


def require_role(*allowed_roles: str) -> dict:
    user = get_current_user()
    if user is None or user.get("role") not in allowed_roles:
        st.error("Access denied. You do not have permission to view this page.")
        st.stop()
    return user
