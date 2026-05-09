-- ============================================
-- DATABASE: aero_planner
-- ============================================

-- ==============================
-- TABLE 1: Upload History
-- ==============================
CREATE TABLE IF NOT EXISTS upload_history (
    upload_id        SERIAL PRIMARY KEY,
    file_name        TEXT        NOT NULL,
    upload_timestamp TIMESTAMP   DEFAULT NOW(),
    total_records    INT         NOT NULL DEFAULT 0,
    stations_count   INT         NOT NULL DEFAULT 0,
    date_range_from  DATE,
    date_range_to    DATE
);

-- ==============================
-- TABLE 2: Station Health
-- ==============================
CREATE TABLE IF NOT EXISTS station_health (
    loc_id      TEXT    NOT NULL,
    report_date DATE    NOT NULL,
    -- FK to upload_history; set NULL if the parent record is deleted (DL-006)
    upload_id   INT     REFERENCES upload_history(upload_id) ON DELETE SET NULL,

    pk_gross_tot        NUMERIC  DEFAULT 0  NOT NULL,

    calculated_area     NUMERIC  DEFAULT 0  NOT NULL,
    area_status         TEXT     DEFAULT 'UNKNOWN' NOT NULL
                            CHECK (area_status IN (
                                'HEALTHY', 'REVIEW_NEEDED', 'CRITICAL', 'UNKNOWN', 'NO DATA'
                            )),

    calculated_agents   NUMERIC  DEFAULT 0  NOT NULL,
    resource_status     TEXT     DEFAULT 'UNKNOWN' NOT NULL
                            CHECK (resource_status IN (
                                'HEALTHY', 'REVIEW_NEEDED', 'CRITICAL', 'UNKNOWN', 'NO DATA'
                            )),

    calculated_couriers NUMERIC  DEFAULT 0  NOT NULL,
    courier_status      TEXT     DEFAULT 'UNKNOWN' NOT NULL
                            CHECK (courier_status IN (
                                'HEALTHY', 'REVIEW_NEEDED', 'CRITICAL', 'UNKNOWN', 'NO DATA'
                            )),

    published_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (loc_id, report_date)
);

-- ==============================
-- INDEXES (Performance) (DL-006)
-- ==============================
CREATE INDEX IF NOT EXISTS idx_station_health_date
ON station_health(report_date);

CREATE INDEX IF NOT EXISTS idx_station_health_loc
ON station_health(loc_id);

CREATE INDEX IF NOT EXISTS idx_station_health_upload
ON station_health(upload_id);

-- ==============================
-- BASIC VIEW (for testing)
-- ==============================
CREATE OR REPLACE VIEW v_health_summary AS
SELECT
    loc_id,
    report_date,
    area_status,
    resource_status,
    courier_status,
    CASE
        WHEN area_status = 'CRITICAL'
          OR resource_status = 'CRITICAL'
          OR courier_status = 'CRITICAL'
        THEN 'CRITICAL'
        WHEN area_status = 'REVIEW_NEEDED'
          OR resource_status = 'REVIEW_NEEDED'
          OR courier_status = 'REVIEW_NEEDED'
        THEN 'REVIEW'
        ELSE 'HEALTHY'
    END AS final_status
FROM station_health;
