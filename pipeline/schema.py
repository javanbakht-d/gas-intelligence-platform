"""
Pipeline Schema - Gas Intelligence Platform
Milestone 2 / Commit 1

Creates the governed data-lifecycle tables (sources, loads, raw, staging,
quality config, quarantine, decisions, reconciliation) WITHOUT touching any
existing analytical table. All rules/thresholds/weights are configurable rows,
never hard-coded business logic.
"""

from __future__ import annotations

import json

from pipeline.db import connect, query, query_one

PIPELINE_TABLES = [
    "src_sources",
    "load_loads",
    "raw_station_consumption",
    "stg_station_consumption",
    "cfg_quality_rules",
    "cfg_quality_weights",
    "cfg_settings",
    "qua_rule_results",
    "qua_quarantine",
    "audit_quality_decisions",
    "audit_reconciliation",
]

DDL = [
    """
    CREATE TABLE IF NOT EXISTS src_sources (
        source_id              TEXT PRIMARY KEY,
        name                   TEXT NOT NULL,
        source_type            TEXT NOT NULL CHECK (source_type IN ('excel','csv','api')),
        default_schema_version TEXT,
        description_fa         TEXT,
        created_at             TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS load_loads (
        load_id            TEXT PRIMARY KEY,
        source_id          TEXT NOT NULL REFERENCES src_sources(source_id),
        file_name          TEXT NOT NULL,
        file_hash          TEXT NOT NULL,
        file_size          INTEGER NOT NULL,
        received_at        TEXT NOT NULL,
        schema_version     TEXT,
        row_count          INTEGER,
        accepted_count     INTEGER,
        rejected_count     INTEGER,
        warning_count      INTEGER,
        processing_time_ms INTEGER,
        status             TEXT NOT NULL CHECK (status IN
            ('RECEIVED','VALIDATING','QUARANTINED','PARTIALLY_ACCEPTED',
             'ACCEPTED','REJECTED','SUPERSEDED','FAILED')),
        superseded_by      TEXT,
        error_message      TEXT,
        created_by         TEXT NOT NULL DEFAULT 'system'
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_loads_source_hash
        ON load_loads(source_id, file_hash)
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_station_consumption (
        raw_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        load_id         TEXT NOT NULL REFERENCES load_loads(load_id),
        row_number      INTEGER NOT NULL,
        row_fingerprint TEXT NOT NULL,
        payload_json    TEXT NOT NULL,
        received_at     TEXT NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_raw_station_fp
        ON raw_station_consumption(row_fingerprint)
    """,
    """
    CREATE TABLE IF NOT EXISTS stg_station_consumption (
        stg_id           INTEGER PRIMARY KEY AUTOINCREMENT,
        load_id          TEXT NOT NULL REFERENCES load_loads(load_id),
        row_number       INTEGER NOT NULL,
        row_fingerprint  TEXT NOT NULL,
        shamsi_date      TEXT,
        gregorian_date   TEXT,
        shamsi_year      INTEGER,
        shamsi_month     INTEGER,
        shamsi_day       INTEGER,
        weekday          INTEGER,
        season           INTEGER,
        is_weekend       INTEGER,
        province         TEXT,
        city             TEXT,
        station          TEXT,
        consumption_type TEXT,
        consumption      REAL,
        temp_point_1     REAL,
        temp_point_2     REAL,
        temp_18          REAL,
        pressure_6       REAL,
        gate_status      TEXT NOT NULL DEFAULT 'PENDING'
            CHECK (gate_status IN ('PENDING','ACCEPTED','WARNING','QUARANTINED')),
        created_at       TEXT NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_stg_station_fp
        ON stg_station_consumption(load_id, row_fingerprint)
    """,
    """
    CREATE TABLE IF NOT EXISTS cfg_quality_rules (
        rule_id        TEXT PRIMARY KEY,
        dimension      TEXT NOT NULL,
        target         TEXT,
        operator       TEXT NOT NULL,
        params_json    TEXT,
        severity       TEXT NOT NULL CHECK (severity IN ('INFO','WARNING','ERROR','CRITICAL')),
        active         INTEGER NOT NULL DEFAULT 1,
        description_fa TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cfg_quality_weights (
        dimension TEXT PRIMARY KEY,
        weight    REAL NOT NULL CHECK (weight >= 0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cfg_settings (
        setting_key    TEXT PRIMARY KEY,
        value_json     TEXT NOT NULL,
        description_fa TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS qua_rule_results (
        result_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        load_id         TEXT NOT NULL REFERENCES load_loads(load_id),
        rule_id         TEXT NOT NULL,
        dimension       TEXT NOT NULL,
        severity        TEXT NOT NULL,
        checked_rows    INTEGER,
        failed_rows     INTEGER,
        metric_value    REAL,
        threshold_value REAL,
        passed          INTEGER NOT NULL,
        message_fa      TEXT,
        evaluated_at    TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS qua_quarantine (
        quarantine_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        load_id          TEXT NOT NULL REFERENCES load_loads(load_id),
        row_number       INTEGER NOT NULL,
        field            TEXT,
        original_value   TEXT,
        normalized_value TEXT,
        rule_id          TEXT NOT NULL,
        error_code       TEXT NOT NULL,
        severity         TEXT NOT NULL,
        explanation_fa   TEXT NOT NULL,
        review_status    TEXT NOT NULL DEFAULT 'PENDING'
            CHECK (review_status IN ('PENDING','APPROVED','REJECTED','FIXED')),
        reviewed_by      TEXT,
        reviewed_at      TEXT,
        review_note      TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_quality_decisions (
        decision_id             INTEGER PRIMARY KEY AUTOINCREMENT,
        load_id                 TEXT NOT NULL UNIQUE REFERENCES load_loads(load_id),
        score_overall           REAL,
        score_by_dimension_json TEXT,
        decision                TEXT NOT NULL CHECK (decision IN
            ('ACCEPT','ACCEPT_WITH_WARNINGS','QUARANTINE','REJECT')),
        auto                    INTEGER NOT NULL DEFAULT 1,
        decided_by              TEXT,
        decided_at              TEXT NOT NULL,
        reason_fa               TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_reconciliation (
        recon_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        load_id       TEXT NOT NULL REFERENCES load_loads(load_id),
        check_name    TEXT NOT NULL,
        source_value  REAL,
        curated_value REAL,
        diff          REAL,
        diff_pct      REAL,
        passed        INTEGER NOT NULL,
        checked_at    TEXT NOT NULL
    )
    """,
]

