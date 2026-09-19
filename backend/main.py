from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import sqlite3

app = FastAPI(title="Gas Intelligence Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "به پلتفرم هوشمند گاز خوش آمدید!"}

@app.get("/api/daily-report")
def get_daily_report(limit: int = 10):
    conn = sqlite3.connect("gas_data.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM GasOperationDailyReport LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return {"count": len(rows), "data": [dict(r) for r in rows]}

@app.get("/api/by-date")
def get_by_date(date: str = Query(..., description="تاریخ شمسی مثل 1405/06/10")):
    conn = sqlite3.connect("gas_data.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(GasOperationDailyReport)")
    columns = [col[1] for col in cursor.fetchall()]
    
    date_col = None
    for col in columns:
        if "date" in col.lower() or "تاریخ" in col:
            date_col = col
            break
    
    if not date_col:
        conn.close()
        return {"error": "ستون تاریخ پیدا نشد", "columns": columns}
    
    cursor.execute(f"SELECT * FROM GasOperationDailyReport WHERE [{date_col}] LIKE ?", (f"%{date}%",))
    rows = cursor.fetchall()
    conn.close()
    return {"date": date, "count": len(rows), "data": [dict(r) for r in rows]}

@app.get("/api/trend")
def get_trend(limit: int = 30):
    conn = sqlite3.connect("gas_data.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM GasOperationDailyReport ORDER BY rowid DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return {"count": len(rows), "data": [dict(r) for r in rows]}