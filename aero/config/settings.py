import os
import json

import streamlit as st

_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(_CONFIG_DIR, "tact.json")
AREA_CONFIG_FILE = os.path.join(_CONFIG_DIR, "area.json")


@st.cache_data(ttl=300)
def load_config() -> dict:
    """Load TACT configuration from tact.json.  Cached for 5 minutes (CQ-010)."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_config(cfg: dict) -> None:
    """Persist TACT configuration and clear the in-memory cache."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)
    load_config.clear()  # invalidate cache so the next load picks up new values


@st.cache_data(ttl=300)
def load_area_config() -> dict:
    """Load area configuration from area.json.  Cached for 5 minutes (CQ-010)."""
    if os.path.exists(AREA_CONFIG_FILE):
        with open(AREA_CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_area_config(cfg: dict) -> None:
    """Persist area configuration and clear the in-memory cache."""
    with open(AREA_CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)
    load_area_config.clear()  # invalidate cache so the next load picks up new values


def get_default_area_constants() -> dict:
    area = load_area_config()
    return area.get("AREA_CONSTANTS", {})
