# Data / AI / Forecast Architecture Audit
**Project:** gas-intelligence-platform  
**Auditor:** Principal Data Architect  
**Date:** 2026-09-23  
**Commit baseline:** `3fd19d3` (main)  
**Status:** Phase 1 — Inspection & Gap Analysis (NO code modified)

---

## Executive Summary

The repository is a working **single-user analytical prototype** that reads one Excel workbook, materializes a handful of pre-computed analytical tables into a local SQLite file, and exposes them through a FastAPI service to a single-page HTML/JS frontend. The platform is **not** a continuously updatable, governed, AI-ready data platform. The gaps between the current state and the target state (Raw → Gate → Quarantine → Curated → Feature Store → Forecast → Grounded AI) are large but well-defined.

Legend used throughout this document:
- **[FACT]** — Verified against an actual file in the repository.
- **[ASSUMPTION]** — Reasonable inference not yet confirmed; flagged for the user.
- **[RISK]** — A condition that could cause incorrect results, data loss, or security exposure.
- **[RECOMMENDATION]** — A proposed action; never implemented yet.

---

## 1. Data Architecture

### 1.1 Current data sources

**[FACT]** There is exactly one source file:
- `data/گزارش روزانه تولید و مصرف و ایستگاهها.xlsx` — a multi-sheet workbook.

Confirmed sheets read by `build_database.py`:
- `GasOperationDailyReport` → table `operation_daily_report`
- `GasOperationDailyStationReport` → table `station_consumption_daily`
- `ViewProdDailyForNaft` → table `production_daily`

**[FACT]** No API source, no streaming source, no second file, no weather feed, no calendar feed, no master-data file is referenced anywhere in the codebase.

**[RISK]** Single point of failure. Any corruption, rename, or schema change of the Excel file breaks every downstream pipeline.

### 1.2 Current tables (19 tables observed via user-supplied `check_schema.py`)

| Layer | Tables | Purpose |
|---|---|---|
| Raw-ish | `operation_daily_report`, `station_consumption_daily`, `production_daily` | One-row-per-source-row copy of the workbook (with normalization and date features added) |
| Metadata | `metadata` | Build-time key/value |
| Model registry | `model_registry`, `model_benchmarks` | Single best model + benchmark rows |
| Forecast | `forecast_results` | 30 rows of pre-computed autoregressive forecast |
| Temperature | `temperature_impact_summary`, `temperature_outlier_stats`, `temperature_by_province`, `temperature_by_season`, `temperature_by_type`, `temperature_bins`, `temperature_elasticity`, `elasticity_by_province`, `temperature_thresholds` | Pre-computed analytical outputs |
| Scenario | `scenario_results`, `scenario_summary`, `scenario_insights` | Pre-computed elasticity scenarios |

### 1.3 Current raw / processed structure

**[FACT]** There is **no physical separation** between raw and curated data. `build_database.py` applies normalization (Persian character folding, date parsing, derived columns like `اختلاف_دمای_ساعت_6_صبح`) and writes the result directly into the analytical tables. The original Excel row values are not preserved in an immutable form.

**[RISK]** Raw values are destroyed on every rebuild. There is no way to replay, audit, or revert a single bad ingestion run.

### 1.4 Current ingestion workflow

1. User runs `build_database.py` (or the older `load_to_db.py`).
2. Script reads the workbook, normalizes text, parses Shamsi dates, adds derived columns.
3. Tables are written with `if_exists='replace'` — full destructive overwrite.
4. User then runs `forecasting_engine.py`, `temperature_analysis.py`, `scenario_analysis.py`, `data_quality_assessment.py` to populate analytical tables.
5. User runs `uvicorn backend.main:app` and opens `frontend/index.html`.

**[RISK]** There is no orchestrator, no scheduler, no dependency graph. Running the scripts in the wrong order (or skipping one) leaves stale analytical tables that the UI will happily display as current truth.

### 1.5 Current database architecture

