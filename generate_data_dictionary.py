"""
Phase 1 - Step 2: Data Dictionary Generation & Missing Strategy Proposal
"""

import json
from pathlib import Path
import pandas as pd

INPUT_REPORT = "data_quality_report.json"
OUTPUT_MD = "DATA_DICTIONARY.md"
OUTPUT_STRATEGY = "MISSING_STRATEGY.json"

# === استراتژی‌های پیش‌فرض برای هر نوع ستون ===
COLUMN_STRATEGIES = {
    # ستون‌های شناسایی‌کننده
    "سال": {"type": "identifier", "missing": "forward_fill_by_context", "zero": "valid"},
    "ماه": {"type": "identifier", "missing": "forward_fill_by_context", "zero": "invalid"},
    "تاریخ": {"type": "date", "missing": "critical_error", "zero": "invalid"},
    "تاریخ شمسی": {"type": "date", "missing": "critical_error", "zero": "invalid"},
    
    # ستون‌های دسته‌بندی
    "منبع": {"type": "dimension", "missing": "unknown_category", "zero": "not_applicable"},
    "نوع منبع": {"type": "dimension", "missing": "unknown_category", "zero": "not_applicable"},
    "دسته بندی": {"type": "dimension", "missing": "unknown_category", "zero": "not_applicable"},
    "نام ایستگاه": {"type": "dimension", "missing": "critical_error", "zero": "not_applicable"},
    "نام پالایشگاه": {"type": "dimension", "missing": "critical_error", "zero": "not_applicable"},
    "نام محصول": {"type": "dimension", "missing": "critical_error", "zero": "not_applicable"},
    "نوع مصرف": {"type": "dimension", "missing": "unknown_category", "zero": "not_applicable"},
    "استان": {"type": "dimension", "missing": "critical_error", "zero": "not_applicable"},
    "شهر": {"type": "dimension", "missing": "unknown_from_province", "zero": "not_applicable"},
    "کد پالایشگاه": {"type": "code", "missing": "critical_error", "zero": "not_applicable"},
    "کد محصول": {"type": "code", "missing": "critical_error", "zero": "not_applicable"},
    "کد نوع مصرف": {"type": "code", "missing": "unknown_category", "zero": "not_applicable"},
    
    # ستون‌های اندازه‌گیری اصلی
    "مقدار": {"type": "measure", "missing": "flag_only", "zero": "valid_real_value"},
    "میزان مصرف": {"type": "measure", "missing": "flag_only", "zero": "valid_real_value"},
    "میزان تولید": {"type": "measure", "missing": "flag_only", "zero": "valid_real_value"},
    
    # ستون‌های فشار (صفر می‌تواند واقعی یا خطا باشد)
    "فشار ساعت 6": {"type": "pressure", "missing": "interpolate_temporal", "zero": "investigate_by_station"},
    "فشار ساعت 18": {"type": "pressure", "missing": "interpolate_temporal", "zero": "investigate_by_station"},
    "فشار ساعت18": {"type": "pressure", "missing": "interpolate_temporal", "zero": "investigate_by_station"},
    
    # ستون‌های دما (صفر می‌تواند واقعی باشد، به خصوص در زمستان)
    "دمای ساعت6": {"type": "temperature", "missing": "interpolate_temporal", "zero": "valid_real_value"},
    "دمای ساعت 6": {"type": "temperature", "missing": "interpolate_temporal", "zero": "valid_real_value"},
    "دمای ساعت18": {"type": "temperature", "missing": "interpolate_temporal", "zero": "valid_real_value"},
    "دمای ساعت 18": {"type": "temperature", "missing": "interpolate_temporal", "zero": "valid_real_value"},
    "دمای محیط ساعت15": {"type": "temperature", "missing": "interpolate_temporal", "zero": "valid_real_value"},
    "دمای محیط ساعت18": {"type": "temperature", "missing": "interpolate_temporal", "zero": "valid_real_value"},
    "دمای ساعت15": {"type": "temperature", "missing": "interpolate_temporal", "zero": "valid_real_value"},
    
    # ستون‌های آماری و مقایسه‌ای
    "انحراف": {"type": "derived", "missing": "compute_from_actual_and_plan", "zero": "valid_exact_match", "negative": "valid_actual_below_plan"},
    "مقدار برنامه": {"type": "plan", "missing": "no_plan_available", "zero": "valid_no_planned"},
    "میانگین": {"type": "derived", "missing": "compute_from_available", "zero": "valid_no_consumption", "negative": "investigate"},
    "جمع سال": {"type": "aggregate", "missing": "compute_partial", "zero": "valid_no_consumption", "negative": "investigate"},
    "میانگین ماه": {"type": "derived", "missing": "compute_from_available", "zero": "valid_no_consumption", "negative": "investigate"},
    "میانگین سال قبل": {"type": "historical", "missing": "no_historical_data", "zero": "valid_no_consumption", "negative": "investigate"},
    "جمع سال قبل": {"type": "historical", "missing": "no_historical_data", "zero": "valid_no_consumption", "negative": "investigate"},
    "میانگین ماه سال قبل": {"type": "historical", "missing": "no_historical_data", "zero": "valid_no_consumption", "negative": "investigate"},
}

