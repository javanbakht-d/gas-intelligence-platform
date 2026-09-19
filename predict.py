import sqlite3
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

# خواندن داده‌ها از دیتابیس
conn = sqlite3.connect("gas_data.db")
df = pd.read_sql_query("SELECT * FROM GasOperationDailyReport", conn)
conn.close()

print("📊 داده‌ها خوانده شدند.")
print(f"   تعداد ردیف‌ها: {len(df)}")

# پیدا کردن ستون‌های عددی
numeric_cols = df.select_dtypes(include=['number']).columns.tolist()

if len(numeric_cols) == 0:
    print("⚠️ هیچ ستون عددی برای پیش‌بینی وجود ندارد!")
    exit()

# انتخاب اولین ستون عددی برای پیش‌بینی
target_col = numeric_cols[0]
print(f"\n🎯 ستون انتخاب شده برای پیش‌بینی: {target_col}")

# آماده‌سازی داده‌ها
values = df[target_col].dropna().values
X = np.arange(len(values)).reshape(-1, 1)  # ایندکس به عنوان متغیر مستقل
y = values  # مقادیر به عنوان متغیر وابسته

# ساخت مدل رگرسیون خطی
model = LinearRegression()
model.fit(X, y)

print(f"\n✅ مدل با موفقیت ساخته شد!")
print(f"   شیب خط (روند): {model.coef_[0]:.4f}")
print(f"   عرض از مبدأ: {model.intercept_:.4f}")

# پیش‌بینی ۷ روز آینده
future_days = 7
future_X = np.arange(len(values), len(values) + future_days).reshape(-1, 1)
predictions = model.predict(future_X)

print(f"\n🔮 پیش‌بینی {future_days} روز آینده برای '{target_col}':")
print("-" * 40)
for i, pred in enumerate(predictions):
    print(f"   روز +{i+1}: {pred:.2f}")

print("\n🎉 پیش‌بینی با موفقیت انجام شد!")