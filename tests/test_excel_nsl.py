"""
tests/test_excel_nsl.py — Unit tests for station NSL persistence in excel_store.py.
"""

import os
import pandas as pd
import pytest
import tempfile
from aero.data import excel_store


def test_nsl_persistence_preserves_master_and_registry(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch FAMIS_META_PATH to target a temporary file
        temp_meta_path = os.path.join(tmpdir, "FAMIS_META.xlsx")
        monkeypatch.setattr(excel_store, "FAMIS_META_PATH", temp_meta_path)

        # 1. Read initially empty NSL data
        df_empty = excel_store.read_station_nsl_data()
        assert df_empty.empty

        # 2. Upsert Master Data
        master_df = pd.DataFrame([{"loc_id": "ST-A", "total_facility_area": 50000}])
        excel_store.upsert_master_data(master_df)

        # 3. Upsert Registry Data (represented as registry row)
        registry_meta = {
            "display_name": "FAMIS-Test",
            "filename": "test.xlsx",
            "file_type": "Daily",
            "date_min": "2026-01-01",
            "date_max": "2026-01-05",
            "rows": 10,
            "stations": 1,
            "uploaded_at": "2026-06-09 12:00:00"
        }
        excel_store.upsert_famis_registry(registry_meta)

        # 4. Upsert Station NSL Data
        nsl_df = pd.DataFrame([{"orig_loc_cd": "ST-A", "tot_vol": 150, "nsl_ot_vol": 140, "nsl_f_vol": 10}])
        excel_store.upsert_station_nsl_data(nsl_df)

        # 5. Read all 3 sheets back and verify that nothing was overwritten/lost
        read_master = excel_store.read_master_data()
        read_registry = excel_store.read_famis_registry()
        read_nsl = excel_store.read_station_nsl_data()

        assert not read_master.empty
        assert read_master.iloc[0]["loc_id"] == "ST-A"

        assert not read_registry.empty
        assert read_registry.iloc[0]["filename"] == "test.xlsx"

        assert not read_nsl.empty
        assert read_nsl.iloc[0]["orig_loc_cd"] == "ST-A"
        assert read_nsl.iloc[0]["tot_vol"] == 150
        assert read_nsl.iloc[0]["nsl_ot_vol"] == 140
        assert read_nsl.iloc[0]["nsl_f_vol"] == 10