# === توضیحات استراتژی‌ها ===
STRATEGY_DESCRIPTIONS = {
    "forward_fill_by_context": "پر کردن با آخرین مقدار معتبر (با در نظر گرفتن ماه/سال)",
    "critical_error": "خطای بحرانی - رکورد قابل استفاده نیست یا باید از منبع اصلی بازیابی شود",
    "unknown_category": "مقدار 'نامشخص' جایگزین می‌شود",
    "not_applicable": "صفر برای این ستون معنی ندارد (ستون متنی/کد)",
    "valid_real_value": "صفر می‌تواند مقدار واقعی باشد (بدون حذف)",
    "valid_exact_match": "صفر یعنی مقدار واقعی دقیقاً برابر با برنامه بوده",
    "valid_actual_below_plan": "مقدار منفی یعنی مصرف کمتر از برنامه بوده (منطقی است)",
    "investigate": "نیاز به بررسی موردی - ممکن است خطا یا رخداد واقعی باشد",
    "investigate_by_station": "بررسی بر اساس ایستگاه - ممکن است برای برخی ایستگاه‌ها معتبر باشد",
    "interpolate_temporal": "پر کردن با میانگین مقادیر قبل و بعد (به صورت temporal)",
    "compute_from_actual_and_plan": "محاسبه مجدد از روی مقدار واقعی و برنامه (اگر موجود باشند)",
    "compute_from_available": "محاسبه از روی داده‌های موجود در بازه",
    "compute_partial": "محاسبه جمع جزئی تا تاریخ موجود",
    "no_plan_available": "برنامه برای این دوره ثبت نشده است",
    "no_historical_data": "داده سال قبل موجود نیست (شروع سری زمانی)",
    "flag_only": "پرچم‌گذاری به عنوان Missing بدون جایگزینی (برای مدل‌های ML)",
    "unknown_from_province": "اگر استان موجود است، از شهرهای آن استان حدس زده می‌شود",
}


