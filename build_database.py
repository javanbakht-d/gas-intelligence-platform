"""
Phase 3: Database Construction Pipeline
ساخت دیتابیس حرفه‌ای با حذف ستون‌های خطایی و استانداردسازی
نسخه 2.1 - رفع باگ KeyError
"""

import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
import jdatetime
from datetime import datetime
import re

# === Configuration ===
EXCEL_FILE = "data/گزارش روزانه تولید و مصرف و ایستگاهها.xlsx"
DB_FILE = "gas_data.db"

# ستون‌هایی که باید حذف شوند (100% خالی یا خطایی)
DROP_COLUMNS = {
    "GasOperationDailyStationReport": [
        "فشار ساعت 18",
        "دمای محیط ساعت15",
    ]
}

# تغییر نام ستون‌ها
RENAME_COLUMNS = {
    "GasOperationDailyStationReport": {
        "دمای ساعت6": "دمای گاز ساعت 6 صبح - نقطه 1",
        "دمای ساعت6.1": "دمای گاز ساعت 6 صبح - نقطه 2",
        "دمای ساعت18": "دمای گاز ساعت 18",
        "فشار ساعت 6": "فشار ساعت 6 صبح",
        "فشار ساعت18": "فشار ساعت 18",
    }
}

# نام جداول
TABLE_NAMES = {
    "GasOperationDailyReport": "operation_daily_report",
    "GasOperationDailyStationReport": "station_consumption_daily",
    "ViewProdDailyForNaft": "production_daily",
}


def normalize_persian_text(text):
    """استانداردسازی متن فارسی"""
    if not isinstance(text, str):
        return text
    text = text.replace('\u200c', ' ')
    text = text.replace('ي', 'ی').replace('ك', 'ک')
    text = ' '.join(text.split())
    return text.strip()


def parse_shamsi_date(date_val):
    """پارس تاریخ شمسی و برگرداندن dict با ویژگی‌ها"""
    # مقادیر پیش‌فرض در صورت شکست
    default = {
        'shamsi_date': None,
        'shamsi_year': None,
        'shamsi_month': None,
        'shamsi_day': None,
        'gregorian_date': None,
        'weekday': None,
        'season': None,
        'is_weekend': None,
    }
    
    if pd.isna(date_val):
        return default
    
    date_str = str(date_val).strip()
    
    patterns = [
        r'^(\d{4})/(\d{1,2})/(\d{1,2})$',
        r'^(\d{4})-(\d{1,2})-(\d{1,2})$',
        r'^(\d{4})\.(\d{1,2})\.(\d{1,2})$',
    ]
    
    for pattern in patterns:
        match = re.match(pattern, date_str)
        if match:
            try:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                jdate = jdatetime.date(year, month, day)
                gdate = jdate.togregorian()
                weekday = jdate.weekday()
                season = (month - 1) // 3 + 1
                return {
                    'shamsi_date': date_str,
                    'shamsi_year': year,
                    'shamsi_month': month,
                    'shamsi_day': day,
                    'gregorian_date': gdate.isoformat(),
                    'weekday': weekday,
                    'season': season,
                    'is_weekend': weekday in [4, 5],
                }
            except:
                pass
    
    return default


def add_date_features(df, date_col):
    """اضافه کردن ویژگی‌های زمانی با استفاده از dict keys"""
    print(f"   📅 استخراج ویژگی‌های زمانی از ستون: {date_col}")
    
    date_features = df[date_col].apply(parse_shamsi_date)
    
    # استفاده از keyهای dict به جای ایندکس عددی
    df['shamsi_year'] = [f.get('shamsi_year') for f in date_features]
    df['shamsi_month'] = [f.get('shamsi_month') for f in date_features]
    df['shamsi_day'] = [f.get('shamsi_day') for f in date_features]
    df['gregorian_date'] = [f.get('gregorian_date') for f in date_features]
    df['weekday'] = [f.get('weekday') for f in date_features]
    df['season'] = [f.get('season') for f in date_features]
    df['is_weekend'] = [f.get('is_weekend') for f in date_features]
    
    invalid_dates = df['gregorian_date'].isna().sum()
    total = len(df)
    valid_pct = (total - invalid_dates) / total * 100
    print(f"   ✅ تاریخ‌های معتبر: {total - invalid_dates:,} از {total:,} ({valid_pct:.1f}%)")
    if invalid_dates > 0:
        print(f"   ⚠️ تعداد تاریخ‌های نامعتبر: {invalid_dates:,}")
    
    return df


