import pandas as pd

file_name = "گزارش روزانه تولید و مصرف و ایستگاهها.xlsx"
xls = pd.ExcelFile(file_name)

print("✅ فایل اکسل با موفقیت باز شد!")
print("📋 نام شیت‌های موجود:")
for sheet in xls.sheet_names:
    print(f"  - {sheet}")