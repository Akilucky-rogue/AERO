"""Hub Courier Tracker — bridges hub session state into station planner render()."""
import streamlit as st


def render():
    """Render Hub Courier Tracker by bridging hub_ session state to station keys."""
    _saved_famis = st.session_state.get("famis_data")
    _saved_master = st.session_state.get("master_data")
    _saved_station = st.session_state.get("station_loc_id")

    try:
        hub_famis = st.session_state.get("hub_famis_data")
        hub_master = st.session_state.get("hub_master_data")
        hub_station = st.session_state.get("hub_famis_station", "")

        if hub_famis is not None:
            st.session_state["famis_data"] = hub_famis
        if hub_master is not None:
            st.session_state["master_data"] = hub_master
        if hub_station:
            st.session_state["station_loc_id"] = hub_station

        from pages.courier_planner import render as _station_render
        _station_render()

    finally:
        if _saved_famis is not None:
            st.session_state["famis_data"] = _saved_famis
        elif "famis_data" in st.session_state and st.session_state.get("famis_data") is not _saved_famis:
            st.session_state["famis_data"] = _saved_famis

        if _saved_master is not None:
            st.session_state["master_data"] = _saved_master
        elif "master_data" in st.session_state and st.session_state.get("master_data") is not _saved_master:
            st.session_state["master_data"] = _saved_master

        if _saved_station is not None:
            st.session_state["station_loc_id"] = _saved_station
