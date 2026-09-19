from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

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

@app.get("/api/predict")
def predict_future(days: int = Query(7, description="تعداد روزهای آینده برای پیش‌بینی")):
    conn = sqlite3.connect("gas_data.db")
    df = pd.read_sql_query("SELECT * FROM GasOperationDailyReport", conn)
    conn.close()
    
    # پیدا کردن ستون‌های عددی
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    
    if len(numeric_cols) == 0:
        return {"error": "هیچ ستون عددی برای پیش‌بینی وجود ندارد"}
    
    # انتخاب اولین ستون به عنوان هدف
    target_col = numeric_cols[0]
    
    # استفاده از سایر ستون‌های عددی به عنوان ویژگی
    feature_cols = numeric_cols[1:4]  # حداکثر ۳ ویژگی
    
    if len(feature_cols) == 0:
        # اگر ستون دیگری نیست، از ایندکس استفاده کن
        X = np.arange(len(df)).reshape(-1, 1)
    else:
        X = df[feature_cols].fillna(0).values
    
    y = df[target_col].fillna(0).values
    
    # ساخت مدل
    model = LinearRegression()
    model.fit(X, y)
    
    # پیش‌بینی با استفاده از آخرین مقادیر
    last_values = X[-1].reshape(1, -1)
    predictions_list = []
    
    for i in range(days):
        pred = model.predict(last_values)[0]
        predictions_list.append({"day": i+1, "value": float(pred)})
    
    return {
        "target_column": target_col,
        "feature_columns": feature_cols,
        "days": days,
        "predictions": predictions_list
    }