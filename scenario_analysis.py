"""
Phase 9: Scenario Analysis Engine
تحلیل سناریوهای مختلف دمایی و اثر آن بر مصرف
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

DB_FILE = "gas_data.db"


# ============================================================
# 1. Load Base Data & Elasticity
# ============================================================
def load_base_data():
    """بارگذاری داده‌های پایه و کشش دمایی"""
    print("📥 بارگذاری داده‌های پایه...")
    
    conn = sqlite3.connect(DB_FILE)
    
    # بارگذاری کشش کلی
    try:
        elasticity_df = pd.read_sql_query("SELECT overall_elasticity FROM temperature_elasticity", conn)
        overall_elasticity = float(elasticity_df['overall_elasticity'].iloc[0])
        print(f"   کشش کلی: {overall_elasticity:.3f}")
    except:
        print("   ⚠️ کشش دمایی محاسبه نشده - از مقدار پیش‌فرض استفاده می‌شود")
        overall_elasticity = -0.2  # مقدار پیش‌فرض معقول
    
    # بارگذاری کشش به تفکیک استان
    try:
        province_elasticity_df = pd.read_sql_query(
            "SELECT province, elasticity FROM elasticity_by_province", conn
        )
        province_elasticity = dict(zip(
            province_elasticity_df['province'],
            province_elasticity_df['elasticity']
        ))
        print(f"   کشش برای {len(province_elasticity)} استان محاسبه شده")
    except:
        province_elasticity = {}
        print("   ⚠️ کشش استانی موجود نیست")
    
    # بارگذاری داده‌های مصرف اخیر (برای محاسبه baseline)
    query = """
        SELECT 
            استان,
            نوع_مصرف,
            AVG(میزان_مصرف) as avg_consumption,
            AVG(COALESCE(دمای_گاز_ساعت_6_صبح___نقطه_1, دمای_گاز_ساعت_18)) as avg_temperature
        FROM station_consumption_daily
        WHERE میزان_مصرف IS NOT NULL
          AND gregorian_date >= date('now', '-30 days')
        GROUP BY استان, نوع_مصرف
        HAVING avg_consumption IS NOT NULL AND avg_temperature IS NOT NULL
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"   ✅ {len(df)} رکورد گروه‌بندی‌شده بارگذاری شد")
    
    return df, overall_elasticity, province_elasticity


# ============================================================
# 2. Calculate Scenario Impact
# ============================================================
def calculate_scenario_impact(df, overall_elasticity, province_elasticity,
                               temperature_change):
    """
    محاسبه اثر سناریو بر مصرف
    
    فرمول Elasticity:
    %ΔConsumption = Elasticity × %ΔTemperature
    
    مثال:
    اگر elasticity = -0.2 و دما 5 درجه از 20 کاهش یابد (25% کاهش)
    %ΔConsumption = -0.2 × (-25%) = +5% (افزایش 5%)
    """
    results = []
    
    for _, row in df.iterrows():
        province = row['استان']
        consumption_type = row['نوع_مصرف']
        base_consumption = row['avg_consumption']
        base_temp = row['avg_temperature']
        
        if base_consumption <= 0 or base_temp <= 0:
            continue
        
        # استفاده از کشش استانی (اگر موجود است) در غیر این صورت کشش کلی
        elasticity = province_elasticity.get(province, overall_elasticity)
        
        # محاسبه درصد تغییر دما
        temp_change_pct = (temperature_change / base_temp) * 100
        
        # محاسبه درصد تغییر مصرف
        consumption_change_pct = elasticity * temp_change_pct
        
        # محاسبه مقدار مصرف جدید
        new_consumption = base_consumption * (1 + consumption_change_pct / 100)
        consumption_diff = new_consumption - base_consumption
        
        results.append({
            'province': province,
            'consumption_type': consumption_type,
            'base_consumption': float(base_consumption),
            'new_consumption': float(new_consumption),
            'consumption_change_pct': float(consumption_change_pct),
            'consumption_diff': float(consumption_diff),
            'base_temperature': float(base_temp),
            'new_temperature': float(base_temp + temperature_change),
            'temperature_change': float(temperature_change),
            'elasticity_used': float(elasticity)
        })
    
    return pd.DataFrame(results)


