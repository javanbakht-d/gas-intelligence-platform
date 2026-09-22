"""
Data Quality Gate - Gas Intelligence Platform
Milestone 2 / Commit 3

Scores a load across explainable dimensions, decides
ACCEPT / ACCEPT_WITH_WARNINGS / QUARANTINE / REJECT,
quarantines failing rows with reasons, and writes reconciliation checks.
Idempotent: re-running resets previous evaluations for the same load.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from pipeline.db import connect, query, query_one
from pipeline.rules import DIM_TO_SCORE, evaluate_rule, load_staging


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_gate(load_id: str) -> dict:
    df = load_staging(load_id)
    if df.empty:
        return {"load_id": load_id, "decision": "REJECT",
                "reason_fa": "هیچ ردیفی در staging برای این بارگذاری نیست"}

    rules = query("SELECT * FROM cfg_quality_rules WHERE active=1")
    weights = {r["dimension"]: r["weight"] for r in query("SELECT * FROM cfg_quality_weights")}
    settings = {r["setting_key"]: json.loads(r["value_json"]) for r in query("SELECT * FROM cfg_settings")}

    # reset previous evaluations (idempotency)
    with connect() as conn:
        conn.execute("DELETE FROM qua_rule_results WHERE load_id=?", (load_id,))
        conn.execute("DELETE FROM qua_quarantine WHERE load_id=?", (load_id,))
        conn.execute("UPDATE stg_station_consumption SET gate_status='PENDING' WHERE load_id=?", (load_id,))

    outcomes, quarantine, warn_rows = [], [], set()
    for rule in rules:
        res = evaluate_rule(rule, df)
        outcomes.append((rule, res))
        if rule["severity"] in ("ERROR", "CRITICAL"):
            for (rn, field, ov) in res["failures"]:
                quarantine.append((load_id, rn, field, ov, rule["rule_id"],
                                   rule["rule_id"], rule["severity"], res["message_fa"]))
        elif rule["severity"] == "WARNING":
            warn_rows.update(rn for (rn, _, _) in res["failures"])

    now = _utcnow()
    with connect() as conn:
        conn.executemany(
            "INSERT INTO qua_rule_results(load_id, rule_id, dimension, severity,"
            " checked_rows, failed_rows, metric_value, threshold_value, passed,"
            " message_fa, evaluated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(load_id, r["rule_id"], r["dimension"], r["severity"], res["checked"],
              len(res["failures"]), res["metric"], res["threshold"], res["passed"],
              res["message_fa"], now) for r, res in outcomes],
        )
        conn.executemany(
            "INSERT INTO qua_quarantine(load_id, row_number, field, original_value,"
            " rule_id, error_code, severity, explanation_fa) VALUES (?,?,?,?,?,?,?,?)",
            quarantine,
        )

    # explainable dimension scores
    dim_scores = {}
    for dim, score_dim in DIM_TO_SCORE.items():
        rel = [(r, res) for r, res in outcomes if r["dimension"] == dim]
        if not rel:
            continue
        vals = [100.0 * (1 - len(res["failures"]) / (res["checked"] or 1)) for _, res in rel]
        dim_scores[score_dim] = round(sum(vals) / len(vals), 2)
    for sd in ("completeness", "accuracy", "validity", "consistency",
               "uniqueness", "timeliness", "integrity"):
        dim_scores.setdefault(sd, 100.0)

    wsum = sum(weights.values()) or 1.0
    overall = round(sum(weights.get(k, 0) * v for k, v in dim_scores.items()) / wsum, 2)

    crit = sum(1 for r, res in outcomes if r["severity"] == "CRITICAL" and not res["passed"])
    err = sum(1 for r, res in outcomes if r["severity"] == "ERROR" and not res["passed"])
    struct_fail = any(r["dimension"] == "structural" and not res["passed"] for r, res in outcomes)

    accept_score = float(settings.get("gate_accept_score", 85.0))
    warn_score = float(settings.get("gate_warn_score", 70.0))
    reject_score = float(settings.get("gate_reject_score", 40.0))
    max_crit = int(settings.get("gate_max_critical", 0))
    max_err = int(settings.get("gate_max_error_for_accept", 0))

    if struct_fail or overall < reject_score:
        decision = "REJECT"
    elif crit > max_crit:
        decision = "QUARANTINE"
    elif overall >= accept_score and err <= max_err:
        decision = "ACCEPT"
    elif overall >= warn_score:
        decision = "ACCEPT_WITH_WARNINGS"
    else:
        decision = "QUARANTINE"

    quar_rows = {q[1] for q in quarantine}
    with connect() as conn:
        conn.execute("CREATE TEMP TABLE IF NOT EXISTS tmp_gate_rows(rn INTEGER)")
        conn.execute("DELETE FROM tmp_gate_rows")
        conn.executemany("INSERT INTO tmp_gate_rows(rn) VALUES (?)", [(r,) for r in quar_rows])
        conn.execute("UPDATE stg_station_consumption SET gate_status='QUARANTINED'"
                     " WHERE load_id=? AND row_number IN (SELECT rn FROM tmp_gate_rows)", (load_id,))
        conn.execute("DELETE FROM tmp_gate_rows")
        conn.executemany("INSERT INTO tmp_gate_rows(rn) VALUES (?)", [(r,) for r in warn_rows])
        conn.execute("UPDATE stg_station_consumption SET gate_status='WARNING'"
                     " WHERE load_id=? AND gate_status='PENDING'"
                     " AND row_number IN (SELECT rn FROM tmp_gate_rows)", (load_id,))
        conn.execute("DELETE FROM tmp_gate_rows")
        conn.execute("UPDATE stg_station_consumption SET gate_status='ACCEPTED'"
                     " WHERE load_id=? AND gate_status='PENDING'", (load_id,))

    counts = query("SELECT gate_status, COUNT(*) AS c FROM stg_station_consumption"
                   " WHERE load_id=? GROUP BY gate_status", (load_id,))
    cmap = {r["gate_status"]: r["c"] for r in counts}
    accepted = cmap.get("ACCEPTED", 0)
    warning = cmap.get("WARNING", 0)
    quarantined = cmap.get("QUARANTINED", 0)

    status_map = {"ACCEPT": "ACCEPTED", "ACCEPT_WITH_WARNINGS": "PARTIALLY_ACCEPTED",
                  "QUARANTINE": "QUARANTINED", "REJECT": "REJECTED"}
    reason = f"امتیاز کلی {overall}؛ خطای بحرانی {crit}؛ خطای عادی {err}"

    with connect() as conn:
        conn.execute("UPDATE load_loads SET accepted_count=?, rejected_count=?,"
                     " warning_count=?, status=? WHERE load_id=?",
                     (accepted + warning, quarantined, warning, status_map[decision], load_id))
        conn.execute("INSERT OR REPLACE INTO audit_quality_decisions"
                     "(load_id, score_overall, score_by_dimension_json, decision,"
                     " auto, decided_by, decided_at, reason_fa) VALUES (?,?,?,?,1,'gate',?,?)",
                     (load_id, overall, json.dumps(dim_scores, ensure_ascii=False),
                      decision, now, reason))

        load = query_one("SELECT row_count FROM load_loads WHERE load_id=?", (load_id,))
        src = float(load["row_count"] or 0)
        stg_total = float(accepted + warning + quarantined)
        for name, sv, cv in [("source_rows_vs_staging_rows", src, stg_total),
                             ("staging_rows_vs_decided_rows", stg_total, stg_total)]:
            diff = cv - sv
            pct = (diff / sv * 100) if sv else 0.0
            conn.execute("INSERT INTO audit_reconciliation(load_id, check_name,"
                         " source_value, curated_value, diff, diff_pct, passed, checked_at)"
                         " VALUES (?,?,?,?,?,?,?,?)",
                         (load_id, name, sv, cv, diff, round(pct, 4),
                          1 if abs(diff) < 1e-9 else 0, now))

    return {"load_id": load_id, "overall_score": overall,
            "dimension_scores": dim_scores, "decision": decision,
            "accepted": accepted, "warning": warning, "quarantined": quarantined,
            "critical_failures": crit, "error_failures": err, "reason_fa": reason}


def main():
    ap = argparse.ArgumentParser(description="Run the Data Quality Gate on a load")
    ap.add_argument("--load-id")
    ap.add_argument("--latest", action="store_true")
    a = ap.parse_args()

    load_id = a.load_id
    if not load_id:
        row = query_one("SELECT load_id FROM load_loads ORDER BY received_at DESC LIMIT 1")
        if not row:
            print("هیچ بارگذاری یافت نشد؛ ابتدا pipeline.ingestion را اجرا کنید.")
            return
        load_id = row["load_id"]

    result = run_gate(load_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    top = query("SELECT rule_id, severity, COUNT(*) AS c FROM qua_quarantine"
                " WHERE load_id=? GROUP BY rule_id ORDER BY c DESC LIMIT 5", (load_id,))
    if top:
        print("\nTop quarantine reasons:")
        for t in top:
            print(f"  - {t['rule_id']} [{t['severity']}]: {t['c']} rows")


if __name__ == "__main__":
    main()