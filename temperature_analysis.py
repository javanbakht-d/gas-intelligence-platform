"""
Phase 8: Temperature Impact Analysis - نسخه 2.0
با Outlier Filtering قوی و گزارش کیفیت داده
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

DB_FILE = "gas_data.db"

# === محدوده‌های منطقی دما ===
TEMP_MIN_VALID = -30.0   # حداقل دمای منطقی
TEMP_MAX_VALID = 100.0   # حداکثر دمای منطقی


# ============================================================
# 1. Data Loading با فیلتر Outlier
# ============================================================
def load_data():
    """بارگذاری داده‌های مصرف و دما با فیلتر Outlier"""
    print("📥 بارگذاری داده‌ها...")
    
    conn = sqlite3.connect(DB_FILE)
    
    query = """
        SELECT 
            s.gregorian_date,
            s.shamsi_year,
            s.shamsi_month,
            s.season,
            s.استان,
            s.شهر,
            s.نام_ایستگاه,
            s.نوع_مصرف,
            s.میزان_مصرف,
            s.دمای_گاز_ساعت_6_صبح___نقطه_1 as temp_point_1,
            s.دمای_گاز_ساعت_6_صبح___نقطه_2 as temp_point_2,
            s.دمای_گاز_ساعت_18 as temp_18,
            s.فشار_ساعت_6_صبح as pressure_6
        FROM station_consumption_daily s
        WHERE s.میزان_مصرف IS NOT NULL
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    total_records = len(df)
    print(f"✅ {total_records:,} رکورد بارگذاری شد")
    
    # محاسبه دمای متوسط
    temp_cols = ['temp_point_1', 'temp_point_2', 'temp_18']
    df['avg_temperature'] = df[temp_cols].mean(axis=1)
    
    # === Outlier Detection ===
    print(f"\n🔍 بررسی Outlierهای دمایی...")
    
    # رکوردهای با دمای معتبر (قبل از فیلتر)
    has_temp = df['avg_temperature'].notna()
    print(f"   رکوردهای دارای دما: {has_temp.sum():,} ({has_temp.sum()/total_records*100:.1f}%)")
    
    if has_temp.sum() > 0:
        raw_temps = df.loc[has_temp, 'avg_temperature']
        print(f"   🔴 بازه دما قبل از فیلتر: {raw_temps.min():.1f} تا {raw_temps.max():.1f}")
        
        # شناسایی Outlierها
        is_outlier = has_temp & ((df['avg_temperature'] < TEMP_MIN_VALID) | 
                                  (df['avg_temperature'] > TEMP_MAX_VALID))
        n_outliers = is_outlier.sum()
        print(f"   ⚠️ Outlierهای شناسایی‌شده: {n_outliers:,} "
              f"({n_outliers/has_temp.sum()*100:.2f}%)")
        
        # ذخیره آمار Outlierها
        outlier_stats = {
            'total_with_temp': int(has_temp.sum()),
            'outliers_count': int(n_outliers),
            'outliers_pct': float(n_outliers / has_temp.sum() * 100),
            'min_raw': float(raw_temps.min()),
            'max_raw': float(raw_temps.max()),
            'mean_raw': float(raw_temps.mean()),
            'temp_min_valid': TEMP_MIN_VALID,
            'temp_max_valid': TEMP_MAX_VALID,
        }
        
        # فیلتر کردن
        df = df[~is_outlier].copy()
        print(f"   ✅ پس از فیلتر: {len(df):,} رکورد با دمای معتبر")
        
        # آمار دماهای معتبر
        valid_temps = df['avg_temperature'].dropna()
        print(f"   🟢 بازه دما معتبر: {valid_temps.min():.1f} تا {valid_temps.max():.1f}")
        print(f"   🟢 میانگین دما: {valid_temps.mean():.1f}")
        print(f"   🟢 میانه دما: {valid_temps.median():.1f}")
    else:
        outlier_stats = None
    
    return df, outlier_stats