# Weights must sum to 1.0 - explainable score dimensions (configurable)
SEED_WEIGHTS = [
    ("completeness", 0.20),
    ("accuracy", 0.20),
    ("validity", 0.20),
    ("consistency", 0.15),
    ("uniqueness", 0.10),
    ("timeliness", 0.10),
    ("integrity", 0.05),
]

# (rule_id, dimension, target, operator, params_json, severity, description_fa)
SEED_RULES = [
    ("R_STRUCT_SHEET_EXISTS", "structural", "sheet:GasOperationDailyStationReport",
     "exists", "{}", "CRITICAL", "شیت اصلی مصرف ایستگاه‌ها باید وجود داشته باشد"),
    ("R_STRUCT_COLS_EXPECTED", "structural", "sheet:GasOperationDailyStationReport",
     "columns_exist",
     json.dumps({"columns": ["تاریخ", "استان", "نام ایستگاه", "نوع مصرف", "میزان مصرف"]}, ensure_ascii=False),
     "CRITICAL", "ستون‌های اجباری باید حضور داشته باشند"),
    ("R_TYPE_DATE_JALALI", "type", "تاریخ", "parse_jalali",
     json.dumps({"min_valid_pct": 99.0}), "ERROR", "تاریخ‌ها باید شمسی و قابل تبدیل باشند"),
    ("R_TYPE_NUMERIC_CONSUMPTION", "type", "میزان مصرف", "parse_numeric",
     json.dumps({"min_valid_pct": 99.0}), "ERROR", "میزان مصرف باید عددی باشد"),
    ("R_COMP_MANDATORY_NOTNULL", "completeness", "mandatory",
     "not_null_pct_gte",
     json.dumps({"columns": ["تاریخ", "استان", "نام ایستگاه", "میزان مصرف"], "min_pct": 95.0}, ensure_ascii=False),
     "ERROR", "ستون‌های اجباری نباید بیش از آستانه مفقود باشند"),
    ("R_UNIQ_ROW_FINGERPRINT", "uniqueness", "row", "duplicate_count_eq",
     json.dumps({"max": 0}), "WARNING", "ردیف کاملاً تکراری نباید وجود داشته باشد"),
    ("R_UNIQ_KEY_STATION_DATE_TYPE", "uniqueness", "نام ایستگاه+تاریخ+نوع مصرف",
     "duplicate_count_eq", json.dumps({"max": 0}), "ERROR",
     "کلید ایستگاه/تاریخ/نوع مصرف باید یکتا باشد"),
    ("R_VALID_TEMP_RANGE", "validity", "دمای گاز", "range",
     json.dumps({"min": -30, "max": 100}), "ERROR", "دما باید در بازه منطقی باشد"),
    ("R_VALID_CONSUMPTION_NONNEG", "validity", "میزان مصرف", "gte",
     json.dumps({"min": 0}), "WARNING", "مقادیر منفی حذف نمی‌شوند؛ فقط پرچم می‌خورند"),
    ("R_CONS_PROVINCE_CITY", "consistency", "استان/شهر", "known_mapping",
     "{}", "WARNING", "ترکیب استان و شهر باید با داده‌های تاریخی سازگار باشد"),
    ("R_XFIELD_TEMP_POINTS_DIFF", "crossfield", "نقطه1/نقطه2", "abs_diff_lte",
     json.dumps({"max": 50}), "WARNING", "اختلاف دو نقطه اندازه‌گیری دما باید منطقی باشد"),
    ("R_TEMP_NO_FUTURE_DATES", "temporal", "تاریخ", "lte_today",
     "{}", "ERROR", "تاریخ آینده غیرمنتظره پذیرفته نمی‌شود"),
    ("R_TEMP_COVERAGE_GAPS", "temporal", "تاریخ", "missing_days_lte",
     json.dumps({"max": 7}), "WARNING", "شکاف روزهای مفقود نباید از آستانه بیشتر باشد"),
]

