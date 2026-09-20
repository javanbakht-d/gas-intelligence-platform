"""
Gas Intelligence Platform - Backend API نسخه 6.0
با اندپوینت AI Chat
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_assistant import GasAIAssistant

app = FastAPI(
    title="Gas Intelligence Platform API",
    description="سامانه هوشمند پایش و تحلیل گاز",
    version="6.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

DB_FILE = "gas_data.db"
ai_assistant = GasAIAssistant()


class ChatRequest(BaseModel):
    question: str


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def safe_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except:
        return None


# === NEW: AI Chat Endpoints ===
@app.post("/api/ai/chat")
def ai_chat(request: ChatRequest):
    try:
        if not request.question or len(request.question.strip()) < 2:
            raise HTTPException(status_code=400, detail="سؤال بسیار کوتاه است")
        response = ai_assistant.ask(request.question)
        return {
            "text": response['text'], "type": response['type'],
            "intent": response['intent'], "question": response['question'],
            "data": response.get('data'),
            "visualization": response.get('visualization'),
            "timestamp": response['timestamp']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطا: {str(e)}")


@app.get("/api/ai/suggestions")
def get_ai_suggestions():
    return {
        "suggestions": [
            {"id": 1, "text": "کدام استان بیشترین مصرف را دارد؟", "category": "استان‌ها"},
            {"id": 2, "text": "پیش‌بینی ۷ روز آینده", "category": "پیش‌بینی"},
            {"id": 3, "text": "اگر دما ۵ درجه سردتر شود", "category": "سناریو"},
            {"id": 4, "text": "بهترین مدل پیش‌بینی چیست؟", "category": "مدل"},
            {"id": 5, "text": "مصرف استان تهران چقدر است؟", "category": "استان"},
            {"id": 6, "text": "ناهنجاری‌ها", "category": "ناهنجاری"},
            {"id": 7, "text": "ایستگاه‌های پرمصرف", "category": "ایستگاه"},
            {"id": 8, "text": "رابطه دما و مصرف", "category": "تحلیل"},
            {"id": 9, "text": "کل مصرف گاز", "category": "آمار"},
        ]
    }


@app.get("/")
def root():
    return {
        "message": "به پلتفرم هوشمند گاز خوش آمدید!",
        "version": "6.0.0",
        "status": "active"
    }


@app.get("/api/summary")
def get_summary():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        stats = {}
        for table in ['operation_daily_report', 'station_consumption_daily', 'production_daily']:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            stats[table] = cursor.fetchone()[0]
        cursor.execute("SELECT MAX(gregorian_date) FROM station_consumption_daily")
        last_date = cursor.fetchone()[0]
        cursor.execute("SELECT SUM(میزان_مصرف) FROM station_consumption_daily")
        total_consumption = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT نام_ایستگاه) FROM station_consumption_daily")
        unique_stations = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT استان) FROM station_consumption_daily")
        unique_provinces = cursor.fetchone()[0]
        try:
            cursor.execute("SELECT best_model, best_score FROM model_registry LIMIT 1")
            row = cursor.fetchone()
            best_model_info = {"model": row[0], "mae": safe_float(row[1])} if row else None
        except:
            best_model_info = None
        return {
            "data_counts": stats, "last_date": last_date,
            "total_consumption": safe_float(total_consumption),
            "unique_stations": unique_stations,
            "unique_provinces": unique_provinces,
            "best_model": best_model_info,
            "generated_at": datetime.now().isoformat()
        }
    finally:
        conn.close()


@app.get("/api/forecast/results")
def get_forecast_results(limit: int = Query(30, le=90)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='forecast_results'")
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="پیش‌بینی اجرا نشده")
        cursor.execute("""
            SELECT day, date, point_forecast, lower_80, upper_80, lower_95, upper_95
            FROM forecast_results ORDER BY day LIMIT ?
        """, (limit,))
        forecasts = []
        for row in cursor.fetchall():
            forecasts.append({
                "day": row[0], "date": row[1],
                "point_forecast": safe_float(row[2]),
                "lower_80": safe_float(row[3]), "upper_80": safe_float(row[4]),
                "lower_95": safe_float(row[5]), "upper_95": safe_float(row[6])
            })
        return {"count": len(forecasts), "data": forecasts}
    finally:
        conn.close()


@app.get("/api/forecast/benchmarks")
def get_model_benchmarks():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='model_benchmarks'")
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="بنچمارک اجرا نشده")
        cursor.execute("""
            SELECT model_name, MAE, RMSE, sMAPE, WAPE, validation_windows, is_best
            FROM model_benchmarks ORDER BY MAE
        """)
        benchmarks = []
        for row in cursor.fetchall():
            benchmarks.append({
                "model_name": row[0], "MAE": safe_float(row[1]),
                "RMSE": safe_float(row[2]), "sMAPE": safe_float(row[3]),
                "WAPE": safe_float(row[4]), "validation_windows": row[5],
                "is_best": bool(row[6])
            })
        cursor.execute("SELECT best_model, best_score, metric, training_date FROM model_registry LIMIT 1")
        registry = cursor.fetchone()
        best_model = {
            "name": registry[0] if registry else None,
            "score": safe_float(registry[1]) if registry else None,
            "metric": registry[2] if registry else None,
            "training_date": registry[3] if registry else None,
        }
        return {"count": len(benchmarks), "best_model": best_model, "data": benchmarks}
    finally:
        conn.close()


@app.get("/api/temperature/summary")
def get_temperature_summary():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='temperature_impact_summary'")
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="تحلیل دما اجرا نشده")
        cursor.execute("SELECT overall_correlation, interpretation, direction, total_records, generated_at FROM temperature_impact_summary")
        row = cursor.fetchone()
        elasticity = None
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='temperature_elasticity'")
        if cursor.fetchone():
            cursor.execute("SELECT overall_elasticity, interpretation FROM temperature_elasticity")
            e_row = cursor.fetchone()
            if e_row:
                elasticity = {"value": safe_float(e_row[0]), "interpretation": e_row[1]}
        outlier_stats = None
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='temperature_outlier_stats'")
        if cursor.fetchone():
            cursor.execute("SELECT total_with_temp, outliers_count, outliers_pct, temp_min_valid, temp_max_valid FROM temperature_outlier_stats")
            o_row = cursor.fetchone()
            if o_row:
                outlier_stats = {
                    "total_with_temp": o_row[0], "outliers_count": o_row[1],
                    "outliers_pct": safe_float(o_row[2]),
                    "temp_min_valid": safe_float(o_row[3]), "temp_max_valid": safe_float(o_row[4])
                }
        return {
            "correlation": {"overall": safe_float(row[0]), "interpretation": row[1], "direction": row[2], "total_records": row[3]},
            "elasticity": elasticity, "outlier_stats": outlier_stats, "generated_at": row[4]
        }
    finally:
        conn.close()


@app.get("/api/temperature/bins")
def get_temperature_bins():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='temperature_bins'")
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="بازه‌های دمایی محاسبه نشده")
        cursor.execute("""
            SELECT temp_range, temp_start, temp_end, temp_mid, record_count,
                   avg_consumption, min_consumption, max_consumption, std_consumption
            FROM temperature_bins ORDER BY temp_mid
        """)
        bins = []
        for row in cursor.fetchall():
            bins.append({
                "temp_range": row[0], "temp_start": row[1], "temp_end": row[2],
                "temp_mid": safe_float(row[3]), "record_count": row[4],
                "avg_consumption": safe_float(row[5]), "min_consumption": safe_float(row[6]),
                "max_consumption": safe_float(row[7]), "std_consumption": safe_float(row[8])
            })
        return {"count": len(bins), "data": bins}
    finally:
        conn.close()


@app.get("/api/temperature/by-province")
def get_temperature_by_province():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='temperature_by_province'")
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="تحلیل استانی انجام نشده")
        cursor.execute("""
            SELECT province, correlation, record_count, avg_temperature, avg_consumption
            FROM temperature_by_province ORDER BY ABS(correlation) DESC
        """)
        provinces = []
        for row in cursor.fetchall():
            provinces.append({
                "province": row[0], "correlation": safe_float(row[1]),
                "record_count": row[2], "avg_temperature": safe_float(row[3]),
                "avg_consumption": safe_float(row[4])
            })
        return {"count": len(provinces), "data": provinces}
    finally:
        conn.close()


@app.get("/api/scenarios/summary")
def get_scenarios_summary():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scenario_summary'")
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="سناریو اجرا نشده")
        cursor.execute("""
            SELECT scenario_name, temp_change, description,
                   total_base_consumption, total_new_consumption,
                   total_diff, change_pct, generated_at
            FROM scenario_summary ORDER BY temp_change
        """)
        scenarios = []
        for row in cursor.fetchall():
            scenarios.append({
                "scenario_name": row[0], "temp_change": row[1], "description": row[2],
                "total_base_consumption": safe_float(row[3]),
                "total_new_consumption": safe_float(row[4]),
                "total_diff": safe_float(row[5]), "change_pct": safe_float(row[6]),
                "generated_at": row[7]
            })
        return {"count": len(scenarios), "data": scenarios}
    finally:
        conn.close()


@app.get("/api/scenarios/insights")
def get_scenario_insights():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scenario_insights'")
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="بینشی موجود نیست")
        cursor.execute("SELECT type, province, consumption_type, insight, severity FROM scenario_insights")
        insights = []
        for row in cursor.fetchall():
            insights.append({
                "type": row[0], "province": row[1],
                "consumption_type": row[2], "insight": row[3], "severity": row[4]
            })
        return {"count": len(insights), "data": insights}
    finally:
        conn.close()


@app.get("/api/scenarios/simulate")
def simulate_scenario(temp_change: float = Query(0, ge=-20, le=20)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT overall_elasticity FROM temperature_elasticity")
        row = cursor.fetchone()
        overall_elasticity = float(row[0]) if row else -0.2
        cursor.execute("SELECT province, elasticity FROM elasticity_by_province")
        province_elasticity = {row[0]: float(row[1]) for row in cursor.fetchall()}
        cursor.execute("""
            SELECT استان, SUM(میزان_مصرف) as total_consumption,
                   AVG(COALESCE(دمای_گاز_ساعت_6_صبح___نقطه_1, دمای_گاز_ساعت_18)) as avg_temp
            FROM station_consumption_daily
            WHERE میزان_مصرف IS NOT NULL AND gregorian_date >= date('now', '-30 days')
            GROUP BY استان HAVING total_consumption > 0 AND avg_temp > 0
        """)
        results = []
        total_base = 0
        total_new = 0
        for row in cursor.fetchall():
            province, base, avg_temp = row[0], float(row[1]), float(row[2])
            elasticity = province_elasticity.get(province, overall_elasticity)
            temp_change_pct = (temp_change / avg_temp) * 100
            consumption_change_pct = elasticity * temp_change_pct
            new = base * (1 + consumption_change_pct / 100)
            diff = new - base
            total_base += base
            total_new += new
            results.append({"province": province, "base": base, "new": new, "diff": diff, "change_pct": consumption_change_pct})
        results = sorted(results, key=lambda x: abs(x['diff']), reverse=True)
        return {
            "temp_change": temp_change,
            "total_base": total_base, "total_new": total_new,
            "total_diff": total_new - total_base,
            "total_change_pct": ((total_new - total_base) / total_base * 100) if total_base > 0 else 0,
            "province_count": len(results), "data": results[:15]
        }
    finally:
        conn.close()


@app.get("/api/consumption/by-province")
def get_consumption_by_province():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT استان, COUNT(*) as record_count, COUNT(DISTINCT نام_ایستگاه) as station_count,
                   AVG(میزان_مصرف) as avg_consumption, SUM(میزان_مصرف) as total_consumption
            FROM station_consumption_daily WHERE استان IS NOT NULL
            GROUP BY استان ORDER BY total_consumption DESC
        """)
        provinces = []
        for row in cursor.fetchall():
            provinces.append({
                "province": row[0], "record_count": row[1], "station_count": row[2],
                "avg_consumption": safe_float(row[3]), "total_consumption": safe_float(row[4])
            })
        return {"count": len(provinces), "data": provinces}
    finally:
        conn.close()