def add_derived_features(df, sheet_name):
    """افزودن ویژگی‌های مشتق‌شده"""
    if sheet_name != "GasOperationDailyStationReport":
        return df
    
    col1 = "دمای گاز ساعت 6 صبح - نقطه 1"
    col2 = "دمای گاز ساعت 6 صبح - نقطه 2"
    
    if col1 in df.columns and col2 in df.columns:
        print(f"   🌡️ ساخت ویژگی جدید: اختلاف دمای نقطه ۱ و ۲")
        df['اختلاف دمای ساعت 6 صبح'] = df[col2] - df[col1]
        
        valid_diff = df['اختلاف دمای ساعت 6 صبح'].dropna()
        if len(valid_diff) > 0:
            print(f"      میانگین اختلاف: {valid_diff.mean():.2f}")
            print(f"      بیشینه اختلاف: {valid_diff.max():.2f}")
            print(f"      کمینه اختلاف: {valid_diff.min():.2f}")
    
    return df


def normalize_text_columns(df):
    """استانداردسازی ستون‌های متنی (رفع warning)"""
    # استفاده از include='object' به جای list
    try:
        text_cols = df.select_dtypes(include='object').columns
    except:
        text_cols = [c for c in df.columns if df[c].dtype == 'object']
    
    for col in text_cols:
        df[col] = df[col].apply(normalize_persian_text)
    return df


def process_sheet(df, sheet_name):
    """پردازش یک شیت"""
    print(f"\n{'='*60}")
    print(f"🔧 پردازش شیت: {sheet_name}")
    print(f"{'='*60}")
    
    # 1. حذف ستون‌های خطایی
    if sheet_name in DROP_COLUMNS:
        cols_to_drop = [c for c in DROP_COLUMNS[sheet_name] if c in df.columns]
        if cols_to_drop:
            print(f"   🗑️ حذف ستون‌های خطایی: {cols_to_drop}")
            df = df.drop(columns=cols_to_drop)
    
    # 2. تغییر نام ستون‌ها
    if sheet_name in RENAME_COLUMNS:
        rename_map = {k: v for k, v in RENAME_COLUMNS[sheet_name].items() if k in df.columns}
        if rename_map:
            print(f"   ✏️ تغییر نام ستون‌ها...")
            df = df.rename(columns=rename_map)
    
    # 3. استانداردسازی متن
    print(f"   📝 استانداردسازی متن‌ها...")
    df = normalize_text_columns(df)
    
    # 4. یافتن ستون تاریخ
    date_col = None
    for col in df.columns:
        if 'تاریخ' in col.lower() or 'date' in col.lower():
            date_col = col
            break
    
    if date_col:
        df = add_date_features(df, date_col)
    else:
        print(f"   ⚠️ ستون تاریخ یافت نشد!")
    
    # 5. افزودن ویژگی‌های مشتق‌شده
    df = add_derived_features(df, sheet_name)
    
    # 6. تمیز کردن نام ستون‌ها
    clean_cols = {}
    for col in df.columns:
        clean_name = col.strip().replace(' ', '_').replace('.', '_').replace('-', '_')
        clean_cols[col] = clean_name
    df = df.rename(columns=clean_cols)
    
    print(f"   ✅ پردازش کامل شد - {len(df):,} ردیف، {len(df.columns)} ستون")
    return df


def create_indexes(conn, table_name, df):
    """ساخت ایندکس"""
    cursor = conn.cursor()
    
    index_columns = ['gregorian_date', 'shamsi_year', 'shamsi_month', 'season', 'weekday']
    
    if table_name == 'station_consumption_daily':
        index_columns.extend(['استان', 'شهر', 'نام_ایستگاه', 'نوع_مصرف'])
    elif table_name == 'operation_daily_report':
        index_columns.extend(['منبع', 'نوع_منبع', 'دسته_بندی'])
    elif table_name == 'production_daily':
        index_columns.extend(['نام_پالایشگاه', 'نام_محصول'])
    
    for col in index_columns:
        if col in df.columns:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{col} ON {table_name}([{col}])")
            except Exception as e:
                pass
    
    conn.commit()