# ============================================================
# 3. Run All Scenarios
# ============================================================
def run_all_scenarios(df, overall_elasticity, province_elasticity):
    """اجرای همه سناریوهای از پیش تعریف‌شده"""
    print("\n🎯 اجرای سناریوهای مختلف...")
    
    scenarios = [
        {'name': 'عادی (Baseline)', 'temp_change': 0, 'description': 'بدون تغییر دما'},
        {'name': 'کمی سردتر', 'temp_change': -2, 'description': '۲ درجه سردتر از معمول'},
        {'name': 'سردتر (هشدار)', 'temp_change': -5, 'description': '۵ درجه سردتر - احتمال بحران'},
        {'name': 'بسیار سردتر (بحرانی)', 'temp_change': -10, 'description': '۱۰ درجه سردتر - شرایط بحرانی'},
        {'name': 'کمی گرم‌تر', 'temp_change': 2, 'description': '۲ درجه گرم‌تر از معمول'},
        {'name': 'گرم‌تر', 'temp_change': 5, 'description': '۵ درجه گرم‌تر از معمول'},
        {'name': 'بسیار گرم‌تر', 'temp_change': 10, 'description': '۱۰ درجه گرم‌تر از معمول'},
    ]
    
    all_results = []
    
    for scenario in scenarios:
        print(f"   📊 سناریو: {scenario['name']} ({scenario['temp_change']:+d}°C)")
        
        result_df = calculate_scenario_impact(
            df, overall_elasticity, province_elasticity,
            scenario['temp_change']
        )
        
        result_df['scenario_name'] = scenario['name']
        result_df['scenario_description'] = scenario['description']
        result_df['temp_change_category'] = scenario['temp_change']
        
        # خلاصه سناریو
        if len(result_df) > 0:
            total_base = result_df['base_consumption'].sum()
            total_new = result_df['new_consumption'].sum()
            total_diff = total_new - total_base
            total_change_pct = (total_diff / total_base * 100) if total_base > 0 else 0
            
            print(f"      🔢 کل مصرف: {total_base:,.0f} → {total_new:,.0f} "
                  f"({total_change_pct:+.2f}%)")
        
        all_results.append(result_df)
    
    return pd.concat(all_results, ignore_index=True), scenarios


# ============================================================
# 4. Generate Insights
# ============================================================
def generate_insights(scenario_results):
    """تولید بینش‌های کلیدی"""
    print("\n💡 تولید بینش‌های کلیدی...")
    
    insights = []
    
    # سناریوهای بحرانی (کاهش 10 درجه)
    critical = scenario_results[scenario_results['temp_change_category'] == -10]
    if len(critical) > 0:
        # پرمصرف‌ترین استان در شرایط بحرانی
        province_summary = critical.groupby('province').agg({
            'new_consumption': 'sum',
            'consumption_diff': 'sum'
        }).sort_values('consumption_diff', ascending=False)
        
        if len(province_summary) > 0:
            top_province = province_summary.index[0]
            top_increase = province_summary.iloc[0]['consumption_diff']
            
            insights.append({
                'type': 'critical_province',
                'province': top_province,
                'insight': f"در شرایط ۱۰ درجه سردتر، استان {top_province} بیشترین "
                          f"افزایش مصرف ({top_increase:,.0f}) را خواهد داشت",
                'severity': 'high'
            })
        
        # بیشترین درصد تغییر
        province_pct = critical.groupby('province').agg({
            'consumption_change_pct': 'mean'
        }).sort_values('consumption_change_pct', ascending=False)
        
        if len(province_pct) > 0:
            most_sensitive = province_pct.index[0]
            sensitivity = province_pct.iloc[0]['consumption_change_pct']
            
            insights.append({
                'type': 'most_sensitive_province',
                'province': most_sensitive,
                'insight': f"استان {most_sensitive} حساس‌ترین به تغییر دما است "
                          f"(+{sensitivity:.2f}% در شرایط ۱۰- درجه)",
                'severity': 'medium'
            })
    
    # تحلیل نوع مصرف
    type_summary = scenario_results[scenario_results['temp_change_category'] == -5].groupby(
        'consumption_type'
    ).agg({
        'consumption_change_pct': 'mean',
        'consumption_diff': 'sum'
    })
    
    if len(type_summary) > 0:
        most_affected_type = type_summary['consumption_change_pct'].idxmax()
        max_pct = type_summary.loc[most_affected_type, 'consumption_change_pct']
        
        insights.append({
            'type': 'most_affected_type',
            'consumption_type': most_affected_type,
            'insight': f"نوع مصرف '{most_affected_type}' بیشترین حساسیت به سرما را دارد "
                      f"(+{max_pct:.2f}%)",
            'severity': 'medium'
        })
    
    for i, insight in enumerate(insights, 1):
        print(f"   {i}. {insight['insight']}")
    
    return insights