@app.get("/api/consumption/trend")
def get_consumption_trend(days: int = Query(30, le=365), province: Optional[str] = None):
    conn = get_db_connection()
    try:
        query = """
            SELECT gregorian_date, shamsi_year, shamsi_month, shamsi_day,
                   SUM(میزان_مصرف) as daily_consumption, COUNT(*) as record_count
            FROM station_consumption_daily WHERE gregorian_date IS NOT NULL
        """
        params = []
        if province:
            query += " AND استان = ?"
            params.append(province)
        query += " GROUP BY gregorian_date, shamsi_year, shamsi_month, shamsi_day ORDER BY gregorian_date DESC LIMIT ?"
        params.append(days)
        cursor = conn.cursor()
        cursor.execute(query, params)
        trend = []
        for row in cursor.fetchall():
            trend.append({
                "gregorian_date": row[0],
                "shamsi_date": f"{row[1]}/{row[2]:02d}/{row[3]:02d}",
                "consumption": safe_float(row[4]), "record_count": row[5]
            })
        trend.reverse()
        return {"days": days, "data": trend}
    finally:
        conn.close()


@app.get("/api/anomalies")
def get_anomalies(threshold: float = Query(100.0), limit: int = Query(100, le=1000)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT gregorian_date, shamsi_year, shamsi_month, shamsi_day, نام_ایستگاه, استان,
                   دمای_گاز_ساعت_6_صبح___نقطه_1, دمای_گاز_ساعت_6_صبح___نقطه_2,
                   اختلاف_دمای_ساعت_6_صبح
            FROM station_consumption_daily
            WHERE اختلاف_دمای_ساعت_6_صبح IS NOT NULL AND ABS(اختلاف_دمای_ساعت_6_صبح) > ?
            ORDER BY ABS(اختلاف_دمای_ساعت_6_صبح) DESC LIMIT ?
        """, (threshold, limit))
        anomalies = []
        for row in cursor.fetchall():
            diff = safe_float(row[8])
            severity = "Critical" if abs(diff) > 500 else "High" if abs(diff) > 200 else "Medium"
            anomalies.append({
                "severity": severity, "gregorian_date": row[0],
                "shamsi_date": f"{row[1]}/{row[2]:02d}/{row[3]:02d}",
                "station": row[4], "province": row[5],
                "temp_point_1": safe_float(row[6]), "temp_point_2": safe_float(row[7]),
                "temperature_diff": diff
            })
        return {"count": len(anomalies), "data": anomalies}
    finally:
        conn.close()


@app.get("/api/filters")
def get_filters():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT استان FROM station_consumption_daily WHERE استان IS NOT NULL ORDER BY استان")
        provinces = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT نوع_مصرف FROM station_consumption_daily WHERE نوع_مصرف IS NOT NULL ORDER BY نوع_مصرف")
        consumption_types = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT shamsi_year FROM station_consumption_daily WHERE shamsi_year IS NOT NULL ORDER BY shamsi_year")
        years = [row[0] for row in cursor.fetchall()]
        return {"provinces": provinces, "consumption_types": consumption_types, "years": years}
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)