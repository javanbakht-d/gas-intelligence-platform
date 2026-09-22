"""
Quality Rule Engine - Gas Intelligence Platform
Milestone 2 / Commit 3

Evaluates configurable rules (cfg_quality_rules) against the staging rows of a
single load. Every operator returns row-level failures so the gate can
quarantine exact rows with exact fields and original values (no silent drops).
"""

from __future__ import annotations

import json

import pandas as pd

from pipeline.db import query

TEMP_FIELDS = ("temp_point_1", "temp_point_2", "temp_18")

FIELD_MAP = {
    "تاریخ": "shamsi_date",
    "استان": "province",
    "شهر": "city",
    "نام ایستگاه": "station",
    "نوع مصرف": "consumption_type",
    "میزان مصرف": "consumption",
}

# rule dimension -> explainable score dimension
DIM_TO_SCORE = {
    "structural": "integrity",
    "type": "accuracy",
    "completeness": "completeness",
    "uniqueness": "uniqueness",
    "validity": "validity",
    "consistency": "consistency",
    "crossfield": "validity",
    "temporal": "timeliness",
}


def load_staging(load_id: str) -> pd.DataFrame:
    rows = query(
        "SELECT row_number, row_fingerprint, shamsi_date, gregorian_date,"
        " shamsi_year, shamsi_month, shamsi_day, province, city, station,"
        " consumption_type, consumption, temp_point_1, temp_point_2, temp_18,"
        " pressure_6 FROM stg_station_consumption WHERE load_id=?",
        (load_id,),
    )
    return pd.DataFrame(rows)


def _fail(row_number, field, value):
    if value is None or (isinstance(value, float) and value != value):
        return (int(row_number), field, None)
    return (int(row_number), field, str(value))


def op_exists(df, params):
    checked = len(df)
    failures = [] if checked > 0 else [(0, "sheet", None)]
    return {"checked": checked, "failures": failures, "metric": float(checked),
            "threshold": 1.0,
            "message_fa": "شیت منبع خوانده شد" if checked > 0 else "شیت منبع وجود ندارد"}


def op_columns_exist(df, params):
    mandatory = ["shamsi_date", "station", "consumption"]
    present = [c for c in mandatory if c in df.columns and df[c].notna().any()]
    checked = len(df)
    ok = len(present) == len(mandatory)
    failures = [] if ok else [(0, c, None) for c in mandatory if c not in present]
    return {"checked": checked, "failures": failures,
            "metric": float(len(present)), "threshold": float(len(mandatory)),
            "message_fa": "ستون‌های اجباری حاضرند" if ok else "ستون اجباری مفقود است"}


def op_parse_jalali(df, params):
    checked = len(df)
    null_mask = df["shamsi_date"].isna()
    failures = [_fail(r, "تاریخ", None) for r in df.loc[null_mask, "row_number"]]
    valid_pct = (checked - len(failures)) / checked * 100 if checked else 0.0
    thr = float(params.get("min_valid_pct", 99.0))
    return {"checked": checked, "failures": failures, "metric": round(valid_pct, 2),
            "threshold": thr,
            "message_fa": f"درصد تاریخ‌های معتبر {valid_pct:.2f}٪ (آستانه {thr}٪)"}


def op_parse_numeric(df, params):
    checked = len(df)
    null_mask = df["consumption"].isna()
    failures = [_fail(r, "میزان مصرف", None) for r in df.loc[null_mask, "row_number"]]
    valid_pct = (checked - len(failures)) / checked * 100 if checked else 0.0
    thr = float(params.get("min_valid_pct", 99.0))
    return {"checked": checked, "failures": failures, "metric": round(valid_pct, 2),
            "threshold": thr,
            "message_fa": f"درصد مقادیر عددی معتبر {valid_pct:.2f}٪ (آستانه {thr}٪)"}


def op_not_null_pct_gte(df, params):
    columns = [FIELD_MAP.get(c, c) for c in params.get("columns", [])]
    checked = len(df)
    failures = []
    worst = 100.0
    for col in columns:
        if col not in df.columns:
            worst = 0.0
            failures.append((0, col, None))
            continue
        null_mask = df[col].isna()
        pct = (checked - int(null_mask.sum())) / checked * 100 if checked else 0.0
        worst = min(worst, pct)
        failures += [_fail(r, col, None) for r in df.loc[null_mask, "row_number"]]
    thr = float(params.get("min_pct", 95.0))
    return {"checked": checked, "failures": failures, "metric": round(worst, 2),
            "threshold": thr,
            "message_fa": f"کمترین درصد کامل بودن ستون‌های اجباری {worst:.2f}٪ (آستانه {thr}٪)"}


def op_duplicate_count_eq(df, params, target="row"):
    checked = len(df)
    max_dup = int(params.get("max", 0))
    keys = ["row_fingerprint"] if target == "row" else ["station", "shamsi_date", "consumption_type"]
    dup_mask = df.duplicated(subset=keys, keep="first")
    failures = [_fail(r, "+".join(keys), None) for r in df.loc[dup_mask, "row_number"]]
    label = "اثرانگشت ردیف" if target == "row" else "کلید تجاری"
    return {"checked": checked, "failures": failures, "metric": float(len(failures)),
            "threshold": float(max_dup),
            "message_fa": f"{len(failures)} ردیف تکراری بر اساس {label}"}