# ============================================================
# 2. Correlation Analysis
# ============================================================
def calculate_correlation(df):
    """محاسبه همبستگی دما و مصرف"""
    print("\n🔗 تحلیل همبستگی...")
    
    valid = df.dropna(subset=['میزان_مصرف', 'avg_temperature'])
    
    if len(valid) < 30:
        print("⚠️ داده کافی برای تحلیل همبستگی نیست")
        return None
    
    # Correlation کلی
    corr_overall = valid['میزان_مصرف'].corr(valid['avg_temperature'])
    print(f"   همبستگی کلی: {corr_overall:.3f}")
    
    # تفسیر
    if abs(corr_overall) < 0.1:
        interpretation = "بسیار ضعیف"
    elif abs(corr_overall) < 0.3:
        interpretation = "ضعیف"
    elif abs(corr_overall) < 0.5:
        interpretation = "متوسط"
    elif abs(corr_overall) < 0.7:
        interpretation = "قوی"
    else:
        interpretation = "بسیار قوی"
    
    direction = "معکوس (با افزایش دما، مصرف کاهش می‌یابد)" if corr_overall < 0 else "مستقیم"
    print(f"   تفسیر: رابطه {interpretation} - {direction}")
    
    # === به تفکیک استان ===
    province_correlations = []
    for province in valid['استان'].dropna().unique():
        province_data = valid[valid['استان'] == province]
        if len(province_data) >= 20:
            corr = province_data['میزان_مصرف'].corr(province_data['avg_temperature'])
            if not np.isnan(corr):
                province_correlations.append({
                    'province': province,
                    'correlation': float(corr),
                    'record_count': int(len(province_data)),
                    'avg_temperature': float(province_data['avg_temperature'].mean()),
                    'avg_consumption': float(province_data['میزان_مصرف'].mean())
                })
    
    # === به تفکیک فصل ===
    season_names = {1: 'بهار', 2: 'تابستان', 3: 'پاییز', 4: 'زمستان'}
    season_correlations = []
    for season in valid['season'].dropna().unique():
        season_data = valid[valid['season'] == season]
        if len(season_data) >= 20:
            corr = season_data['میزان_مصرف'].corr(season_data['avg_temperature'])
            if not np.isnan(corr):
                season_correlations.append({
                    'season': int(season),
                    'season_name': season_names.get(int(season), str(season)),
                    'correlation': float(corr),
                    'record_count': int(len(season_data)),
                    'avg_temperature': float(season_data['avg_temperature'].mean()),
                    'avg_consumption': float(season_data['میزان_مصرف'].mean())
                })
    
    # === به تفکیک نوع مصرف ===
    type_correlations = []
    for ctype in valid['نوع_مصرف'].dropna().unique():
        type_data = valid[valid['نوع_مصرف'] == ctype]
        if len(type_data) >= 20:
            corr = type_data['میزان_مصرف'].corr(type_data['avg_temperature'])
            if not np.isnan(corr):
                type_correlations.append({
                    'consumption_type': ctype,
                    'correlation': float(corr),
                    'record_count': int(len(type_data)),
                    'avg_temperature': float(type_data['avg_temperature'].mean()),
                    'avg_consumption': float(type_data['میزان_مصرف'].mean())
                })
    
    # مرتب‌سازی
    province_correlations = sorted(province_correlations, 
                                    key=lambda x: abs(x['correlation']), 
                                    reverse=True)
    season_correlations = sorted(season_correlations, 
                                  key=lambda x: abs(x['correlation']), 
                                  reverse=True)
    type_correlations = sorted(type_correlations, 
                                key=lambda x: abs(x['correlation']), 
                                reverse=True)
    
    print(f"   استان‌های تحلیل شده: {len(province_correlations)}")
    print(f"   فصل‌های تحلیل شده: {len(season_correlations)}")
    print(f"   انواع مصرف: {len(type_correlations)}")
    
    return {
        'overall_correlation': float(corr_overall),
        'interpretation': interpretation,
        'direction': direction,
        'total_records': int(len(valid)),
        'province_correlations': province_correlations,
        'season_correlations': season_correlations,
        'type_correlations': type_correlations,
    }