**[FACT]** Single local SQLite file `gas_data.db` opened via `sqlite3.connect(DB_FILE)` in every FastAPI endpoint and in every analysis script. No connection pool, no abstraction layer, no migrations.

**[RISK]** SQLite is acceptable for a single-user prototype but is a hard blocker for: concurrent ingestion + serving, row-level locking during rebuilds, multi-user access, production-grade audit logs, and schema versioning.

---

## 2. Data Quality

### 2.1 Existing validation rules (in `data_quality_assessment.py`)

The current "quality report" is a **post-hoc descriptive report** written to `DATA_QUALITY_REPORT.md` and `data_quality_metrics.json`. It is not a gate. Specifically:

| Dimension | Implementation | Verdict |
|---|---|---|
| Completeness | `missing_pct` per column | Report only |
| Outliers | IQR × 3 per numeric column | Report only |
| Zeros / negatives | Counted per column | Report only |
| Date validity | Parsed in `build_database.py` via regex, fallback to None | Silent drop into NULLs |
| Text normalization | Persian ye/ke folding, half-space folding in `build_database.py` | Applied destructively |
| Duplicates | Not checked | **[RISK]** |
| Referential integrity | None — province/city/station strings are not cross-checked | **[RISK]** |
| Cross-field rules | None (no min≤max, no pressure sanity, no date coherence) | **[RISK]** |
| Temporal quality | Basic year/month count in report | No gap / future-date detection |
| Distribution drift | Not implemented | **[RISK]** |

### 2.2 Existing quality scoring

`analyze_column` in `data_quality_assessment.py` computes a 0–100 score by subtracting ad-hoc penalties:
- `-0.5 × missing_pct` (capped at 50)
- `-2 × extreme_outliers_pct` (capped at 20)
- `-20` if temperature/pressure max > 100 or min < -50
- `-5` for Persian/half-space issues

**[RISK]** This is a magic number. The weights are hardcoded, not configurable, not weighted by column importance, and not exposed with provenance. The UI `quality` page shows it without explaining how it was computed.

### 2.3 Specific dangerous behaviors

- **[FACT]** `build_database.py` never rejects a row. Any invalid row lands in the analytical tables.
- **[FACT]** `data_quality_assessment.py` reports outliers like "دمای ۱۲۷,۷۳۷ درجه" but does not remove them from the database.
- **[FACT]** The outlier filter in `temperature_analysis.py` uses hardcoded `TEMP_MIN_VALID = -30` / `TEMP_MAX_VALID = 100`. These thresholds live inside one analysis script, not in a shared rules configuration.
- **[RISK]** `load_to_db.py` still exists in the repo and writes raw sheets to SQLite **without any normalization**. A user running this script will silently corrupt the curated schema assumed by every downstream analysis.

### 2.4 Missing handling / zero / negative handling

- **[FACT]** No unified policy. `0` is counted, not interpreted as missing. Negative values are counted, not flagged by domain. Units are never documented.
- **[RISK]** Rule 66 of your prompt is already relevant: product code `420` is gas condensate (`میعانات گازی`), not natural gas. The current backend endpoint `/api/production/summary` sums `میزان_تولید` across all products and presents it as "total production" without this caveat — a semantic hazard the UI will happily propagate.

---

## 3. Forecasting

### 3.1 Current models (in `forecasting_engine.py`)

- Naive, Seasonal Naive (period=7), Moving Average (window=7)
- Linear Regression, Random Forest (n_estimators=50), XGBoost (n_estimators=50, max_depth=5) — the last two optional

**[FACT]** Only **one target** is modeled: `SUM(میزان_مصرف)` aggregated at the **national daily** level. Province / station / consumption-type forecasts do not exist.

### 3.2 Feature engineering

