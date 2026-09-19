from fastapi import FastAPI
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
    result = [dict(row) for row in rows]
    return {"count": len(result), "data": result}