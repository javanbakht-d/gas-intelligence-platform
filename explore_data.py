import pandas as pd

file_name = "data/گزارش روزانه تولید و مصرف و ایستگاهها.xlsx"
xls = pd.ExcelFile(file_name)

with open("data_info.txt", "w", encoding="utf-8") as f:
    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)
        f.write("=" * 50 + "\n")
        f.write(f"شیت: {sheet}\n")
        f.write(f"تعداد ردیف‌ها: {len(df)}\n")
        f.write(f"تعداد ستون‌ها: {len(df.columns)}\n")
        f.write(f"نام ستون‌ها: {', '.join(str(c) for c in df.columns)}\n")

print("DONE! Please open data_info.txt")