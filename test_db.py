import sqlite3

conn = sqlite3.connect("gas_data.db")
cursor = conn.cursor()

# گرفتن لیست جدول‌ها
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

print("📋 جدول‌های موجود در دیتابیس:")
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM '{table[0]}'")
    count = cursor.fetchone()[0]
    print(f"  - {table[0]}: {count} ردیف")

conn.close()
print("\n✅ تست دیتابیس با موفقیت انجام شد!")