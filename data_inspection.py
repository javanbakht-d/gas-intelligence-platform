"""
Phase 1: Data Inspection & Profiling Pipeline
سامانه پایش هوشمند گاز - بررسی کیفیت داده‌ها
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
import jdatetime

# === Configuration ===
EXCEL_FILE = "data/گزارش روزانه تولید و مصرف و ایستگاهها.xlsx"
OUTPUT_REPORT = "data_quality_report.json"

def load_excel_sheets(file_path):
    """بارگذاری همه شیت‌های فایل اکسل"""
    print(f"📂 در حال خواندن فایل: {file_path}")
    
    if not Path(file_path).exists():
        print(f"❌ فایل یافت نشد: {file_path}")
        return None
    
    xls = pd.ExcelFile(file_path)
    print(f"✅ شیت‌های یافت شده: {xls.sheet_names}")
    
    sheets = {}
    for sheet_name in xls.sheet_names:
        print(f"\n📊 خواندن شیت: {sheet_name}")
        df = pd.read_excel(xls, sheet_name=sheet_name)
        # تمیز کردن نام ستون‌ها
        df.columns = [str(c).strip() for c in df.columns]
        sheets[sheet_name] = df
        print(f"   - ردیف‌ها: {len(df):,}")
        print(f"   - ستون‌ها: {len(df.columns)}")
    
    return sheets


def profile_column(series, col_name):
    """بررسی یک ستون"""
    profile = {
        "column_name": col_name,
        "dtype": str(series.dtype),
        "total_rows": len(series),
        "missing_count": int(series.isna().sum()),
        "missing_pct": float(series.isna().mean() * 100),
        "unique_count": int(series.nunique()),
    }
    
    # بررسی مقادیر عددی
    if pd.api.types.is_numeric_dtype(series):
        numeric_series = series.dropna()
        if len(numeric_series) > 0:
            profile.update({
                "min": float(numeric_series.min()),
                "max": float(numeric_series.max()),
                "mean": float(numeric_series.mean()),
                "median": float(numeric_series.median()),
                "std": float(numeric_series.std()),
                "zero_count": int((series == 0).sum()),
                "negative_count": int((series < 0).sum()),
                "zero_pct": float((series == 0).mean() * 100),
                "negative_pct": float((series < 0).mean() * 100),
            })
            
            # شناسایی Outlier با IQR
            Q1 = numeric_series.quantile(0.25)
            Q3 = numeric_series.quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            outliers = ((numeric_series < lower) | (numeric_series > upper)).sum()
            profile["outlier_count"] = int(outliers)
            profile["outlier_pct"] = float(outliers / len(numeric_series) * 100)
    else:
        # ستون‌های متنی
        non_null = series.dropna()
        if len(non_null) > 0:
            profile.update({
                "top_values": non_null.value_counts().head(10).to_dict(),
                "empty_string_count": int((series.astype(str).str.strip() == "").sum()),
            })
    
    return profile


def analyze_date_columns(df, sheet_name):
    """تحلیل ستون‌های تاریخ"""
    date_analysis = {}
    
    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in ['تاریخ', 'date', 'سال', 'ماه']):
            print(f"   📅 تحلیل ستون تاریخ: {col}")
            
            sample_values = df[col].dropna().head(20).tolist()
            date_analysis[col] = {
                "sample_values": sample_values,
                "unique_dates": int(df[col].nunique()),
                "missing": int(df[col].isna().sum()),
            }
            
            # تلاش برای شناسایی فرمت تاریخ
            try:
                if df[col].dtype == 'object':
                    first_val = str(df[col].dropna().iloc[0])
                    if '/' in first_val and len(first_val.split('/')) == 3:
                        date_analysis[col]["format"] = "شمسی با /"
                    else:
                        date_analysis[col]["format"] = "نامشخص"
                else:
                    date_analysis[col]["format"] = str(df[col].dtype)
            except:
                date_analysis[col]["format"] = "خطا در تشخیص"
    
    return date_analysis


def profile_sheet(df, sheet_name):
    """بررسی کامل یک شیت"""
    print(f"\n{'='*60}")
    print(f"🔍 تحلیل شیت: {sheet_name}")
    print(f"{'='*60}")
    
    sheet_profile = {
        "sheet_name": sheet_name,
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "columns": {},
        "date_analysis": {},
    }
    
    # بررسی هر ستون
    for col in df.columns:
        sheet_profile["columns"][col] = profile_column(df[col], col)
    
    # تحلیل ستون‌های تاریخ
    sheet_profile["date_analysis"] = analyze_date_columns(df, sheet_name)
    
    # بررسی رکوردهای تکراری
    duplicates = df.duplicated().sum()
    sheet_profile["duplicate_rows"] = int(duplicates)
    sheet_profile["duplicate_pct"] = float(duplicates / len(df) * 100)
    
    # خلاصه
    print(f"\n📋 خلاصه شیت {sheet_name}:")
    print(f"   - رکوردهای تکراری: {duplicates:,} ({sheet_profile['duplicate_pct']:.2f}%)")
    
    return sheet_profile


def generate_summary_report(profiles):
    """تولید گزارش خلاصه"""
    summary = {
        "generated_at": datetime.now().isoformat(),
        "generated_at_jalali": jdatetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "total_sheets": len(profiles),
        "sheets": {},
        "key_findings": [],
    }
    
    for sheet_name, profile in profiles.items():
        summary["sheets"][sheet_name] = {
            "rows": profile["total_rows"],
            "columns": profile["total_columns"],
            "duplicates": profile["duplicate_rows"],
        }
        
        # شناسایی مشکلات
        for col, col_profile in profile["columns"].items():
            if col_profile.get("missing_pct", 0) > 5:
                summary["key_findings"].append(
                    f"⚠️ {sheet_name}.{col}: {col_profile['missing_pct']:.1f}% داده مفقود"
                )
            if col_profile.get("negative_pct", 0) > 0:
                summary["key_findings"].append(
                    f"🔻 {sheet_name}.{col}: {col_profile['negative_count']:,} مقدار منفی"
                )
            if col_profile.get("zero_pct", 0) > 10:
                summary["key_findings"].append(
                    f"⚪ {sheet_name}.{col}: {col_profile['zero_pct']:.1f}% مقدار صفر"
                )
    
    return summary


def main():
    """اجرای اصلی"""
    print("=" * 60)
    print("🔬 DATA INSPECTION & PROFILING PIPELINE")
    print("=" * 60)
    
    # بارگذاری فایل
    sheets = load_excel_sheets(EXCEL_FILE)
    if not sheets:
        return
    
    # بررسی هر شیت
    profiles = {}
    for sheet_name, df in sheets.items():
        profiles[sheet_name] = profile_sheet(df, sheet_name)
    
    # تولید گزارش
    summary = generate_summary_report(profiles)
    
    # ذخیره گزارش
    report = {
        "summary": summary,
        "detailed_profiles": profiles,
    }
    
    with open(OUTPUT_REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n{'='*60}")
    print(f"✅ گزارش در فایل ذخیره شد: {OUTPUT_REPORT}")
    print(f"{'='*60}")
    
    # چاپ یافته‌های کلیدی
    print("\n🎯 یافته‌های کلیدی:")
    for finding in summary["key_findings"][:20]:  # فقط ۲۰ مورد اول
        print(f"   {finding}")
    
    if len(summary["key_findings"]) > 20:
        print(f"   ... و {len(summary['key_findings']) - 20} مورد دیگر (در فایل JSON)")
    
    print("\n📊 خلاصه شیت‌ها:")
    for sheet, info in summary["sheets"].items():
        print(f"   - {sheet}: {info['rows']:,} ردیف، {info['columns']} ستون، {info['duplicates']} تکراری")


if __name__ == "__main__":
    main()