- Temporal: `day_of_week`, `month`, `day_of_year`, `is_weekend`, `season`
- Lags: 1, 2, 3, 7, 14, 30
- Rolling: mean/std over 3, 7, 14, 30 (shifted by 1 — correct)
- Growth: `pct_change(1)`, `pct_change(7)`
- `[FACT]` Temperature and pressure are available in the aggregation query (`میانگین_دما`, `میانگین_فشار`) but are **not** included in `X_features` because `create_features` only keeps lags/rolling/temporal columns and the target. **[ASSUMPTION — needs direct source review]** This means the forecast does not actually use weather as a regressor.

### 3.3 Training / validation

- Walk-forward with `n_windows=3`, `test_size=14`, `horizon=7` — this is legitimate time-series validation.
- Only 3 windows → small validation sample. **[RISK]** Metric estimates have high variance.
- No hyperparameter search; fixed defaults.
- No leakage tests automated.

### 3.4 Horizons & uncertainty

- Fixed horizon of 30 days, autoregressive (each prediction fed back as the next lag).
- Prediction intervals computed as `± 1.28 × residual_std × (1 + 0.05 × (day-1))` for 80% and `± 1.96 × residual_std × (1 + 0.05 × (day-1))` for 95%.
- **[RISK]** This is not a principled prediction interval. It assumes homoskedastic Gaussian residuals, uses in-sample residuals (not out-of-sample), and the "uncertainty grows 5% per day" factor is an ad-hoc multiplier, not derived from the model.
- **[RISK]** The UI labels these as "بازه ۹۵٪" — the code correctly calls them prediction intervals in variable names (`lower_95`/`upper_95`) but the frontend copy must be checked to ensure it doesn't say "اطمینان" (confidence).

### 3.5 Model registry

- Single-row `model_registry` table overwritten on every run: `best_model`, `best_score`, `metric='MAE'`, `training_date`, `forecast_horizon`.
- No versioning, no feature set version, no artifact storage, no promotion logic, no champion/challenger.
- **[RISK]** Every retraining silently replaces the champion. No rollback possible.

---

## 4. AI Assistant

### 4.1 Architecture (`ai_assistant.py`)

**[FACT]** `GasAIAssistant` is a **rule-based dispatcher, not an LLM**. There is no external model, no embedding, no retrieval, no RAG.

Pipeline:
1. `_clean_text`: strip, collapse whitespace, fold Persian digits to ASCII.
2. `_detect_intent`: iterate `self.intent_patterns` (regex list), return first match.
3. `_extract_entities`: iterate a hard-coded list of 13 province names; extract the first integer via regex.
4. `handler_map` dispatches to a method that runs a hard-coded SQL query.
5. Response is a hand-crafted Persian string with emoji.

### 4.2 Intent detection / query generation

- 9 intents: `top_consumption_provinces`, `province_consumption`, `forecast`, `temperature_scenario`, `anomalies`, `top_stations`, `model_performance`, `temperature_correlation`, `total_consumption`.
- **[RISK]** Regex-based intent detection is brittle. "مصرف تهران چقدر بوده" matches `province_consumption`; "مصرف تهران در ۷ روز اخیر" may not; "تهران چقدر مصرف دارد" may not.
- **[RISK]** Province extraction uses a static list of 13 provinces. Real data contains more. Any province not on the list is silently dropped.

### 4.3 SQL access / tools / context

- **[FACT]** SQL is written inline in each handler. There is no tool catalog, no allowlisted views, no SQL validator.
- **[FACT]** `conversation_context` is a plain dict holding only the last question/intent/entities. No multi-turn state.
- **[RISK]** No Text-to-SQL. No Text-to-Semantic-Query. The assistant cannot answer questions that don't match one of the 9 hard-coded intents.

### 4.4 Hallucination controls / numerical grounding

- **[FACT]** Numerical grounding is real: every handler runs a real SQL query and formats the result. The assistant does not invent numbers.
- **[RISK]** However, the assistant will happily return a result even when the underlying data is stale, missing, or low-quality. There is no `insufficient_data` branch, no freshness check, no quality check.
- **[RISK]** The `_handle_unknown` fallback is a canned menu, not an abstention.

### 4.5 Visualization generation

