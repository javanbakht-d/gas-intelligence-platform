"""
Generic Source Ingestion Framework - Gas Intelligence Platform
Milestone 2 / Commit 2

Flow:  file -> hash -> load registry -> raw (immutable) -> staging (normalized)
Idempotent: same (source_id, file_hash) or same row fingerprint never duplicates.
Analytical tables are NOT touched here (UI stays intact until Milestone 3).
"""

from __future__ import annotations

import argparse
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from pipeline.db import connect, query, query_one
from pipeline.fingerprints import (
    canon_value,
    file_sha256,
    normalize_persian_text,
    row_fingerprint,
)
from pipeline.schema import init_schema

DEFAULT_SHEET = "GasOperationDailyStationReport"

# canonical field -> acceptable source header names (normalized at match time)
COLUMN_CANDIDATES = {
    "date": ["تاریخ", "تاریخ شمسی"],
    "province": ["استان"],
    "city": ["شهر"],
    "station": ["نام ایستگاه"],
    "consumption_type": ["نوع مصرف"],
    "consumption": ["میزان مصرف"],
    "temp_point_1": ["دمای گاز ساعت 6 صبح - نقطه 1", "دمای ساعت6", "دمای ساعت 6"],
    "temp_point_2": ["دمای گاز ساعت 6 صبح - نقطه 2", "دمای ساعت6.1", "دمای ساعت 6.1"],
    "temp_18": ["دمای گاز ساعت 18", "دمای ساعت18", "دمای ساعت 18"],
    "pressure_6": ["فشار ساعت 6 صبح", "فشار ساعت 6", "فشار ساعت6"],
}

MANDATORY = ["date", "station", "consumption"]


