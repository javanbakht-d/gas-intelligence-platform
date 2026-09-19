import pandas as pd
import sqlite3

# مسیر فایل اکسل و دیتابیس
excel_file = "data/گزارش روزانه تولید و مصرف و ایستگاهها.xlsx"
db_file = "gas_data.db"

print("⏳ در حال خواندن فایل اکسل... (ممکن است ۱ تا ۲ دقیقه طول بکشد)")
xls = pd.ExcelFile(excel_file)

# اتصال به دیتابیس SQLite
conn = sqlite3.connect(db_file)

for sheet in xls.sheet_names:
    print(f"📊 در حال پردازش و ذخیره شیت: {sheet}")
    df = pd.read_excel(xls, sheet_name=sheet)
    
    # تمیز کردن نام ستون‌ها
    df.columns = [str(c).strip() for c in df.columns]
    
    # ذخیره در دیتابیس
    df.to_sql(sheet, conn, if_exists="replace", index=False)

conn.close()
print("🎉 تمام داده‌ها با موفقیت به دیتابیس SQLite منتقل شدند!")