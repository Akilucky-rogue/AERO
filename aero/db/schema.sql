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

-- ==============================
-- NSL ANALYTICS TABLES
-- ==============================

-- Upload log — one row per file ingested
CREATE TABLE IF NOT EXISTS nsl_upload_log (
    id            SERIAL PRIMARY KEY,
    filename      VARCHAR(255)  NOT NULL,
    rows_upserted INTEGER       NOT NULL DEFAULT 0,
    total_rows_db INTEGER       NOT NULL DEFAULT 0,
    uploaded_at   TIMESTAMP     NOT NULL DEFAULT NOW(),
    uploaded_by   VARCHAR(100)  DEFAULT 'system'
);

-- Core shipment data — shp_trk_nbr is the natural unique key
CREATE TABLE IF NOT EXISTS nsl_shipments (
    shp_trk_nbr            VARCHAR(60)  PRIMARY KEY,
    month_date             DATE,
    weekending_dt          DATE,
    svc_commit_dt          DATE,
    shp_dt                 DATE,
    pckup_scan_dt          DATE,
    pod_scan_dt            DATE,
    shpr_co_nm             VARCHAR(255),
    orig_loc_cd            VARCHAR(20),
    dest_loc_cd            VARCHAR(20),
    orig_region            VARCHAR(50),
    dest_region            VARCHAR(50),
    orig_market_cd         VARCHAR(20),
    dest_market_cd         VARCHAR(20),
    orig_subregion         VARCHAR(50),
    dest_subregion         VARCHAR(50),
    service                VARCHAR(50),
    service_detail         VARCHAR(100),
    product                VARCHAR(50),
    bucket                 VARCHAR(50),
    pof_cause              VARCHAR(20),
    mbg_class              VARCHAR(20),
    nsl_ot_vol             SMALLINT,
    mbg_ot_vol             SMALLINT,
    nsl_f_vol              SMALLINT,
    mbg_f_vol              SMALLINT,
    tot_vol                SMALLINT,
    pkg_pckup_scan_typ_cd  SMALLINT,
    pkg_pckup_excp_typ_cd  SMALLINT,
    pckup_stop_typ_cd      VARCHAR(5),
    pof_region_cd          VARCHAR(50),
    pof_loc_cd             VARCHAR(20),
    updated_at             TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nsl_month      ON nsl_shipments(month_date);
CREATE INDEX IF NOT EXISTS idx_nsl_dest_mkt   ON nsl_shipments(dest_market_cd);
CREATE INDEX IF NOT EXISTS idx_nsl_dest_reg   ON nsl_shipments(dest_region);
CREATE INDEX IF NOT EXISTS idx_nsl_customer   ON nsl_shipments(shpr_co_nm);
CREATE INDEX IF NOT EXISTS idx_nsl_service    ON nsl_shipments(service);
CREATE INDEX IF NOT EXISTS idx_nsl_bucket     ON nsl_shipments(bucket);
CREATE INDEX IF NOT EXISTS idx_nsl_week       ON nsl_shipments(weekending_dt);

-- ==============================
-- FAMIS VOLUME DATA
-- ==============================

CREATE TABLE IF NOT EXISTS famis_data (
    loc_id          VARCHAR(20)  NOT NULL,
    report_date     DATE         NOT NULL,
    pk_gross_tot    NUMERIC      DEFAULT 0  NOT NULL,
    pk_gross_inb    NUMERIC,
    pk_gross_outb   NUMERIC,
    pk_oda          NUMERIC,
    pk_opa          NUMERIC,
    pk_roc          NUMERIC,
    fte_tot         NUMERIC,
    st_cr_or        NUMERIC,
    pk_fte          NUMERIC,
    pk_cr_or        NUMERIC,
    uploaded_at     TIMESTAMP    DEFAULT NOW(),
    PRIMARY KEY (loc_id, report_date)
);

CREATE TABLE IF NOT EXISTS famis_upload_log (
    id              SERIAL        PRIMARY KEY,
    filename        VARCHAR(255)  NOT NULL,
    rows_upserted   INTEGER       NOT NULL DEFAULT 0,
    total_rows_db   INTEGER       NOT NULL DEFAULT 0,
    uploaded_at     TIMESTAMP     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_famis_date  ON famis_data(report_date);
CREATE INDEX IF NOT EXISTS idx_famis_loc   ON famis_data(loc_id);
