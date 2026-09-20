"""
Data Quality Assessment Report
تحلیل جامع کیفیت داده‌ها برای ارائه به تأمین‌کننده داده
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
import jdatetime

EXCEL_FILE = "data/گزارش روزانه تولید و مصرف و ایستگاهها.xlsx"
OUTPUT_MD = "DATA_QUALITY_REPORT.md"
OUTPUT_JSON = "data_quality_metrics.json"

# ============================================================
# 1. Data Loading
# ============================================================
def load_data():
    print("📥 بارگذاری داده‌ها...")
    xls = pd.ExcelFile(EXCEL_FILE)
    sheets = {}
    for sheet in xls.sheet_names:
        sheets[sheet] = pd.read_excel(xls, sheet_name=sheet)
        sheets[sheet].columns = [str(c).strip() for c in sheets[sheet].columns]
        print(f"   ✅ {sheet}: {len(sheets[sheet]):,} ردیف")
    return sheets


# ============================================================
# 2. Column-Level Quality Analysis
# ============================================================
def analyze_column(series, col_name):
    """تحلیل کیفیت یک ستون"""
    profile = {
        'column': col_name,
        'dtype': str(series.dtype),
        'total_rows': len(series),
        'missing_count': int(series.isna().sum()),
        'missing_pct': round(float(series.isna().mean() * 100), 2),
        'unique_count': int(series.nunique()),
    }
    
    # امتیاز کیفیت ستون (از 100)
    quality_score = 100
    
    # کسر امتیاز برای داده‌های مفقود
    quality_score -= min(50, profile['missing_pct'] * 0.5)
    
    if pd.api.types.is_numeric_dtype(series):
        numeric = series.dropna()
        if len(numeric) > 0:
            zero_count = int((series == 0).sum())
            negative_count = int((series < 0).sum())
            
            profile.update({
                'min': float(numeric.min()),
                'max': float(numeric.max()),
                'mean': float(numeric.mean()),
                'zero_count': zero_count,
                'zero_pct': round(float(zero_count / len(series) * 100), 2),
                'negative_count': negative_count,
                'negative_pct': round(float(negative_count / len(series) * 100), 2),
            })
            
            # Outlier detection با IQR
            Q1, Q3 = numeric.quantile(0.25), numeric.quantile(0.75)
            IQR = Q3 - Q1
            outliers = ((numeric < Q1 - 3 * IQR) | (numeric > Q3 + 3 * IQR)).sum()
            profile['extreme_outliers'] = int(outliers)
            profile['extreme_outliers_pct'] = round(float(outliers / len(series) * 100), 2)
            
            # کسر امتیاز برای پرت‌های شدید
            quality_score -= min(20, profile['extreme_outliers_pct'] * 2)
            
            # بررسی دامنه غیرمنطقی برای دما و فشار
            if any(keyword in col_name for keyword in ['دما', 'فشار']):
                if numeric.max() > 100:
                    profile['range_issue'] = f"بیشینه غیرمنطقی: {numeric.max():.0f}"
                    quality_score -= 20
                if numeric.min() < -50:
                    profile['range_issue'] = f"کمینه غیرمنطقی: {numeric.min():.0f}"
                    quality_score -= 20
    else:
        # ستون‌های متنی
        non_null = series.dropna().astype(str)
        if len(non_null) > 0:
            # بررسی نیم‌فاصله و کاراکترهای غیراستاندارد
            half_space_count = int(non_null.str.contains('\u200c', na=False).sum())
            arabic_ye = int(non_null.str.contains('ي|ك', na=False).sum())
            
            profile.update({
                'half_space_issues': half_space_count,
                'arabic_char_issues': arabic_ye,
                'empty_strings': int((non_null.str.strip() == '').sum()),
            })
            
            if half_space_count > 0 or arabic_ye > 0:
                quality_score -= 5
    
    profile['quality_score'] = max(0, round(quality_score, 1))
    
    # تعیین وضعیت
    if profile['quality_score'] >= 90:
        profile['status'] = 'عالی ✅'
    elif profile['quality_score'] >= 70:
        profile['status'] = 'خوب 🟢'
    elif profile['quality_score'] >= 50:
        profile['status'] = 'متوسط 🟡'
    else:
        profile['status'] = 'نیازمند اصلاح 🔴'
    
    return profile


# ============================================================
# 3. Temporal Analysis
# ============================================================
def analyze_temporal(sheets):
    """تحلیل پوشش زمانی"""
    print("\n📅 تحلیل پوشش زمانی...")
    
    temporal_report = {}
    
    for sheet_name, df in sheets.items():
        date_col = None
        for col in df.columns:
            if 'تاریخ' in col.lower():
                date_col = col
                break
        
        if date_col is None:
            continue
        
        dates = df[date_col].dropna().astype(str)
        
        # استخراج سال و ماه
        years, months = [], []
        valid_dates = 0
        for d in dates:
            parts = d.split('/')
            if len(parts) == 3:
                try:
                    y, m = int(parts[0]), int(parts[1])
                    years.append(y)
                    months.append((y, m))
                    valid_dates += 1
                except:
                    pass
        
        if not years:
            continue
        
        year_series = pd.Series(years)
        month_series = pd.Series(months)
        
        temporal_report[sheet_name] = {
            'total_records': len(df),
            'valid_dates': valid_dates,
            'date_validity_pct': round(valid_dates / len(df) * 100, 2),
            'year_range': f"{min(years)} تا {max(years)}",
            'unique_years': int(year_series.nunique()),
            'unique_year_months': int(month_series.nunique()),
            'records_per_month_avg': round(len(df) / max(1, month_series.nunique()), 0),
        }
    
    return temporal_report


# ============================================================
# 4. Geographic Coverage Analysis
# ============================================================
def analyze_geographic(sheets):
    """تحلیل پوشش جغرافیایی"""
    print("\n🗺️ تحلیل پوشش جغرافیایی...")
    
    geo_report = {}
    
    if 'GasOperationDailyStationReport' in sheets:
        df = sheets['GasOperationDailyStationReport']
        
        if 'استان' in df.columns:
            provinces = df['استان'].dropna().unique()
            geo_report['provinces'] = {
                'count': len(provinces),
                'list': sorted(provinces.tolist()),
            }
        
        if 'نام ایستگاه' in df.columns:
            stations = df['نام ایستگاه'].dropna().unique()
            geo_report['stations'] = {
                'count': len(stations),
            }
            
            # بررسی ایستگاه‌های با داده کم
            station_counts = df['نام ایستگاه'].value_counts()
            geo_report['low_data_stations'] = {
                'count': int((station_counts < 10).sum()),
                'description': 'ایستگاه‌هایی با کمتر از ۱۰ رکورد'
            }
    
    if 'GasOperationDailyReport' in sheets:
        df = sheets['GasOperationDailyReport']
        if 'منبع' in df.columns:
            sources = df['منبع'].dropna().unique()
            geo_report['sources'] = {
                'count': len(sources),
                'list': sorted(sources.tolist())[:20],
            }
    
    if 'ViewProdDailyForNaft' in sheets:
        df = sheets['ViewProdDailyForNaft']
        if 'نام پالایشگاه' in df.columns:
            refineries = df['نام پالایشگاه'].dropna().unique()
            geo_report['refineries'] = {
                'count': len(refineries),
                'list': sorted(refineries.tolist()),
            }
    
    return geo_report


# ============================================================
# 5. Missing Fields & Data Domain Analysis
# ============================================================
def identify_missing_fields(sheets):
    """شناسایی فیلدها و حوزه‌های داده‌ای موجود نیست"""
    print("\n🔍 شناسایی حوزه‌های داده‌ای موجود نیست...")
    
    # حوزه‌های داده‌ای استاندارد در صنعت گاز
    expected_domains = {
        'اطلاعات هواشناسی محیطی': {
            'description': 'دمای محیط، رطوبت، سرعت باد، بارندگی',
            'impact': 'افزایش دقت پیش‌بینی مصرف تا ۳۰٪',
            'priority': 'بحرانی',
        },
        'شناسه‌های یکتا': {
            'description': 'کد ملی ایستگاه، کد پستی، مختصات جغرافیایی (GPS)',
            'impact': 'امکان تحلیل مکانی و نقشه‌سازی',
            'priority': 'بالا',
        },
        'داده‌های ساعتی': {
            'description': 'مصرف ساعتی به جای روزانه',
            'impact': 'پیش‌بینی دقیق‌تر در زمان پیک مصرف',
            'priority': 'بالا',
        },
        'داده‌های اقتصادی': {
            'description': 'قیمت گاز، تعرفه‌ها، هزینه‌های انتقال',
            'impact': 'تحلیل هزینه-فایده و پیش‌بینی درآمد',
            'priority': 'متوسط',
        },
        'داده‌های تعمیر و نگهداری': {
            'description': 'تاریخ تعمیرات، قطعی‌ها، ظرفیت ایستگاه',
            'impact': 'تشخیص علل ناهنجاری و برنامه‌ریزی',
            'priority': 'بالا',
        },
        'اطلاعات مشترکین': {
            'description': 'تعداد مشترکین به تفکیک خانگی/تجاری/صنعتی',
            'impact': 'تحلیل دقیق‌تر رفتار مصرف',
            'priority': 'متوسط',
        },
        'داده‌های تولید کامل': {
            'description': 'تولید همه محصولات (نه فقط میعانات گازی)',
            'impact': 'تحلیل کامل تراز تولید-مصرف',
            'priority': 'بحرانی',
        },
        'داده‌های واردات/صادرات': {
            'description': 'حجم واردات و صادرات روزانه',
            'impact': 'تحلیل دقیق تراز ملی گاز',
            'priority': 'بالا',
        },
        'داده‌های ذخیره‌سازی': {
            'description': 'موجودی مخازن ذخیره‌سازی',
            'impact': 'مدیریت بهینه منابع در زمان پیک',
            'priority': 'بالا',
        },
        'تاریخچه بلندمدت': {
            'description': 'حداقل ۳-۵ سال داده (فعلی ۶ ماه)',
            'impact': 'پیش‌بینی فصلی و سالانه دقیق',
            'priority': 'بحرانی',
        },
        'اطلاعات واحد اندازه‌گیری': {
            'description': 'واحد دقیق هر ستون (متر مکعب، لیتر، تن و ...)',
            'impact': 'جلوگیری از اشتباهات محاسباتی',
            'priority': 'بحرانی',
        },
        'متادیتای منبع داده': {
            'description': 'منبع استخراج، زمان استخراج، نسخه داده',
            'impact': 'قابلیت ردیابی و ممیزی داده',
            'priority': 'متوسط',
        },
    }
    
    return expected_domains


# ============================================================
# 6. Calculate Overall Quality Score
# ============================================================
def calculate_overall_score(column_profiles):
    """محاسبه امتیاز کیفیت کلی"""
    scores = [p['quality_score'] for p in column_profiles]
    return round(sum(scores) / len(scores), 1) if scores else 0


# ============================================================
# 7. Generate Recommendations
# ============================================================
def generate_recommendations(column_profiles, temporal_report, geo_report):
    """تولید پیشنهادات اولویت‌بندی شده"""
    recommendations = []
    
    # پیشنهادات بر اساس کیفیت ستون‌ها
    critical_columns = [p for p in column_profiles if p['quality_score'] < 50]
    if critical_columns:
        recommendations.append({
            'priority': 'بحرانی 🔴',
            'category': 'کیفیت داده',
            'issue': f"{len(critical_columns)} ستون با کیفیت بحرانی",
            'action': 'بررسی و اصلاح فوری ستون‌های با امتیاز زیر ۵۰',
            'columns': [p['column'] for p in critical_columns],
        })
    
    # Outliers
    high_outlier_cols = [p for p in column_profiles if p.get('extreme_outliers_pct', 0) > 1]
    if high_outlier_cols:
        recommendations.append({
            'priority': 'بحرانی 🔴',
            'category': 'داده‌های پرت',
            'issue': 'وجود مقادیر پرت شدید (مثلاً دمای ۱۲۷,۷۳۷ درجه)',
            'action': 'اعمال اعتبارسنجی در زمان ثبت داده و حذف مقادیر خارج از دامنه منطقی',
            'columns': [p['column'] for p in high_outlier_cols],
        })
    
    # Missing data
    high_missing_cols = [p for p in column_profiles if p['missing_pct'] > 30]
    if high_missing_cols:
        recommendations.append({
            'priority': 'بالا 🟡',
            'category': 'داده‌های مفقود',
            'issue': f"{len(high_missing_cols)} ستون با بیش از ۳۰٪ داده مفقود",
            'action': 'بررسی فرآیند ثبت داده و الزامی کردن فیلدهای کلیدی',
            'columns': [p['column'] for p in high_missing_cols],
        })
    
    # ستون‌های خالی
    empty_cols = [p for p in column_profiles if p['missing_pct'] == 100]
    if empty_cols:
        recommendations.append({
            'priority': 'بالا 🟡',
            'category': 'ستون‌های خالی',
            'issue': f"{len(empty_cols)} ستون کاملاً خالی (احتمالاً خطا در استخراج)",
            'action': 'حذف ستون‌های خالی یا اصلاح فرآیند استخراج',
            'columns': [p['column'] for p in empty_cols],
        })
    
    # پوشش زمانی
    for sheet, info in temporal_report.items():
        if info['unique_year_months'] < 12:
            recommendations.append({
                'priority': 'بحرانی 🔴',
                'category': 'پوشش زمانی',
                'issue': f'شیت {sheet} فقط {info["unique_year_months"]} ماه داده دارد',
                'action': 'افزودن داده‌های تاریخی (حداقل ۳ سال) برای پیش‌بینی فصلی دقیق',
            })
    
    # پوشش جغرافیایی
    if 'low_data_stations' in geo_report:
        low_stations = geo_report['low_data_stations']['count']
        if low_stations > 0:
            recommendations.append({
                'priority': 'متوسط 🟢',
                'category': 'پوشش ایستگاه‌ها',
                'issue': f'{low_stations} ایستگاه با کمتر از ۱۰ رکورد',
                'action': 'بررسی فعال بودن این ایستگاه‌ها و تکمیل داده‌ها',
            })
    
    # واحد اندازه‌گیری
    recommendations.append({
        'priority': 'بحرانی 🔴',
        'category': 'متادیتا',
        'issue': 'واحد اندازه‌گیری هیچ ستونی در داده‌ها مشخص نیست',
        'action': 'افزودن یک فایل متادیتا با واحد هر ستون (متر مکعب، لیتر، درجه و ...)',
    })
    
    # داده‌های هواشناسی
    recommendations.append({
        'priority': 'بحرانی 🔴',
        'category': 'حوزه داده‌ای جدید',
        'issue': 'نبود داده‌های هواشناسی محیطی (دمای هوا، رطوبت، باد)',
        'action': 'اتصال به سامانه هواشناسی یا افزودن سنسورهای محیطی',
    })
    
    # داده‌های ساعتی
    recommendations.append({
        'priority': 'بالا 🟡',
        'category': 'دانه زمانی',
        'issue': 'داده‌ها فقط در سطح روزانه هستند',
        'action': 'افزودن داده‌های ساعتی برای تحلیل پیک مصرف',
    })
    
    return recommendations


# ============================================================
# 8. Generate Markdown Report
# ============================================================
def generate_markdown_report(sheets, column_profiles_by_sheet, temporal_report,
                              geo_report, expected_domains, recommendations,
                              overall_scores):
    """تولید گزارش Markdown"""
    
    md = []
    
    # عنوان
    md.append("# 📊 گزارش جامع تحلیل کیفیت داده‌ها")
    md.append("")
    md.append("**پروژه:** سامانه هوشمند پایش و تحلیل گاز")
    md.append("")
    md.append(f"**تاریخ تولید:** {jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}")
    md.append("")
    md.append("**تهیه‌کننده:** تیم تحلیل داده")
    md.append("")
    md.append("**مخاطب:** بخش تأمین‌کننده داده")
    md.append("")
    md.append("---")
    md.append("")
    
    # بخش ۱: خلاصه اجرایی
    md.append("## ۱. خلاصه اجرایی")
    md.append("")
    
    total_records = sum(len(df) for df in sheets.values())
    total_columns = sum(len(df.columns) for df in sheets.values())
    avg_score = sum(overall_scores.values()) / len(overall_scores) if overall_scores else 0
    
    md.append("| شاخص | مقدار |")
    md.append("|:---|:---:|")
    md.append(f"| تعداد کل رکوردها | {total_records:,} |")
    md.append(f"| تعداد شیت‌ها | {len(sheets)} |")
    md.append(f"| تعداد کل ستون‌ها | {total_columns} |")
    md.append(f"| **امتیاز کیفیت کلی** | **{avg_score:.1f} از ۱۰۰** |")
    md.append("")
    
    # وضعیت کلی
    if avg_score >= 80:
        md.append("**وضعیت کلی:** 🟢 کیفیت داده‌ها خوب است اما نیاز به بهبود دارد.")
    elif avg_score >= 60:
        md.append("**وضعیت کلی:** 🟡 کیفیت داده‌ها متوسط است و نیاز به توجه جدی دارد.")
    else:
        md.append("**وضعیت کلی:** 🔴 کیفیت داده‌ها نیازمند اصلاح فوری است.")
    md.append("")
    
    # امتیاز هر شیت
    md.append("### امتیاز کیفیت به تفکیک شیت:")
    md.append("")
    md.append("| شیت | امتیاز کیفیت | وضعیت |")
    md.append("|:---|:---:|:---:|")
    for sheet, score in overall_scores.items():
        status = "🟢 خوب" if score >= 70 else "🟡 متوسط" if score >= 50 else "🔴 بحرانی"
        md.append(f"| {sheet} | {score} | {status} |")
    md.append("")
    md.append("---")
    md.append("")
    
    # بخش ۲: کمیت داده‌ها
    md.append("## ۲. کمیت داده‌ها")
    md.append("")
    md.append("| شیت | تعداد رکورد | تعداد ستون |")
    md.append("|:---|---:|:---:|")
    for sheet, df in sheets.items():
        md.append(f"| {sheet} | {len(df):,} | {len(df.columns)} |")
    md.append("")
    
    # پوشش زمانی
    md.append("### پوشش زمانی:")
    md.append("")
    for sheet, info in temporal_report.items():
        md.append(f"**{sheet}:**")
        md.append(f"- بازه: {info['year_range']}")
        md.append(f"- تعداد ماه‌های دارای داده: {info['unique_year_months']}")
        md.append(f"- میانگین رکورد در ماه: {info['records_per_month_avg']:,.0f}")
        md.append("")
    
    # پوشش جغرافیایی
    md.append("### پوشش جغرافیایی:")
    md.append("")
    if 'provinces' in geo_report:
        md.append(f"- **تعداد استان‌ها:** {geo_report['provinces']['count']}")
    if 'stations' in geo_report:
        md.append(f"- **تعداد ایستگاه‌ها:** {geo_report['stations']['count']}")
    if 'refineries' in geo_report:
        md.append(f"- **تعداد پالایشگاه‌ها:** {geo_report['refineries']['count']}")
    if 'sources' in geo_report:
        md.append(f"- **تعداد منابع:** {geo_report['sources']['count']}")
    md.append("")
    md.append("---")
    md.append("")
    
    # بخش ۳: کیفیت داده‌ها
    md.append("## ۳. کیفیت داده‌ها (به تفکیک ستون)")
    md.append("")
    
    for sheet, profiles in column_profiles_by_sheet.items():
        md.append(f"### شیت: {sheet}")
        md.append("")
        md.append("| ستون | نوع | مفقود٪ | صفر٪ | پرت٪ | امتیاز | وضعیت |")
        md.append("|:---|:---:|:---:|:---:|:---:|:---:|:---:|")
        
        for p in profiles:
            zero_pct = p.get('zero_pct', '-')
            outlier_pct = p.get('extreme_outliers_pct', '-')
            md.append(f"| {p['column']} | {p['dtype']} | {p['missing_pct']}% | "
                     f"{zero_pct}{'%' if zero_pct != '-' else ''} | "
                     f"{outlier_pct}{'%' if outlier_pct != '-' else ''} | "
                     f"{p['quality_score']} | {p['status']} |")
        md.append("")
    
    md.append("---")
    md.append("")
    
    # بخش ۴: نواقص نوع داده
    md.append("## ۴. نواقص نوع داده")
    md.append("")
    md.append("### مشکلات شناسایی‌شده:")
    md.append("")
    
    type_issues = []
    for sheet, profiles in column_profiles_by_sheet.items():
        for p in profiles:
            if p.get('range_issue'):
                type_issues.append(f"- **{sheet}.{p['column']}**: {p['range_issue']}")
            if p.get('half_space_issues', 0) > 0:
                type_issues.append(f"- **{sheet}.{p['column']}**: {p['half_space_issues']} مورد نیم‌فاصله غیراستاندارد")
            if p.get('arabic_char_issues', 0) > 0:
                type_issues.append(f"- **{sheet}.{p['column']}**: {p['arabic_char_issues']} مورد کاراکتر عربی (ي/ك)")
    
    if type_issues:
        md.extend(type_issues[:20])
    else:
        md.append("مشکل نوع داده‌ای شناسایی نشد.")
    md.append("")
    md.append("---")
    md.append("")
    
    # بخش ۵: حوزه‌های داده‌ای موجود نیست
    md.append("## ۵. حوزه‌های داده‌ای موجود نیست")
    md.append("")
    md.append("این حوزه‌ها در داده‌های فعلی وجود ندارند اما برای توسعه قابلیت‌های سامانه ضروری هستند:")
    md.append("")
    md.append("| حوزه داده‌ای | توضیح | اثرگذاری | اولویت |")
    md.append("|:---|:---|:---|:---:|")
    for domain, info in expected_domains.items():
        md.append(f"| **{domain}** | {info['description']} | {info['impact']} | {info['priority']} |")
    md.append("")
    md.append("---")
    md.append("")
    
    # بخش ۶: پیشنهادات عملی
    md.append("## ۶. پیشنهادات عملی (اولویت‌بندی شده)")
    md.append("")
    
    # مرتب‌سازی بر اساس اولویت
    priority_order = {'بحرانی 🔴': 0, 'بالا 🟡': 1, 'متوسط 🟢': 2}
    sorted_recs = sorted(recommendations, key=lambda x: priority_order.get(x['priority'], 3))
    
    md.append("| # | اولویت | دسته | مشکل | اقدام پیشنهادی |")
    md.append("|:---:|:---:|:---|:---|:---|")
    for i, rec in enumerate(sorted_recs, 1):
        md.append(f"| {i} | {rec['priority']} | {rec['category']} | {rec['issue']} | {rec['action']} |")
    md.append("")
    md.append("---")
    md.append("")
    
    # بخش ۷: وضعیت فعلی در مقابل مطلوب
    md.append("## ۷. وضعیت فعلی در مقابل وضعیت مطلوب")
    md.append("")
    md.append("| مؤلفه | وضعیت فعلی | وضعیت مطلوب |")
    md.append("|:---|:---|:---|")
    md.append("| پوشش زمانی | ۶ ماه | ۳-۵ سال |")
    md.append("| دانه زمانی | روزانه | ساعتی |")
    md.append("| داده‌های هواشناسی | دمای گاز فقط | دمای محیط + رطوبت + باد |")
    md.append("| شناسه یکتا | ندارد | کد ملی ایستگاه + GPS |")
    md.append("| واحد اندازه‌گیری | نامشخص | مستند برای هر ستون |")
    md.append("| اعتبارسنجی داده | ندارد | خودکار در زمان ثبت |")
    md.append("| متادیتا | ندارد | کامل و استاندارد |")
    md.append("| تولید (پالایشگاه) | فقط میعانات گازی | همه محصولات |")
    md.append("")
    md.append("---")
    md.append("")
    
    # بخش ۸: نتیجه‌گیری
    md.append("## ۸. نتیجه‌گیری و گام‌های بعدی")
    md.append("")
    md.append("### اولویت‌های فوری (طی ۱ ماه آینده):")
    md.append("1. 🔴 اصلاح داده‌های پرت شدید (دمای ۱۲۷,۷۳۷ درجه)")
    md.append("2. 🔴 حذف ستون‌های ۱۰۰٪ خالی")
    md.append("3. 🔴 مستندسازی واحد اندازه‌گیری هر ستون")
    md.append("4. 🔴 افزودن داده‌های هواشناسی محیطی")
    md.append("")
    md.append("### اولویت‌های میان‌مدت (طی ۳ ماه آینده):")
    md.append("1. 🟡 افزایش پوشش زمانی به حداقل ۲ سال")
    md.append("2. 🟡 افزودن داده‌های ساعتی")
    md.append("3. 🟡 افزودن شناسه‌های یکتا و مختصات جغرافیایی")
    md.append("")
    md.append("### اولویت‌های بلندمدت (طی ۶ ماه آینده):")
    md.append("1. 🟢 اتصال به سامانه‌های بلادرنگ (SCADA)")
    md.append("2. 🟢 پیاده‌سازی اعتبارسنجی خودکار در زمان ثبت")
    md.append("3. 🟢 افزودن متادیتای کامل و استاندارد")
    md.append("")
    md.append("---")
    md.append("")
    md.append("*این گزارش به صورت خودکار توسط سامانه تحلیل کیفیت داده تولید شده است.*")
    
    return "\n".join(md)


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 70)
    print("📊 DATA QUALITY ASSESSMENT REPORT")
    print("=" * 70)
    
    # بارگذاری داده‌ها
    sheets = load_data()
    
    # تحلیل کیفیت هر ستون
    print("\n🔍 تحلیل کیفیت ستون‌ها...")
    column_profiles_by_sheet = {}
    all_profiles = []
    
    for sheet_name, df in sheets.items():
        print(f"   📋 {sheet_name}")
        profiles = []
        for col in df.columns:
            profile = analyze_column(df[col], col)
            profiles.append(profile)
            all_profiles.append(profile)
        column_profiles_by_sheet[sheet_name] = profiles
    
    # تحلیل زمانی
    temporal_report = analyze_temporal(sheets)
    
    # تحلیل جغرافیایی
    geo_report = analyze_geographic(sheets)
    
    # شناسایی حوزه‌های موجود نیست
    expected_domains = identify_missing_fields(sheets)
    
    # محاسبه امتیاز کلی
    overall_scores = {}
    for sheet_name, profiles in column_profiles_by_sheet.items():
        overall_scores[sheet_name] = calculate_overall_score(profiles)
    
    print(f"\n📈 امتیاز کیفیت به تفکیک شیت:")
    for sheet, score in overall_scores.items():
        print(f"   - {sheet}: {score}/100")
    
    # تولید پیشنهادات
    recommendations = generate_recommendations(
        all_profiles, temporal_report, geo_report
    )
    
    print(f"\n💡 تعداد پیشنهادات: {len(recommendations)}")
    
    # تولید گزارش Markdown
    print("\n📝 تولید گزارش Markdown...")
    md_report = generate_markdown_report(
        sheets, column_profiles_by_sheet, temporal_report,
        geo_report, expected_domains, recommendations, overall_scores
    )
    
    with open(OUTPUT_MD, 'w', encoding='utf-8') as f:
        f.write(md_report)
    print(f"✅ گزارش ذخیره شد: {OUTPUT_MD}")
    
    # ذخیره JSON
    json_data = {
        'generated_at': datetime.now().isoformat(),
        'generated_at_jalali': jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
        'overall_scores': overall_scores,
        'total_records': sum(len(df) for df in sheets.values()),
        'temporal_report': temporal_report,
        'geographic_report': geo_report,
        'column_profiles': column_profiles_by_sheet,
        'expected_domains': expected_domains,
        'recommendations': recommendations,
    }
    
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"✅ داده‌های خام ذخیره شد: {OUTPUT_JSON}")
    
    print("\n" + "=" * 70)
    print("✅ گزارش تحلیل کیفیت داده با موفقیت تولید شد!")
    print("=" * 70)
    print(f"\n📄 فایل‌های خروجی:")
    print(f"   1. {OUTPUT_MD} (برای ارائه به مدیریت)")
    print(f"   2. {OUTPUT_JSON} (برای پردازش ماشینی)")
    print("\n💡 پیشنهاد: فایل Markdown را در VS Code باز کنید و به صورت PDF ذخیره کنید.")


if __name__ == "__main__":
    main()