- **[FACT]** `response.get('visualization')` is referenced by the backend but the `ai_assistant.py` code shown does not actually populate it in the handlers. **[ASSUMPTION — needs handler-by-handler review]** that some handlers return chart metadata; otherwise the frontend's chart-on-response feature is inert.

---

## 5. Operations

### 5.1 Data refresh

- **[FACT]** Manual only. The user runs scripts from a terminal.
- No scheduler (no cron, no Airflow, no Prefect, no Dagster, no `apscheduler`).
- No trigger on file change.

### 5.2 Retraining

- **[FACT]** Manual. The user re-runs `forecasting_engine.py`.
- No drift-triggered retraining, no schedule, no staleness check.

### 5.3 Monitoring / logging / auditability

- **[FACT]** `print()` statements are the only logging. No structured logs, no request IDs, no load IDs, no correlation IDs.
- No audit table. No lineage. No "who ran which script when with which file" record.
- `metadata` table stores only `last_build_time`, `source_file`, `sheets_count`, `version` — all static strings, no per-load identity.

### 5.4 Error handling

- `backend/main.py` endpoints wrap calls in `try/finally` to close the DB connection, but return generic HTTP 500 with the Python exception string leaked to the client: `detail=f"خطا: {str(e)}"`.
- **[RISK]** Exception messages can leak file paths, SQL fragments, or stack hints.

---

## 6. Security

| Control | Current state | Verdict |
|---|---|---|
| CORS | `allow_origins=["*"]`, credentials allowed | **[RISK]** Wide open |
| Authentication | None | **[RISK]** |
| Authorization | None | **[RISK]** |
| Secret management | No secrets present yet, no `.env` loader | OK today, fragile tomorrow |
| SQL safety | Most queries are static strings; parameterized where user input exists. However, some queries build column/table names via string concat (safe only because inputs are internal). | Moderate |
| Input validation | Pydantic `ChatRequest` validates only that `question` is a string. Length check (`< 2`) only. | Weak |
| File upload | **Not implemented** — no upload endpoint exists. | N/A |
| Rate limiting | None | **[RISK]** |
| Error leakage | Python exception strings returned in HTTP 500 | **[RISK]** |

---

## 7. Verification of the specific findings listed in §2 of the prompt

| Prompt claim | Verified? | Source |
|---|---|---|
| Uses `sqlite3` | ✅ FACT | `backend/main.py`, every analysis script |
| Local DB file | ✅ FACT | `DB_FILE = "gas_data.db"` |
| Instantiates `GasAIAssistant` directly | ✅ FACT | `ai_assistant = GasAIAssistant()` at module scope |
| Exposes an AI chat endpoint | ✅ FACT | `POST /api/ai/chat` |
| Exposes precomputed forecasting results | ✅ FACT | `GET /api/forecast/results` reads `forecast_results` table |
| Exposes precomputed temperature analysis | ✅ FACT | `GET /api/temperature/summary`, `/bins`, `/by-province` |
| Exposes precomputed scenarios | ✅ FACT | `GET /api/scenarios/summary`, `/insights` |
| Exposes a data quality JSON report | ✅ FACT | `GET /api/quality/report` reads `data_quality_metrics.json` |
| Permissive CORS | ✅ FACT | `allow_origins=["*"]` |
| Hard-coded / default analytical behavior | ✅ FACT | Intent patterns, province list, scenario temp deltas, anomaly threshold=100 |
| Scenario uses stored elasticity | ✅ FACT | `/api/scenarios/simulate` reads `temperature_elasticity` and `elasticity_by_province` |
| Fixed recent-data window in scenario | ✅ FACT | `gregorian_date >= date('now', '-30 days')` hardcoded in both script and endpoint |
| Elasticity fallback to `-0.2` | ✅ FACT | `scenario_analysis.py`: `overall_elasticity = -0.2  # مقدار پیش‌فرض معقول` |

---

## 8. Top risks ranked