def load_report():
    """بارگذاری گزارش Data Inspection"""
    if not Path(INPUT_REPORT).exists():
        print(f"❌ فایل گزارش یافت نشد: {INPUT_REPORT}")
        return None
    
    with open(INPUT_REPORT, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_column_name(name):
    """نرمال‌سازی نام ستون برای تطبیق بهتر"""
    # حذف فاصله‌های اضافی و نیم‌فاصله‌ها
    name = name.strip()
    name = name.replace('\u200c', ' ')  # نیم‌فاصله
    name = ' '.join(name.split())  # فاصله‌های چندگانه
    return name


def get_strategy_for_column(col_name):
    """یافتن استراتژی مناسب برای یک ستون"""
    normalized = normalize_column_name(col_name)
    
    # بررسی تطابق دقیق
    if normalized in COLUMN_STRATEGIES:
        return COLUMN_STRATEGIES[normalized]
    
    # بررسی تطابق جزئی
    for key in COLUMN_STRATEGIES:
        if key in normalized or normalized in key:
            return COLUMN_STRATEGIES[key]
    
    # استراتژی پیش‌فرض برای ستون‌های ناشناخته
    return {
        "type": "unknown",
        "missing": "investigate",
        "zero": "investigate",
        "_note": "ستون جدید - نیاز به بررسی توسط مدیر"
    }


def generate_markdown_report(report):
    """تولید گزارش Markdown خوانا"""
    md = []
    
    md.append("# 📖 Data Dictionary & Missing Strategy Report")
    md.append("")
    md.append("**تاریخ تولید:** " + report['summary']['generated_at_jalali'])
    md.append("")
    md.append("---")
    md.append("")
    
    # === خلاصه اجرایی ===
    md.append("## 📊 خلاصه اجرایی")
    md.append("")
    md.append("| شیت | تعداد ردیف | تعداد ستون | رکورد تکراری |")
    md.append("|:---|:---:|:---:|:---:|")
    for sheet, info in report['summary']['sheets'].items():
        md.append(f"| {sheet} | {info['rows']:,} | {info['columns']} | {info['duplicates']:,} |")
    md.append("")
    
    # === Data Dictionary به تفکیک شیت ===
    md.append("---")
    md.append("")
    md.append("## 📋 Data Dictionary (به تفکیک شیت)")
    md.append("")
    
    strategies_json = {}
    
    for sheet_name, profile in report['detailed_profiles'].items():
        md.append(f"### 📑 شیت: `{sheet_name}`")
        md.append("")
        md.append(f"**تعداد رکورد:** {profile['total_rows']:,} | **تعداد ستون:** {profile['total_columns']}")
        md.append("")
        md.append("| ستون | نوع داده | Missing | صفر | منفی | استراتژی پیشنهادی |")
        md.append("|:---|:---:|:---:|:---:|:---:|:---|")
        
        sheet_strategies = {}
        
        for col_name, col_profile in profile['columns'].items():
            strategy = get_strategy_for_column(col_name)
            
            # فرمت‌بندی مقادیر
            dtype = col_profile['dtype'].replace('float64', 'عدد اعشاری') \
                                        .replace('int64', 'عدد صحیح') \
                                        .replace('object', 'متن')
            missing = f"{col_profile['missing_pct']:.1f}%" if col_profile['missing_pct'] > 0 else "0"
            zero = f"{col_profile.get('zero_pct', 0):.1f}%" if col_profile.get('zero_pct', 0) > 0 else "0"
            negative = f"{col_profile.get('negative_count', 0):,}" if col_profile.get('negative_count', 0) > 0 else "0"
            
            # توضیح استراتژی
            missing_strategy = strategy.get('missing', 'investigate')
            strategy_desc = STRATEGY_DESCRIPTIONS.get(missing_strategy, missing_strategy)
            
            # علامت‌گذاری موارد بحرانی
            warning = ""
            if col_profile['missing_pct'] > 50:
                warning = " ⚠️"
            elif col_profile['missing_pct'] > 20:
                warning = " ⚡"
            
            md.append(f"| `{col_name}`{warning} | {dtype} | {missing} | {zero} | {negative} | {strategy_desc} |")
            
            sheet_strategies[col_name] = {
                "column_type": strategy.get('type', 'unknown'),
                "missing_strategy": missing_strategy,
                "missing_strategy_description": strategy_desc,
                "zero_strategy": strategy.get('zero', 'investigate'),
                "negative_strategy": strategy.get('negative', 'investigate'),
                "quality_issues": {
                    "missing_pct": col_profile['missing_pct'],
                    "zero_count": col_profile.get('zero_count', 0),
                    "negative_count": col_profile.get('negative_count', 0),
                }
            }
        
        md.append("")
        strategies_json[sheet_name] = sheet_strategies
    
    # === استراتژی‌های کلی ===
    md.append("---")
    md.append("")
    md.append("## 🎯 راهنمای استراتژی‌ها")
    md.append("")
    for key, desc in STRATEGY_DESCRIPTIONS.items():
        md.append(f"- **`{key}`**: {desc}")
    md.append("")
    
    # === یافته‌های کلیدی ===
    md.append("---")
    md.append("")
    md.append("## 🚨 یافته‌های کلیدی و اقدامات لازم")
    md.append("")
    
    # گروه‌بندی یافته‌ها
    critical = [f for f in report['summary']['key_findings'] if "⚠️" in f and "64" in f or "40" in f]
    negative = [f for f in report['summary']['key_findings'] if "🔻" in f]
    zero = [f for f in report['summary']['key_findings'] if "⚪" in f]
    
    if critical:
        md.append("### بحرانی (Missing بالا)")
        for f in critical:
            md.append(f"- {f}")
        md.append("")
    
    if negative:
        md.append("### مقادیر منفی")
        for f in negative[:10]:
            md.append(f"- {f}")
        if len(negative) > 10:
            md.append(f"- ... و {len(negative) - 10} مورد دیگر")
        md.append("")
    
    if zero:
        md.append("### مقادیر صفر قابل توجه")
        for f in zero:
            md.append(f"- {f}")
        md.append("")
    
    return "\n".join(md), strategies_json


def main():
    print("=" * 60)
    print("📖 تولید Data Dictionary و استراتژی‌های Missing/Zero")
    print("=" * 60)
    
    report = load_report()
    if not report:
        return
    
    # تولید گزارش Markdown
    md_content, strategies_json = generate_markdown_report(report)
    
    # ذخیره Markdown
    with open(OUTPUT_MD, 'w', encoding='utf-8') as f:
        f.write(md_content)
    print(f"✅ گزارش Markdown ذخیره شد: {OUTPUT_MD}")
    
    # ذخیره JSON استراتژی‌ها
    with open(OUTPUT_STRATEGY, 'w', encoding='utf-8') as f:
        json.dump(strategies_json, f, ensure_ascii=False, indent=2)
    print(f"✅ استراتژی‌ها ذخیره شدند: {OUTPUT_STRATEGY}")
    
    print("\n" + "=" * 60)
    print("📋 خلاصه:")
    print(f"   - فایل {OUTPUT_MD} را در VS Code باز کنید")
    print(f"   - استراتژی‌های هر ستون را بررسی کنید")
    print(f"   - در صورت نیاز، استراتژی‌ها را اصلاح کنید")
    print("=" * 60)


if __name__ == "__main__":
    main()