def build_database():
    """ساخت دیتابیس اصلی"""
    print("=" * 60)
    print("🏗️ ساخت دیتابیس حرفه‌ای گاز (نسخه 2.1)")
    print("=" * 60)
    
    if not Path(EXCEL_FILE).exists():
        print(f"❌ فایل یافت نشد: {EXCEL_FILE}")
        return False
    
    if Path(DB_FILE).exists():
        print(f"🗑️ حذف دیتابیس قبلی: {DB_FILE}")
        Path(DB_FILE).unlink()
    
    conn = sqlite3.connect(DB_FILE)
    
    xls = pd.ExcelFile(EXCEL_FILE)
    
    for sheet_name in xls.sheet_names:
        print(f"\n📖 خواندن شیت: {sheet_name}")
        df = pd.read_excel(xls, sheet_name=sheet_name)
        df.columns = [str(c).strip() for c in df.columns]
        
        try:
            df = process_sheet(df, sheet_name)
            
            table_name = TABLE_NAMES.get(sheet_name, sheet_name.lower().replace(' ', '_'))
            print(f"   💾 ذخیره در جدول: {table_name}")
            df.to_sql(table_name, conn, if_exists='replace', index=False)
            
            create_indexes(conn, table_name, df)
        except Exception as e:
            print(f"   ❌ خطا در پردازش شیت {sheet_name}: {e}")
            import traceback
            traceback.print_exc()
            conn.close()
            return False
    
    # ذخیره متادیتا
    metadata = pd.DataFrame({
        'key': ['last_build_time', 'source_file', 'sheets_count', 'version'],
        'value': [
            datetime.now().isoformat(),
            EXCEL_FILE,
            str(len(xls.sheet_names)),
            '2.1 - رفع باگ KeyError'
        ]
    })
    metadata.to_sql('metadata', conn, if_exists='replace', index=False)
    
    conn.close()
    
    print("\n" + "=" * 60)
    print(f"✅ دیتابیس با موفقیت ساخته شد: {DB_FILE}")
    print("=" * 60)
    return True


def verify_database():
    """بررسی صحت دیتابیس"""
    print("\n🔍 بررسی صحت دیتابیس...")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print(f"\n📋 جداول دیتابیس:")
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        count = cursor.fetchone()[0]
        cursor.execute(f"PRAGMA table_info([{table_name}])")
        cols = cursor.fetchall()
        print(f"   - {table_name}: {count:,} ردیف، {len(cols)} ستون")
    
    # نمایش ستون‌های جدول ایستگاه‌ها
    if any('station_consumption_daily' in t[0] for t in tables):
        print(f"\n📋 ستون‌های جدول ایستگاه‌ها:")
        cursor.execute("PRAGMA table_info(station_consumption_daily)")
        for col in cursor.fetchall():
            print(f"   - {col[1]} ({col[2]})")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = cursor.fetchall()
    print(f"\n📇 تعداد ایندکس‌ها: {len(indexes)}")
    
    # نمونه داده‌ها
    print(f"\n🔬 نمونه داده‌های جدول ایستگاه‌ها:")
    try:
        cursor.execute("""
            SELECT شمسى_سال, شمسى_ماه, شمسى_روز, gregorian_date, 
                   استان, نام_ایستگاه, میزان_مصرف
            FROM station_consumption_daily 
            LIMIT 5
        """)
        for row in cursor.fetchall():
            print(f"   {row}")
    except:
        try:
            cursor.execute("SELECT * FROM station_consumption_daily LIMIT 3")
            for row in cursor.fetchall():
                print(f"   {row[:5]}...")
        except Exception as e:
            print(f"   ⚠️ خطا در نمایش نمونه: {e}")
    
    conn.close()
    
    print("\n✅ بررسی کامل شد!")


if __name__ == "__main__":
    if build_database():
        verify_database()