1. **No data lifecycle, no raw/curated separation** — every rebuild is destructive.
2. **Quality report is not a gate** — bad rows enter analytical tables silently.
3. **No lineage, no load id, no audit** — results cannot be reproduced or investigated.
4. **AI Assistant is rule-based** — cannot answer novel questions, cannot abstain, cannot cite.
5. **Single national forecast target** — no hierarchical, no sub-national, no reconciliation.
6. **Ad-hoc prediction intervals** — statistically unsound.
7. **No master data** — province / station / refinery / product names are raw strings; aliases will fragment analytics silently.
8. **Open CORS + no auth + no rate limit** — trivially exploitable once exposed beyond localhost.
9. **Exception leakage in HTTP 500** — information disclosure.
10. **`load_to_db.py` still in repo** — an accidental run destroys curated schema.

---

## 9. Recommendations (high level, no implementation yet)

- **R1.** Freeze the repository; create branch `feat/data-foundation-upgrade`.
- **R2.** Introduce an ingestion framework with load_id, file_hash, source_id, row fingerprints, idempotent upserts.
- **R3.** Split the DB into logical schemas: `raw`, `staging`, `quarantine`, `master`, `curated`, `analytics`, `features`, `forecast`, `ai`, `audit`.
- **R4.** Replace `data_quality_assessment.py` report with a configurable Data Quality Gate that produces ACCEPT / ACCEPT_WITH_WARNINGS / QUARANTINE / REJECT decisions.
- **R5.** Build a master-data layer for Province, City, Station, Refinery, Product, ConsumptionType with alias mapping and approval workflow.
- **R6.** Replace the rule-based AI Assistant with a semantic-layer-driven agent that calls explicit analytical tools, returns provenance, and abstains when data is insufficient or stale.
- **R7.** Rebuild the forecasting engine with a feature store, leakage tests, walk-forward evaluation across multiple targets, principled prediction intervals, and a champion/challenger registry.
- **R8.** Add a data freshness service and a Data Refresh Center API/UI.
- **R9.** Harden security: restrictive CORS, no exception leakage, input validation, rate limiting, and (later) authentication.
- **R10.** Evaluate PostgreSQL migration; keep SQLite only if single-user constraints are permanent.

---

## 10. Milestone alignment with the prompt

The prompt defines 12 milestones. This audit covers **Milestone 1** (audit + architecture). The remaining 11 milestones must not begin until the user reviews this audit and confirms:

1. Which risks are accepted as-is.
2. Which recommendations are prioritized.
3. Whether SQLite is to be retained or migrated.
4. Which new data domains (weather, calendar, network, etc.) have real sources available versus schema-only stubs.

---

## 11. Files inspected (by URL against `main` @ `3fd19d3`)

- `backend/main.py` ✅
- `ai_assistant.py` ✅
- `build_database.py` ✅
- `load_to_db.py` ✅
- `forecasting_engine.py` ✅
- `temperature_analysis.py` ✅
- `scenario_analysis.py` ✅
- `data_quality_assessment.py` ✅
- Directory layout via GitHub file listing ✅
- Table list via user-supplied `check_schema.py` output ✅

**Not yet inspected** (will be inspected in Phase 2 if needed):
- `frontend/index.html` (known structure from prior conversation, not re-read in this audit)
- `analyze_for_prediction.py`, `data_inspection.py`, `explore_data.py`, `predict.py`, `generate_beautiful_report.py`, `generate_data_dictionary.py`, `test.py`, `test_db.py`
- `DATA_DICTIONARY.md`, `DATA_QUALITY_REPORT.md`, `MISSING_STRATEGY.json`, `requirements.txt`
- `docs/*` (design-system, frontend-architecture, frontend-ui-ux-audit)
- `notebooks/*`
- `data/*` (the actual Excel workbook — cannot inspect contents without local access or user upload)
- `data_quality_metrics.json`, `data_quality_report.json` (generated artifacts)
- `.gitignore`

---

## 12. Next step

**Do not modify any production code yet.** Awaiting user confirmation to proceed to Milestone 2 (Ingestion + Raw/Staging + Quality Gate).