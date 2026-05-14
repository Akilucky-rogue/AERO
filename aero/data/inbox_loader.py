"""
inbox_loader.py — Auto-loads files dropped into aero/data/inbox/ subdirectories.

Folder layout on the server (Windows):
    aero/data/inbox/
        famis/       ← FAMIS REPORT_WE_*.xlsx  (drop here weekly)
        nsl/         ← IN Outbound/Inbound *.txt / *.csv files
        scorecard/   ← MD Scorecard *.xlsb files
        processed/
            famis/
            nsl/
            scorecard/

The app scans these folders on startup. New files are processed
automatically and moved to processed/. No UI upload required.
"""
import os
import shutil
import glob
import logging
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)

_DATA_DIR  = os.path.dirname(os.path.abspath(__file__))
_INBOX_ROOT = os.path.join(_DATA_DIR, "inbox")

# ── Column normalization helpers ───────────────────────────────────────────────
_SKIP_SHEETS = {"india summary view", "in summary graph", "summary", "graph"}

def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase + underscore column names; strip noise chars."""
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"[#%]", "", regex=True)
        .str.replace(r"[\s/\\]+", "_", regex=True)
        .str.replace(r"_+", "_", regex=True)
        .str.strip("_")
    )
    return df


# ── Allowed FAMIS columns (canonical → display) ────────────────────────────────
FAMIS_ALLOWED = {
    "date", "loc_id", "pk_gross_tot", "pk_gross_inb", "pk_gross_outb",
    "pk_oda", "pk_opa", "pk_roc", "fte_tot", "st_cr_or", "pk_fte", "pk_cr_or",
}
FAMIS_REQUIRED = {"date", "loc_id", "pk_gross_tot"}

# Extra aliases that appear in some weekly sheets
_COL_ALIAS = {
    "loc_nbr":        None,   # drop
    "type":           None,   # drop
    "pk_gross_outb":  "pk_gross_outb",
    "fte_tot_":       "fte_tot",   # "FTE TOT #" → after # removal → "fte_tot_"
    "fte_tot":        "fte_tot",
}


# ── Directory helpers ─────────────────────────────────────────────────────────
def _inbox(*parts) -> str:
    return os.path.join(_INBOX_ROOT, *parts)


def _processed(*parts) -> str:
    return os.path.join(_INBOX_ROOT, "processed", *parts)


def ensure_inbox_dirs() -> None:
    for sub in ["famis", "nsl", "scorecard",
                os.path.join("processed", "famis"),
                os.path.join("processed", "nsl"),
                os.path.join("processed", "scorecard")]:
        os.makedirs(_inbox(sub), exist_ok=True)


def _list_inbox(subfolder: str, *extensions) -> list:
    """Return files in inbox/subfolder matching extensions, newest first."""
    paths = []
    for ext in extensions:
        paths.extend(glob.glob(_inbox(subfolder, f"*{ext}")))
    return sorted(paths, key=os.path.getmtime, reverse=True)


def _move_processed(path: str, subfolder: str) -> str:
    dst_dir = _processed(subfolder)
    os.makedirs(dst_dir, exist_ok=True)
    base, ext = os.path.splitext(os.path.basename(path))
    dst = os.path.join(dst_dir, f"{base}{ext}")
    if os.path.exists(dst):
        dst = os.path.join(dst_dir, f"{base}_{datetime.now():%Y%m%d_%H%M%S}{ext}")
    shutil.move(path, dst)
    logger.info("Moved %s → %s", path, dst)
    return dst


# ── FAMIS parser ──────────────────────────────────────────────────────────────
def parse_famis_file(path_or_bytes) -> pd.DataFrame:
    """
    Parse a FAMIS REPORT xlsx.
    Reads ALL sheets, discards summary/graph sheets, normalises columns,
    and concatenates all sheets that have the required DATE/LOC_ID/PK_GROSS_TOT columns.
    Returns a clean DataFrame or raises ValueError.
    """
    if isinstance(path_or_bytes, (str, os.PathLike)):
        all_sheets = pd.read_excel(path_or_bytes, sheet_name=None)
    else:
        import io
        all_sheets = pd.read_excel(io.BytesIO(path_or_bytes), sheet_name=None)

    valid_dfs = []
    for sheet_name, raw in all_sheets.items():
        if sheet_name.strip().lower() in _SKIP_SHEETS:
            continue
        if raw.empty or len(raw.columns) < 4:
            continue

        df = _norm_cols(raw)

        # Fix trailing underscore on fte_tot_ → fte_tot
        df.columns = [
            "fte_tot" if c.startswith("fte_tot") else c
            for c in df.columns
        ]

        if not FAMIS_REQUIRED.issubset(df.columns):
            continue

        # Keep only allowed columns
        keep = [c for c in df.columns if c in FAMIS_ALLOWED]
        df = df[keep].copy()

        # Drop rows where loc_id is null/numeric (header leak)
        df = df[df["loc_id"].notna()]
        df = df[df["loc_id"].astype(str).str.match(r"^[A-Z]{3,6}$", na=False)]

        if df.empty:
            continue

        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
        df = df[df["date"].notna()]
        valid_dfs.append(df)

    if not valid_dfs:
        raise ValueError(
            "No sheets with required columns (date, loc_id, pk_gross_tot) found. "
            "Check the file — summary/graph sheets are skipped automatically."
        )

    combined = (
        pd.concat(valid_dfs, ignore_index=True)
        .drop_duplicates(subset=["date", "loc_id"])
        .sort_values(["date", "loc_id"])
        .reset_index(drop=True)
    )
    return combined


# ── Inbox scan functions ──────────────────────────────────────────────────────
def scan_famis_inbox(auto_move: bool = False) -> list:
    """
    Return list of dicts: {path, filename, df} for each valid FAMIS file in inbox.
    If auto_move=True, moves processed files to processed/famis/.
    """
    ensure_inbox_dirs()
    results = []
    for path in _list_inbox("famis", ".xlsx", ".xls"):
        try:
            df = parse_famis_file(path)
            entry = {"path": path, "filename": os.path.basename(path), "df": df}
            results.append(entry)
            if auto_move:
                _move_processed(path, "famis")
        except Exception as e:
            logger.warning("FAMIS inbox: could not parse %s: %s", path, e)
    return results


def scan_nsl_inbox() -> list:
    """
    Return list of dicts: {path, filename, bytes} for NSL text files in inbox.
    Does NOT move files — NSL parser is in nsl_tab.py.
    """
    ensure_inbox_dirs()
    results = []
    for path in _list_inbox("nsl", ".txt", ".csv"):
        try:
            with open(path, "rb") as f:
                data = f.read()
            results.append({"path": path, "filename": os.path.basename(path), "bytes": data})
        except Exception as e:
            logger.warning("NSL inbox: could not read %s: %s", path, e)
    return results


def mark_nsl_processed(path: str) -> str:
    return _move_processed(path, "nsl")


def scan_scorecard_inbox() -> tuple:
    """
    Return (path, file_bytes) of the most recent scorecard xlsb, or (None, None).
    """
    ensure_inbox_dirs()
    files = _list_inbox("scorecard", ".xlsb")
    if not files:
        return None, None
    path = files[0]
    try:
        with open(path, "rb") as f:
            data = f.read()
        return path, data
    except Exception as e:
        logger.warning("Scorecard inbox: could not read %s: %s", path, e)
        return None, None


def mark_scorecard_processed(path: str) -> str:
    return _move_processed(path, "scorecard")