class IngestionError(Exception):
    pass


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_source(source_id: str, name: str, source_type: str = "excel",
                  description_fa: str = None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO src_sources(source_id, name, source_type,"
            " default_schema_version, description_fa, created_at)"
            " VALUES (?, ?, ?, 'v1', ?, ?)",
            (source_id, name, source_type, description_fa, _utcnow()),
        )


def _norm_header(h: str) -> str:
    return normalize_persian_text(str(h))


def _resolve_columns(df: pd.DataFrame) -> dict:
    norm_map = {_norm_header(c): c for c in df.columns}
    resolved = {}
    for canon, candidates in COLUMN_CANDIDATES.items():
        resolved[canon] = None
        for cand in candidates:
            if _norm_header(cand) in norm_map:
                resolved[canon] = norm_map[_norm_header(cand)]
                break
    return resolved


def _parse_jalali(value):
    """Parse a Jalali date string; returns dict of date features (None-safe)."""
    out = {
        "shamsi_date": None, "shamsi_year": None, "shamsi_month": None,
        "shamsi_day": None, "gregorian_date": None, "weekday": None,
        "season": None, "is_weekend": None,
    }
    if value is None or (isinstance(value, float) and value != value):
        return out
    text = str(value).strip()
    m = re.match(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$", text)
    if not m:
        return out
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    out.update(shamsi_date=text, shamsi_year=y, shamsi_month=mo, shamsi_day=d)
    out["season"] = (mo - 1) // 3 + 1
    try:
        import jdatetime
        jd = jdatetime.date(y, mo, d)
        gd = jd.togregorian()
        wd = jd.weekday()
        out["gregorian_date"] = gd.isoformat()
        out["weekday"] = wd
        out["is_weekend"] = 1 if wd in (4, 5) else 0
    except Exception:
        pass
    return out


def _read_frame(path: Path, sheet: str) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        xls = pd.ExcelFile(path)
        if sheet not in xls.sheet_names:
            raise IngestionError(
                f"sheet '{sheet}' not found; available: {xls.sheet_names}"
            )
        df = pd.read_excel(xls, sheet_name=sheet)
    elif suffix == ".csv":
        df = pd.read_csv(path)
    else:
        raise IngestionError(f"unsupported file type: {suffix}")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def receive_file(source_id: str, file_path, sheet: str = DEFAULT_SHEET,
                 created_by: str = "cli") -> dict:
    t0 = time.perf_counter()
    path = Path(file_path)
    if not path.exists():
        raise IngestionError(f"file not found: {path}")

    init_schema()
    ensure_source(source_id, path.name)

    fhash = file_sha256(path)
    fsize = path.stat().st_size
    received_at = _utcnow()

    existing = query_one(
        "SELECT load_id, status FROM load_loads WHERE source_id=? AND file_hash=?",
        (source_id, fhash),
    )
    if existing:
        return {
            "duplicate": True,
            "load_id": existing["load_id"],
            "status": existing["status"],
            "message_fa": "این فایل قبلاً بارگذاری شده است؛ رکوردی تکراری نشد.",
        }

    load_id = f"L{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO load_loads(load_id, source_id, file_name, file_hash,"
            " file_size, received_at, schema_version, status, created_by)"
            " VALUES (?, ?, ?, ?, ?, ?, 'v1', 'RECEIVED', ?)",
            (load_id, source_id, path.name, fhash, fsize, received_at, created_by),
        )

    def _fail(msg: str):
        with connect() as conn:
            conn.execute(
                "UPDATE load_loads SET status='FAILED', error_message=?,"
                " processing_time_ms=? WHERE load_id=?",
                (msg, int((time.perf_counter() - t0) * 1000), load_id),
            )

    try:
        df = _read_frame(path, sheet)
        with connect() as conn:
            conn.execute(
                "UPDATE load_loads SET status='VALIDATING', row_count=? WHERE load_id=?",
                (len(df), load_id),
            )

        cols = _resolve_columns(df)
        missing = [c for c in MANDATORY if cols[c] is None]
        if missing:
            raise IngestionError(f"mandatory columns missing: {missing}")

        # vectorized numeric coercion
        numeric = {}
        for canon in ("consumption", "temp_point_1", "temp_point_2", "temp_18", "pressure_6"):
            src = cols[canon]
            numeric[canon] = pd.to_numeric(df[src], errors="coerce") if src else pd.Series([None] * len(df))

        texts = {}
        for canon in ("province", "city", "station", "consumption_type"):
            src = cols[canon]
            texts[canon] = df[src].map(normalize_persian_text) if src else pd.Series([""] * len(df))

        dates = df[cols["date"]].map(_parse_jalali)

        raw_rows, stg_rows = [], []
        payload_df = df.astype(object).where(pd.notna(df), None)
        records = payload_df.to_dict(orient="records")

        for i, rec in enumerate(records, start=1):
            d = dates.iloc[i - 1]
            fp = row_fingerprint({
                "date": canon_value(rec.get(cols["date"])),
                "province": texts["province"].iloc[i - 1],
                "city": texts["city"].iloc[i - 1],
                "station": texts["station"].iloc[i - 1],
                "ctype": texts["consumption_type"].iloc[i - 1],
                "consumption": canon_value(numeric["consumption"].iloc[i - 1]),
                "t1": canon_value(numeric["temp_point_1"].iloc[i - 1]),
                "t2": canon_value(numeric["temp_point_2"].iloc[i - 1]),
                "t18": canon_value(numeric["temp_18"].iloc[i - 1]),
                "p6": canon_value(numeric["pressure_6"].iloc[i - 1]),
            })
            raw_rows.append((
                load_id, i, fp,
                json.dumps(rec, ensure_ascii=False, default=str), received_at,
            ))
            stg_rows.append((
                load_id, i, fp,
                d["shamsi_date"], d["gregorian_date"], d["shamsi_year"],
                d["shamsi_month"], d["shamsi_day"], d["weekday"], d["season"],
                d["is_weekend"],
                texts["province"].iloc[i - 1] or None,
                texts["city"].iloc[i - 1] or None,
                texts["station"].iloc[i - 1] or None,
                texts["consumption_type"].iloc[i - 1] or None,
                None if pd.isna(numeric["consumption"].iloc[i - 1]) else float(numeric["consumption"].iloc[i - 1]),
                None if pd.isna(numeric["temp_point_1"].iloc[i - 1]) else float(numeric["temp_point_1"].iloc[i - 1]),
                None if pd.isna(numeric["temp_point_2"].iloc[i - 1]) else float(numeric["temp_point_2"].iloc[i - 1]),
                None if pd.isna(numeric["temp_18"].iloc[i - 1]) else float(numeric["temp_18"].iloc[i - 1]),
                None if pd.isna(numeric["pressure_6"].iloc[i - 1]) else float(numeric["pressure_6"].iloc[i - 1]),
                _utcnow(),
            ))

        with connect() as conn:
            cur = conn.executemany(
                "INSERT OR IGNORE INTO raw_station_consumption"
                "(load_id, row_number, row_fingerprint, payload_json, received_at)"
                " VALUES (?, ?, ?, ?, ?)",
                raw_rows,
            )
            raw_inserted = cur.rowcount
            cur = conn.executemany(
                "INSERT OR IGNORE INTO stg_station_consumption"
                "(load_id, row_number, row_fingerprint, shamsi_date, gregorian_date,"
                " shamsi_year, shamsi_month, shamsi_day, weekday, season, is_weekend,"
                " province, city, station, consumption_type, consumption,"
                " temp_point_1, temp_point_2, temp_18, pressure_6, gate_status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)",
                stg_rows,
            )
            stg_inserted = cur.rowcount
            conn.execute(
                "UPDATE load_loads SET row_count=?, accepted_count=?, rejected_count=0,"
                " warning_count=0, processing_time_ms=?, status='VALIDATING'"
                " WHERE load_id=?",
                (len(df), stg_inserted, int((time.perf_counter() - t0) * 1000), load_id),
            )

        return {
            "duplicate": False,
            "load_id": load_id,
            "status": "VALIDATING",
            "row_count": len(df),
            "raw_inserted": raw_inserted,
            "staging_inserted": stg_inserted,
            "processing_time_ms": int((time.perf_counter() - t0) * 1000),
            "message_fa": "بارگذاری در raw/staging انجام شد؛ منتظر Quality Gate (Commit 3).",
        }
    except Exception as exc:
        _fail(str(exc))
        raise


def list_loads(limit: int = 20):
    return query(
        "SELECT load_id, source_id, file_name, status, row_count, accepted_count,"
        " rejected_count, received_at FROM load_loads ORDER BY received_at DESC LIMIT ?",
        (limit,),
    )


def get_load(load_id: str):
    return query_one("SELECT * FROM load_loads WHERE load_id=?", (load_id,))


def main():
    parser = argparse.ArgumentParser(description="Ingest a source file into raw/staging")
    parser.add_argument("--file", required=True)
    parser.add_argument("--source", default="main_excel")
    parser.add_argument("--sheet", default=DEFAULT_SHEET)
    parser.add_argument("--created-by", default="cli")
    args = parser.parse_args()

    print(f"⏳ Ingesting {args.file} ... (may take 1-2 minutes for Excel)")
    result = receive_file(args.source, args.file, sheet=args.sheet,
                          created_by=args.created_by)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()