# ============================================================
# 5. Save to Database
# ============================================================
def save_to_db(scenario_results, insights, scenarios):
    """ذخیره نتایج در دیتابیس"""
    print("\n💾 ذخیره نتایج در دیتابیس...")
    
    conn = sqlite3.connect(DB_FILE)
    
    # 1. جدول نتایج سناریو
    scenario_results.to_sql('scenario_results', conn, if_exists='replace', index=False)
    
    # 2. جدول خلاصه سناریوها
    summary_rows = []
    for scenario in scenarios:
        scenario_data = scenario_results[
            scenario_results['temp_change_category'] == scenario['temp_change']
        ]
        
        if len(scenario_data) > 0:
            total_base = scenario_data['base_consumption'].sum()
            total_new = scenario_data['new_consumption'].sum()
            total_diff = total_new - total_base
            change_pct = (total_diff / total_base * 100) if total_base > 0 else 0
            
            summary_rows.append({
                'scenario_name': scenario['name'],
                'temp_change': scenario['temp_change'],
                'description': scenario['description'],
                'total_base_consumption': float(total_base),
                'total_new_consumption': float(total_new),
                'total_diff': float(total_diff),
                'change_pct': float(change_pct),
                'generated_at': datetime.now().isoformat()
            })
    
    pd.DataFrame(summary_rows).to_sql(
        'scenario_summary', conn, if_exists='replace', index=False
    )
    
    # 3. جدول بینش‌ها
    if insights:
        pd.DataFrame(insights).to_sql(
            'scenario_insights', conn, if_exists='replace', index=False
        )
    
    conn.commit()
    conn.close()
    
    print("✅ نتایج در دیتابیس ذخیره شدند")


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 70)
    print("🎯 SCENARIO ANALYSIS ENGINE - Phase 9")
    print("=" * 70)
    
    # بارگذاری داده‌ها
    df, overall_elasticity, province_elasticity = load_base_data()
    
    if len(df) == 0:
        print("❌ داده کافی برای سناریو وجود ندارد!")
        return
    
    # اجرای سناریوها
    scenario_results, scenarios = run_all_scenarios(
        df, overall_elasticity, province_elasticity
    )
    
    # تولید بینش‌ها
    insights = generate_insights(scenario_results)
    
    # گزارش نهایی
    print("\n" + "=" * 70)
    print("📋 گزارش نهایی تحلیل سناریو")
    print("=" * 70)
    
    print(f"\n🎯 سناریوهای اجرا شده: {len(scenarios)}")
    for s in scenarios:
        scenario_data = scenario_results[
            scenario_results['scenario_name'] == s['name']
        ]
        if len(scenario_data) > 0:
            total_base = scenario_data['base_consumption'].sum()
            total_new = scenario_data['new_consumption'].sum()
            diff = total_new - total_base
            pct = (diff / total_base * 100) if total_base > 0 else 0
            
            emoji = "🌡️" if s['temp_change'] == 0 else \
                    "❄️" if s['temp_change'] < 0 else "🔥"
            
            print(f"   {emoji} {s['name']:30s} | "
                  f"{s['temp_change']:+3d}°C | "
                  f"تغییر: {pct:+.2f}% | "
                  f"Δ: {diff:+,.0f}")
    
    # ذخیره
    save_to_db(scenario_results, insights, scenarios)
    
    print("\n" + "=" * 70)
    print("✅ تحلیل سناریو با موفقیت انجام شد!")
    print("=" * 70)
    
    return scenario_results, insights


if __name__ == "__main__":
    main()