# (setting_key, value, description_fa)
SEED_SETTINGS = [
    ("gate_accept_score", 85.0, "حداقل امتیاز برای پذیرش خودکار"),
    ("gate_warn_score", 70.0, "حداقل امتیاز برای پذیرش مشروط به هشدار"),
    ("gate_reject_score", 40.0, "زیر این امتیاز کل بارگذاری رد می‌شود"),
    ("gate_max_critical", 0, "حداکثر خطای CRITICAL مجاز برای پذیرش"),
    ("gate_max_error_for_accept", 0, "حداکثر خطای ERROR مجاز برای پذیرش کامل"),
]


def init_schema() -> dict:
    """Create pipeline tables and seed configuration. Idempotent."""
    with connect() as conn:
        for stmt in DDL:
            conn.execute(stmt)

        for dim, weight in SEED_WEIGHTS:
            conn.execute(
                "INSERT OR IGNORE INTO cfg_quality_weights(dimension, weight) VALUES (?, ?)",
                (dim, weight),
            )

        for rule in SEED_RULES:
            conn.execute(
                "INSERT OR IGNORE INTO cfg_quality_rules"
                "(rule_id, dimension, target, operator, params_json, severity, active, description_fa)"
                " VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                rule,
            )

        for key, value, desc in SEED_SETTINGS:
            conn.execute(
                "INSERT OR IGNORE INTO cfg_settings(setting_key, value_json, description_fa)"
                " VALUES (?, ?, ?)",
                (key, json.dumps(value, ensure_ascii=False), desc),
            )

    return schema_report()


def schema_report() -> dict:
    """Return row counts of pipeline tables (None if a table is missing)."""
    report = {}
    for name in PIPELINE_TABLES:
        row = query_one(f"SELECT COUNT(*) AS c FROM {name}")
        report[name] = row["c"] if row else None
    return report


if __name__ == "__main__":
    print("Initializing pipeline schema...")
    rep = init_schema()

    print("\nPipeline tables:")
    for name, count in rep.items():
        status = f"{count} rows" if count is not None else "MISSING!"
        print(f"  - {name}: {status}")

    rules = query_one("SELECT COUNT(*) AS c FROM cfg_quality_rules")
    weights = query_one("SELECT COUNT(*) AS c FROM cfg_quality_weights")
    settings = query_one("SELECT COUNT(*) AS c FROM cfg_settings")
    print(f"\nSeeds: rules={rules['c']} weights={weights['c']} settings={settings['c']}")
    print("\n✅ Pipeline schema ready.")