# ============================================================
# 3. Temperature Binning
# ============================================================
def create_temperature_bins(df, bin_size=5):
    """دسته‌بندی داده‌ها بر اساس بازه‌های دمایی"""
    print(f"\n📊 Temperature Binning (اندازه بازه: {bin_size} درجه)")
    
    valid = df.dropna(subset=['میزان_مصرف', 'avg_temperature'])
    
    if len(valid) < 30:
        return None
    
    # ایجاد بازه‌های دمایی
    min_temp = int(valid['avg_temperature'].min() // bin_size * bin_size)
    max_temp = int(valid['avg_temperature'].max() // bin_size * bin_size + bin_size)
    
    bins = []
    for start in range(min_temp, max_temp + bin_size, bin_size):
        end = start + bin_size
        bin_data = valid[(valid['avg_temperature'] >= start) & (valid['avg_temperature'] < end)]
        
        if len(bin_data) >= 5:
            bins.append({
                'temp_range': f"{start} تا {end}",
                'temp_start': int(start),
                'temp_end': int(end),
                'temp_mid': float((start + end) / 2),
                'record_count': int(len(bin_data)),
                'avg_consumption': float(bin_data['میزان_مصرف'].mean()),
                'min_consumption': float(bin_data['میزان_مصرف'].min()),
                'max_consumption': float(bin_data['میزان_مصرف'].max()),
                'std_consumption': float(bin_data['میزان_مصرف'].std())
            })
    
    print(f"   تعداد بازه‌های معتبر: {len(bins)}")
    
    # پیدا کردن بازه بحرانی
    if bins:
        peak_bin = max(bins, key=lambda x: x['avg_consumption'])
        min_bin = min(bins, key=lambda x: x['avg_consumption'])
        print(f"   🔥 بیشترین مصرف در بازه: {peak_bin['temp_range']}°C "
              f"(متوسط: {peak_bin['avg_consumption']:,.0f})")
        print(f"   ❄️  کمترین مصرف در بازه: {min_bin['temp_range']}°C "
              f"(متوسط: {min_bin['avg_consumption']:,.0f})")
    
    return bins


# ============================================================
# 4. Elasticity Calculation
# ============================================================
def calculate_elasticity(df):
    """محاسبه کشش دمایی"""
    print("\n📈 محاسبه کشش دمایی (Elasticity)...")
    
    valid = df.dropna(subset=['میزان_مصرف', 'avg_temperature'])
    # فقط مقادیر مثبت برای Log
    valid = valid[(valid['میزان_مصرف'] > 0) & (valid['avg_temperature'] > 0)]
    
    if len(valid) < 30:
        print("⚠️ داده کافی نیست")
        return None
    
    try:
        log_consumption = np.log(valid['میزان_مصرف'])
        log_temp = np.log(valid['avg_temperature'])
        
        x_mean = log_temp.mean()
        y_mean = log_consumption.mean()
        
        numerator = ((log_temp - x_mean) * (log_consumption - y_mean)).sum()
        denominator = ((log_temp - x_mean) ** 2).sum()
        
        elasticity = numerator / denominator if denominator != 0 else 0
        
        print(f"   کشش کلی: {elasticity:.3f}")
        direction = "کاهش" if elasticity < 0 else "افزایش"
        print(f"   تفسیر: هر ۱٪ افزایش دما → {abs(elasticity):.3f}٪ {direction} مصرف")
        
        # به تفکیک استان (top 10)
        province_elasticities = []
        for province in valid['استان'].dropna().unique():
            p_data = valid[valid['استان'] == province]
            if len(p_data) >= 20:
                try:
                    log_c = np.log(p_data['میزان_مصرف'])
                    log_t = np.log(p_data['avg_temperature'])
                    x_m = log_t.mean()
                    y_m = log_c.mean()
                    num = ((log_t - x_m) * (log_c - y_m)).sum()
                    den = ((log_t - x_m) ** 2).sum()
                    e = num / den if den != 0 else 0
                    
                    province_elasticities.append({
                        'province': province,
                        'elasticity': float(e),
                        'record_count': int(len(p_data))
                    })
                except:
                    pass
        
        province_elasticities = sorted(province_elasticities, 
                                        key=lambda x: abs(x['elasticity']), 
                                        reverse=True)
        
        return {
            'overall_elasticity': float(elasticity),
            'interpretation': f"هر ۱٪ افزایش دما → {abs(elasticity):.3f}% {direction} مصرف",
            'province_elasticities': province_elasticities[:10]
        }
    except Exception as e:
        print(f"⚠️ خطا: {e}")
        return None


# ============================================================
# 5. Threshold Detection
# ============================================================
def detect_thresholds(bins):
    """شناسایی نقاط بحرانی دمایی"""
    print("\n🎯 شناسایی نقاط بحرانی دمایی...")
    
    if not bins or len(bins) < 3:
        return None
    
    sorted_bins = sorted(bins, key=lambda x: x['temp_mid'])
    
    thresholds = []
    
    # نقاط اوج و کمینه محلی
    for i in range(1, len(sorted_bins) - 1):
        prev = sorted_bins[i-1]['avg_consumption']
        curr = sorted_bins[i]['avg_consumption']
        next_val = sorted_bins[i+1]['avg_consumption']
        
        # اوج مصرف (local maximum)
        if curr > prev and curr > next_val:
            thresholds.append({
                'type': 'peak',
                'temperature': sorted_bins[i]['temp_mid'],
                'consumption': curr,
                'description': f"اوج مصرف در {sorted_bins[i]['temp_mid']:.0f}°C "
                              f"(مصرف: {curr:,.0f})"
            })
        
        # کمینه مصرف (local minimum)
        if curr < prev and curr < next_val:
            thresholds.append({
                'type': 'valley',
                'temperature': sorted_bins[i]['temp_mid'],
                'consumption': curr,
                'description': f"کمینه مصرف در {sorted_bins[i]['temp_mid']:.0f}°C "
                              f"(مصرف: {curr:,.0f})"
            })
    
    # همیشه بیشترین و کمترین را اضافه کن
    max_bin = max(sorted_bins, key=lambda x: x['avg_consumption'])
    min_bin = min(sorted_bins, key=lambda x: x['avg_consumption'])
    
    # فقط اگر در لیست نیست
    existing_temps = [t['temperature'] for t in thresholds]
    if max_bin['temp_mid'] not in existing_temps:
        thresholds.append({
            'type': 'global_peak',
            'temperature': max_bin['temp_mid'],
            'consumption': max_bin['avg_consumption'],
            'description': f"🔥 بیشترین مصرف کلی در {max_bin['temp_mid']:.0f}°C"
        })
    if min_bin['temp_mid'] not in existing_temps:
        thresholds.append({
            'type': 'global_valley',
            'temperature': min_bin['temp_mid'],
            'consumption': min_bin['avg_consumption'],
            'description': f"❄️  کمترین مصرف کلی در {min_bin['temp_mid']:.0f}°C"
        })
    
    # محدود کردن به ۱۰ نقطه اصلی (حذف نقاط فرعی)
    if len(thresholds) > 10:
        thresholds = sorted(thresholds, 
                           key=lambda x: abs(x['consumption']), 
                           reverse=True)[:10]
    
    print(f"   {len(thresholds)} نقطه بحرانی اصلی شناسایی شد")
    for t in thresholds[:5]:
        print(f"   - {t['description']}")
    
    return thresholds


# ============================================================
# 6. Save Results
# ============================================================
def save_to_db(outlier_stats, correlations, bins, elasticity, thresholds):
    """ذخیره نتایج در دیتابیس"""
    print("\n💾 ذخیره نتایج در دیتابیس...")
    
    conn = sqlite3.connect(DB_FILE)
    
    # 1. آمار Outlier
    if outlier_stats:
        pd.DataFrame([outlier_stats]).to_sql(
            'temperature_outlier_stats', conn, if_exists='replace', index=False
        )
    
    # 2. خلاصه همبستگی
    if correlations:
        summary_df = pd.DataFrame([{
            'overall_correlation': correlations['overall_correlation'],
            'interpretation': correlations['interpretation'],
            'direction': correlations['direction'],
            'total_records': correlations['total_records'],
            'generated_at': datetime.now().isoformat()
        }])
        summary_df.to_sql('temperature_impact_summary', conn, if_exists='replace', index=False)
        
        # 3. همبستگی استان‌ها
        if correlations['province_correlations']:
            pd.DataFrame(correlations['province_correlations']).to_sql(
                'temperature_by_province', conn, if_exists='replace', index=False
            )
        
        # 4. همبستگی فصلی
        if correlations['season_correlations']:
            pd.DataFrame(correlations['season_correlations']).to_sql(
                'temperature_by_season', conn, if_exists='replace', index=False
            )
        
        # 5. همبستگی نوع مصرف
        if correlations['type_correlations']:
            pd.DataFrame(correlations['type_correlations']).to_sql(
                'temperature_by_type', conn, if_exists='replace', index=False
            )
    
    # 6. بازه‌های دمایی
    if bins:
        pd.DataFrame(bins).to_sql(
            'temperature_bins', conn, if_exists='replace', index=False
        )
    
    # 7. کشش دمایی
    if elasticity:
        pd.DataFrame([{
            'overall_elasticity': elasticity['overall_elasticity'],
            'interpretation': elasticity['interpretation']
        }]).to_sql('temperature_elasticity', conn, if_exists='replace', index=False)
        
        if elasticity['province_elasticities']:
            pd.DataFrame(elasticity['province_elasticities']).to_sql(
                'elasticity_by_province', conn, if_exists='replace', index=False
            )
    
    # 8. نقاط بحرانی
    if thresholds:
        pd.DataFrame(thresholds).to_sql(
            'temperature_thresholds', conn, if_exists='replace', index=False
        )
    
    conn.commit()
    conn.close()
    
    print("✅ نتایج در دیتابیس ذخیره شدند")


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 70)
    print("🌡️  TEMPERATURE IMPACT ANALYSIS - نسخه 2.0 (با Outlier Filtering)")
    print("=" * 70)
    
    # بارگذاری داده با فیلتر Outlier
    df, outlier_stats = load_data()
    
    if len(df) < 100:
        print("❌ داده کافی پس از فیلتر وجود ندارد!")
        return
    
    # تحلیل همبستگی
    correlations = calculate_correlation(df)
    if not correlations:
        print("❌ تحلیل همبستگی شکست خورد")
        return
    
    # بازه‌بندی دمایی
    bins = create_temperature_bins(df, bin_size=5)
    
    # کشش دمایی
    elasticity = calculate_elasticity(df)
    
    # نقاط بحرانی
    thresholds = detect_thresholds(bins)
    
    # === گزارش نهایی ===
    print("\n" + "=" * 70)
    print("📋 گزارش نهایی تحلیل اثر دما")
    print("=" * 70)
    
    if outlier_stats:
        print(f"\n🔴 کیفیت داده‌های دمایی:")
        print(f"   رکوردهای دارای دما: {outlier_stats['total_with_temp']:,}")
        print(f"   Outlierهای حذف‌شده: {outlier_stats['outliers_count']:,} "
              f"({outlier_stats['outliers_pct']:.2f}%)")
        print(f"   بازه معتبر: {outlier_stats['temp_min_valid']} تا "
              f"{outlier_stats['temp_max_valid']} درجه")
    
    print(f"\n🔗 همبستگی کلی دما-مصرف: {correlations['overall_correlation']:.3f}")
    print(f"   تفسیر: {correlations['interpretation']} - {correlations['direction']}")
    
    if correlations['province_correlations']:
        print(f"\n🏆 حساس‌ترین استان‌ها به دما (Top 5):")
        for i, p in enumerate(correlations['province_correlations'][:5], 1):
            direction = "↓" if p['correlation'] < 0 else "↑"
            print(f"   {i}. {p['province']}: {p['correlation']:.3f} ({direction}) "
                  f"[{p['record_count']} رکورد]")
    
    if correlations['season_correlations']:
        print(f"\n📅 تحلیل فصلی:")
        for s in correlations['season_correlations']:
            direction = "↓" if s['correlation'] < 0 else "↑"
            print(f"   - {s['season_name']}: {s['correlation']:.3f} ({direction}) "
                  f"[دما: {s['avg_temperature']:.1f}°C، مصرف: {s['avg_consumption']:,.0f}]")
    
    if correlations['type_correlations']:
        print(f"\n⚙️ حساس‌ترین انواع مصرف به دما (Top 5):")
        for t in correlations['type_correlations'][:5]:
            direction = "↓" if t['correlation'] < 0 else "↑"
            print(f"   - {t['consumption_type']}: {t['correlation']:.3f} ({direction})")
    
    if elasticity:
        print(f"\n📊 کشش دمایی: {elasticity['overall_elasticity']:.3f}")
        print(f"   {elasticity['interpretation']}")
    
    # ذخیره در دیتابیس
    save_to_db(outlier_stats, correlations, bins, elasticity, thresholds)
    
    print("\n" + "=" * 70)
    print("✅ تحلیل اثر دما با موفقیت انجام شد!")
    print("=" * 70)
    
    return outlier_stats, correlations, bins, elasticity, thresholds


if __name__ == "__main__":
    main()