def op_range(df, params):
    lo, hi = float(params.get("min", -30)), float(params.get("max", 100))
    checked = len(df)
    failures = []
    for col in TEMP_FIELDS:
        if col not in df.columns:
            continue
        s = df[col]
        bad = s.notna() & ((s < lo) | (s > hi))
        failures += [_fail(r, col, v) for r, v in zip(df.loc[bad, "row_number"], s[bad])]
    return {"checked": checked, "failures": failures, "metric": float(len(failures)),
            "threshold": 0.0,
            "message_fa": f"{len(failures)} مقدار دما خارج از بازه [{lo}, {hi}]"}


def op_gte(df, params):
    lo = float(params.get("min", 0))
    checked = len(df)
    s = df["consumption"]
    bad = s.notna() & (s < lo)
    failures = [_fail(r, "consumption", v) for r, v in zip(df.loc[bad, "row_number"], s[bad])]
    return {"checked": checked, "failures": failures, "metric": float(len(failures)),
            "threshold": 0.0,
            "message_fa": f"{len(failures)} مقدار کمتر از {lo} (پرچم هشدار؛ حذف نشده)"}


def op_known_mapping(df, params):
    checked = len(df)
    sub = df.dropna(subset=["city", "province"])
    multi = sub.groupby("city")["province"].nunique()
    bad_cities = set(multi[multi > 1].index)
    mask = df["city"].isin(bad_cities)
    failures = [_fail(r, "شهر/استان", c) for r, c in zip(df.loc[mask, "row_number"], df.loc[mask, "city"])]
    return {"checked": checked, "failures": failures, "metric": float(len(bad_cities)),
            "threshold": 0.0,
            "message_fa": f"{len(bad_cities)} شهر با بیش از یک استان ثبت شده"}


def op_abs_diff_lte(df, params):
    mx = float(params.get("max", 50))
    checked = len(df)
    t1, t2 = df["temp_point_1"], df["temp_point_2"]
    both = t1.notna() & t2.notna()
    diff = (t1 - t2).abs()
    bad = both & (diff > mx)
    failures = [_fail(r, "اختلاف نقطه1/نقطه2", d) for r, d in zip(df.loc[bad, "row_number"], diff[bad])]
    return {"checked": checked, "failures": failures, "metric": float(len(failures)),
            "threshold": 0.0,
            "message_fa": f"{len(failures)} ردیف با اختلاف دمایی بیش از {mx}"}


def op_lte_today(df, params):
    checked = len(df)
    try:
        import jdatetime
        today = jdatetime.datetime.now().date()
        t = (today.year, today.month, today.day)
    except Exception:
        return {"checked": checked, "failures": [], "metric": 0.0, "threshold": 0.0,
                "message_fa": "بررسی تاریخ آینده در دسترس نیست (jdatetime نصب نیست)"}
    y, m, d = df["shamsi_year"], df["shamsi_month"], df["shamsi_day"]
    valid = y.notna() & m.notna() & d.notna()
    future = [(yy, mm, dd) > t for yy, mm, dd in zip(y[valid], m[valid], d[valid])]
    fs = pd.Series(future, index=df.index[valid]).reindex(df.index, fill_value=False)
    failures = [_fail(r, "تاریخ", None) for r in df.loc[fs, "row_number"]]
    return {"checked": checked, "failures": failures, "metric": float(len(failures)),
            "threshold": 0.0,
            "message_fa": f"{len(failures)} تاریخ آینده غیرمنتظره"}


def op_missing_days_lte(df, params):
    mx = int(params.get("max", 7))
    checked = len(df)
    dates = pd.to_datetime(df["gregorian_date"], errors="coerce").dropna()
    if len(dates) == 0:
        return {"checked": checked, "failures": [], "metric": 0.0, "threshold": float(mx),
                "message_fa": "تاریخ میلادی معتبری برای بررسی پیوستگی نیست"}
    full = pd.date_range(dates.min(), dates.max(), freq="D")
    missing = len(full) - dates.dt.normalize().nunique()
    missing = max(int(missing), 0)
    return {"checked": checked, "failures": [], "metric": float(missing),
            "threshold": float(mx),
            "message_fa": f"{missing} روز مفقود در بازه پوشش"}


OPERATORS = {
    "exists": op_exists,
    "columns_exist": op_columns_exist,
    "parse_jalali": op_parse_jalali,
    "parse_numeric": op_parse_numeric,
    "not_null_pct_gte": op_not_null_pct_gte,
    "duplicate_count_eq": op_duplicate_count_eq,
    "range": op_range,
    "gte": op_gte,
    "known_mapping": op_known_mapping,
    "abs_diff_lte": op_abs_diff_lte,
    "lte_today": op_lte_today,
    "missing_days_lte": op_missing_days_lte,
}


def _passed(rule, res, params):
    op = rule["operator"]
    m, t = res["metric"], res["threshold"]
    if op in ("parse_jalali", "parse_numeric", "not_null_pct_gte", "columns_exist"):
        return 1 if m >= t else 0
    if op == "duplicate_count_eq":
        return 1 if m <= float(params.get("max", 0)) else 0
    if op == "missing_days_lte":
        return 1 if m <= t else 0
    if op == "exists":
        return 1 if m >= 1 else 0
    return 1 if m == 0 else 0


def evaluate_rule(rule: dict, df: pd.DataFrame) -> dict:
    params = json.loads(rule["params_json"] or "{}")
    target = rule["target"] or ""
    if rule["operator"] == "duplicate_count_eq":
        kind = "row" if target == "row" else "key"
        res = op_duplicate_count_eq(df, params, target=kind)
    else:
        res = OPERATORS[rule["operator"]](df, params)
    res["passed"] = _passed(rule, res, params)
    return res