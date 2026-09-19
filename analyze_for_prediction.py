import sqlite3
import pandas as pd

# خواندن داده‌ها از دیتابیس
conn = sqlite3.connect("gas_data.db")
df = pd.read_sql_query("SELECT * FROM GasOperationDailyReport", conn)
conn.close()

print(f"📊 تعداد کل ردیف‌ها: {len(df)}")
print(f"📋 تعداد کل ستون‌ها: {len(df.columns)}")
print("\n🔢 ستون‌های عددی (مناسب برای پیش‌بینی):")
print("-" * 50)

numeric_cols = df.select_dtypes(include=['number']).columns.tolist()

if len(numeric_cols) == 0:
    print("⚠️ هیچ ستون عددی پیدا نشد!")
else:
    for col in numeric_cols:
        print(f"  ✅ {col}")
        print(f"     میانگین: {df[col].mean():.2f}")
        print(f"     کمینه: {df[col].min():.2f}")
        print(f"     بیشینه: {df[col].max():.2f}")
        print()

print(f"\n📅 ستون‌های غیر عددی:")
non_numeric = [c for c in df.columns if c not in numeric_cols]
for col in non_numeric:
    print(f"  - {col}")