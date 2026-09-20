"""
تولید گزارش وب زیبا و حرفه‌ای تحلیل کیفیت داده
با قابلیت تبدیل به PDF از طریق مرورگر
"""

import json
from pathlib import Path
import jdatetime

INPUT_JSON = "data_quality_metrics.json"
OUTPUT_HTML = "Data_Quality_Report.html"


def load_metrics():
    """بارگذاری داده‌های کیفیت"""
    if not Path(INPUT_JSON).exists():
        print("❌ فایل data_quality_metrics.json یافت نشد!")
        print("   لطفاً ابتدا data_quality_assessment.py را اجرا کنید.")
        return None
    
    with open(INPUT_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_score_color(score):
    """تعیین رنگ بر اساس امتیاز"""
    if score >= 80:
        return "#10b981"  # سبز
    elif score >= 60:
        return "#f59e0b"  # نارنجی
    else:
        return "#ef4444"  # قرمز


def get_score_label(score):
    """برچسب وضعیت"""
    if score >= 80:
        return "عالی"
    elif score >= 70:
        return "خوب"
    elif score >= 50:
        return "متوسط"
    else:
        return "بحرانی"


def generate_html(data):
    """تولید HTML زیبا"""
    
    overall_scores = data['overall_scores']
    total_records = data['total_records']
    temporal = data['temporal_report']
    geo = data['geographic_report']
    column_profiles = data['column_profiles']
    expected_domains = data['expected_domains']
    recommendations = data['recommendations']
    
    avg_score = sum(overall_scores.values()) / len(overall_scores)
    jalali_date = jdatetime.datetime.now().strftime('%Y/%m/%d')
    
    # مرتب‌سازی پیشنهادات بر اساس اولویت
    priority_order = {'بحرانی 🔴': 0, 'بالا 🟡': 1, 'متوسط 🟢': 2}
    sorted_recs = sorted(recommendations, key=lambda x: priority_order.get(x['priority'], 3))
    
    html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>گزارش کیفیت داده‌ها</title>
    <link href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn-font@v33.003/Vazirmatn-font-face.css" rel="stylesheet" />
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        
        body {{
            font-family: 'Vazirmatn', Tahoma, sans-serif;
            background: #f5f7fa;
            color: #1a202c;
            line-height: 1.7;
            font-size: 14px;
        }}
        
        .page {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            padding: 50px;
            min-height: 100vh;
        }}
        
        /* Header */
        .report-header {{
            text-align: center;
            padding: 30px 0;
            border-bottom: 4px solid #2563eb;
            margin-bottom: 40px;
        }}
        
        .report-header .logo {{
            font-size: 60px;
            margin-bottom: 10px;
        }}
        
        .report-header h1 {{
            font-size: 28px;
            color: #1e3a8a;
            margin-bottom: 10px;
        }}
        
        .report-header .subtitle {{
            color: #6b7280;
            font-size: 15px;
        }}
        
        .report-meta {{
            display: flex;
            justify-content: space-around;
            margin-top: 25px;
            padding: 15px;
            background: #f0f9ff;
            border-radius: 10px;
            flex-wrap: wrap;
            gap: 15px;
        }}
        
        .report-meta .meta-item {{
            text-align: center;
        }}
        
        .report-meta .meta-label {{
            font-size: 11px;
            color: #6b7280;
        }}
        
        .report-meta .meta-value {{
            font-size: 14px;
            font-weight: 700;
            color: #1e3a8a;
        }}
        
        /* Sections */
        .section {{
            margin-bottom: 40px;
            page-break-inside: avoid;
        }}
        
        .section-title {{
            font-size: 20px;
            color: #1e3a8a;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e5e7eb;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .section-title .icon {{
            font-size: 24px;
        }}
        
        /* Score Cards */
        .score-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }}
        
        .score-card {{
            background: white;
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            transition: transform 0.2s;
        }}
        
        .score-card .score-value {{
            font-size: 36px;
            font-weight: 700;
            margin-bottom: 5px;
        }}
        
        .score-card .score-label {{
            font-size: 13px;
            color: #6b7280;
        }}
        
        .score-card .score-status {{
            display: inline-block;
            padding: 3px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 700;
            margin-top: 10px;
            color: white;
        }}
        
        /* Score Bar */
        .score-bar {{
            height: 8px;
            background: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 10px;
        }}
        
        .score-bar-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s;
        }}
        
        /* Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 13px;
        }}
        
        th {{
            background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
            color: white;
            padding: 12px 15px;
            text-align: right;
            font-weight: 700;
        }}
        
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #e5e7eb;
            text-align: right;
        }}
        
        tbody tr:nth-child(even) {{
            background: #f9fafb;
        }}
        
        tbody tr:hover {{
            background: #eff6ff;
        }}
        
        /* Badges */
        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
        }}
        
        .badge-critical {{ background: #fee2e2; color: #991b1b; }}
        .badge-high {{ background: #fef3c7; color: #92400e; }}
        .badge-medium {{ background: #dbeafe; color: #1e40af; }}
        .badge-good {{ background: #d1fae5; color: #065f46; }}
        
        /* Info Box */
        .info-box {{
            background: #f0f9ff;
            border-right: 4px solid #2563eb;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        
        .warning-box {{
            background: #fef3c7;
            border-right: 4px solid #f59e0b;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        
        .critical-box {{
            background: #fee2e2;
            border-right: 4px solid #ef4444;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        
        .box-title {{
            font-weight: 700;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        /* List */
        .checklist {{
            list-style: none;
            padding: 0;
        }}
        
        .checklist li {{
            padding: 10px 15px;
            margin-bottom: 8px;
            background: #f9fafb;
            border-radius: 8px;
            border-right: 3px solid #2563eb;
        }}
        
        .checklist li.priority-critical {{ border-right-color: #ef4444; }}
        .checklist li.priority-high {{ border-right-color: #f59e0b; }}
        .checklist li.priority-medium {{ border-right-color: #10b981; }}
        
        .checklist .item-title {{
            font-weight: 700;
            color: #1e3a8a;
        }}
        
        .checklist .item-desc {{
            color: #6b7280;
            font-size: 13px;
        }}
        
        /* Footer */
        .report-footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 2px solid #e5e7eb;
            text-align: center;
            color: #6b7280;
            font-size: 12px;
        }}
        
        /* Print Button */
        .print-controls {{
            position: fixed;
            top: 20px;
            left: 20px;
            z-index: 1000;
            display: flex;
            gap: 10px;
        }}
        
        .btn {{
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-family: inherit;
            font-weight: 700;
            font-size: 14px;
            transition: all 0.2s;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }}
        
        .btn-primary {{
            background: #2563eb;
            color: white;
        }}
        
        .btn-primary:hover {{
            background: #1d4ed8;
            transform: translateY(-2px);
        }}
        
        /* Print Styles */
        @media print {{
            body {{ background: white; }}
            .page {{ 
                max-width: 100%; 
                padding: 30px;
                box-shadow: none;
            }}
            .print-controls {{ display: none; }}
            .section {{ page-break-inside: avoid; }}
            table {{ font-size: 11px; }}
            th, td {{ padding: 8px 10px; }}
        }}
    </style>
</head>
<body>
    <div class="print-controls">
        <button class="btn btn-primary" onclick="window.print()">🖨️ ذخیره به صورت PDF</button>
    </div>
    
    <div class="page">
        <!-- Header -->
        <div class="report-header">
            <div class="logo">🔥</div>
            <h1>گزارش جامع تحلیل کیفیت داده‌ها</h1>
            <div class="subtitle">سامانه هوشمند پایش و تحلیل گاز</div>
            
            <div class="report-meta">
                <div class="meta-item">
                    <div class="meta-label">تاریخ تولید</div>
                    <div class="meta-value">{jalali_date}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">تعداد کل رکوردها</div>
                    <div class="meta-value">{total_records:,}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">تعداد شیت‌ها</div>
                    <div class="meta-value">{len(overall_scores)}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">امتیاز کیفیت کلی</div>
                    <div class="meta-value">{avg_score:.1f} از ۱۰۰</div>
                </div>
            </div>
        </div>
        
        <!-- Executive Summary -->
        <div class="section">
            <div class="section-title">
                <span class="icon">📊</span>
                <span>۱. خلاصه اجرایی</span>
            </div>
            
            <div class="score-grid">
"""
    
    # کارت‌های امتیاز هر شیت
    for sheet, score in overall_scores.items():
        color = get_score_color(score)
        label = get_score_label(score)
        html += f"""
                <div class="score-card">
                    <div class="score-value" style="color: {color};">{score}</div>
                    <div class="score-label">{sheet}</div>
                    <div class="score-status" style="background: {color};">{label}</div>
                    <div class="score-bar">
                        <div class="score-bar-fill" style="width: {score}%; background: {color};"></div>
                    </div>
                </div>
"""
    
    html += """
            </div>
"""
    
    # وضعیت کلی
    if avg_score >= 80:
        box_class = "info-box"
        box_icon = "🟢"
        box_text = "کیفیت داده‌ها خوب است اما نیاز به بهبود دارد."
    elif avg_score >= 60:
        box_class = "warning-box"
        box_icon = "🟡"
        box_text = "کیفیت داده‌ها متوسط است و نیاز به توجه جدی دارد."
    else:
        box_class = "critical-box"
        box_icon = "🔴"
        box_text = "کیفیت داده‌ها نیازمند اصلاح فوری است."
    
    html += f"""
            <div class="{box_class}">
                <div class="box-title">{box_icon} وضعیت کلی</div>
                <div>{box_text}</div>
            </div>
        </div>
        
        <!-- Data Quantity -->
        <div class="section">
            <div class="section-title">
                <span class="icon">📈</span>
                <span>۲. کمیت داده‌ها</span>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>شیت</th>
                        <th>تعداد رکورد</th>
                        <th>تعداد ستون</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # جدول کمیت داده‌ها
    for sheet, profiles in column_profiles.items():
        records = profiles[0]['total_rows'] if profiles else 0
        cols = len(profiles)
        html += f"""
                    <tr>
                        <td><strong>{sheet}</strong></td>
                        <td>{records:,}</td>
                        <td>{cols}</td>
                    </tr>
"""
    
    html += """
                </tbody>
            </table>
            
            <div class="info-box">
                <div class="box-title">📅 پوشش زمانی</div>
"""
    
    for sheet, info in temporal.items():
        html += f"""
                <div style="margin-bottom: 10px;">
                    <strong>{sheet}</strong><br>
                    بازه: {info['year_range']} | 
                    تعداد ماه‌ها: {info['unique_year_months']} | 
                    میانگین رکورد در ماه: {info['records_per_month_avg']:,.0f}
                </div>
"""
    
    html += """
            </div>
        </div>
        
        <!-- Geographic Coverage -->
        <div class="section">
            <div class="section-title">
                <span class="icon">🗺️</span>
                <span>۳. پوشش جغرافیایی</span>
            </div>
            
            <div class="score-grid">
"""
    
    if 'provinces' in geo:
        html += f"""
                <div class="score-card">
                    <div class="score-value" style="color: #2563eb;">{geo['provinces']['count']}</div>
                    <div class="score-label">استان</div>
                </div>
"""
    
    if 'stations' in geo:
        html += f"""
                <div class="score-card">
                    <div class="score-value" style="color: #10b981;">{geo['stations']['count']}</div>
                    <div class="score-label">ایستگاه</div>
                </div>
"""
    
    if 'refineries' in geo:
        html += f"""
                <div class="score-card">
                    <div class="score-value" style="color: #f59e0b;">{geo['refineries']['count']}</div>
                    <div class="score-label">پالایشگاه</div>
                </div>
"""
    
    if 'sources' in geo:
        html += f"""
                <div class="score-card">
                    <div class="score-value" style="color: #8b5cf6;">{geo['sources']['count']}</div>
                    <div class="score-label">منبع</div>
                </div>
"""
    
    html += """
            </div>
        </div>
        
        <!-- Column Quality -->
        <div class="section">
            <div class="section-title">
                <span class="icon">🔍</span>
                <span>۴. کیفیت ستون‌ها</span>
            </div>
"""
    
    # جدول کیفیت ستون‌ها برای هر شیت
    for sheet, profiles in column_profiles.items():
        html += f"""
            <h3 style="margin: 20px 0 10px; color: #1e3a8a;">{sheet}</h3>
            <table>
                <thead>
                    <tr>
                        <th>ستون</th>
                        <th>مفقود٪</th>
                        <th>صفر٪</th>
                        <th>پرت٪</th>
                        <th>امتیاز</th>
                        <th>وضعیت</th>
                    </tr>
                </thead>
                <tbody>
"""
        
        for p in profiles:
            zero_pct = p.get('zero_pct', '-')
            outlier_pct = p.get('extreme_outliers_pct', '-')
            score = p['quality_score']
            color = get_score_color(score)
            status_class = 'badge-good' if score >= 70 else 'badge-medium' if score >= 50 else 'badge-critical'
            
            html += f"""
                    <tr>
                        <td><strong>{p['column']}</strong></td>
                        <td>{p['missing_pct']}%</td>
                        <td>{zero_pct}{'%' if zero_pct != '-' else ''}</td>
                        <td>{outlier_pct}{'%' if outlier_pct != '-' else ''}</td>
                        <td style="color: {color}; font-weight: 700;">{score}</td>
                        <td><span class="badge {status_class}">{p['status']}</span></td>
                    </tr>
"""
        
        html += """
                </tbody>
            </table>
"""
    
    html += """
        </div>
        
        <!-- Missing Data Domains -->
        <div class="section">
            <div class="section-title">
                <span class="icon">📋</span>
                <span>۵. حوزه‌های داده‌ای موجود نیست</span>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>حوزه داده‌ای</th>
                        <th>توضیح</th>
                        <th>اثرگذاری</th>
                        <th>اولویت</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    for domain, info in expected_domains.items():
        priority_class = 'badge-critical' if info['priority'] == 'بحرانی' else 'badge-high' if info['priority'] == 'بالا' else 'badge-medium'
        html += f"""
                    <tr>
                        <td><strong>{domain}</strong></td>
                        <td>{info['description']}</td>
                        <td>{info['impact']}</td>
                        <td><span class="badge {priority_class}">{info['priority']}</span></td>
                    </tr>
"""
    
    html += """
                </tbody>
            </table>
        </div>
        
        <!-- Recommendations -->
        <div class="section">
            <div class="section-title">
                <span class="icon">💡</span>
                <span>۶. پیشنهادات عملی (اولویت‌بندی شده)</span>
            </div>
            
            <ul class="checklist">
"""
    
    for i, rec in enumerate(sorted_recs, 1):
        priority_class = 'priority-critical' if 'بحرانی' in rec['priority'] else 'priority-high' if 'بالا' in rec['priority'] else 'priority-medium'
        html += f"""
                <li class="{priority_class}">
                    <div class="item-title">{i}. {rec['priority']} - {rec['issue']}</div>
                    <div class="item-desc">
                        <strong>دسته:</strong> {rec['category']}<br>
                        <strong>اقدام:</strong> {rec['action']}
                    </div>
                </li>
"""
    
    html += """
            </ul>
        </div>
        
        <!-- Roadmap -->
        <div class="section">
            <div class="section-title">
                <span class="icon">🚀</span>
                <span>۷. نقشه راه بهبود</span>
            </div>
            
            <div class="critical-box">
                <div class="box-title">🔴 اولویت‌های فوری (۱ ماه آینده)</div>
                <ol>
                    <li>اصلاح داده‌های پرت شدید (دمای ۱۲۷,۷۳۷ درجه)</li>
                    <li>حذف ستون‌های ۱۰۰٪ خالی</li>
                    <li>مستندسازی واحد اندازه‌گیری هر ستون</li>
                    <li>افزودن داده‌های هواشناسی محیطی</li>
                </ol>
            </div>
            
            <div class="warning-box">
                <div class="box-title">🟡 اولویت‌های میان‌مدت (۳ ماه آینده)</div>
                <ol>
                    <li>افزایش پوشش زمانی به حداقل ۲ سال</li>
                    <li>افزودن داده‌های ساعتی</li>
                    <li>افزودن شناسه‌های یکتا و مختصات جغرافیایی</li>
                </ol>
            </div>
            
            <div class="info-box">
                <div class="box-title">🟢 اولویت‌های بلندمدت (۶ ماه آینده)</div>
                <ol>
                    <li>اتصال به سامانه‌های بلادرنگ (SCADA)</li>
                    <li>پیاده‌سازی اعتبارسنجی خودکار در زمان ثبت</li>
                    <li>افزودن متادیتای کامل و استاندارد</li>
                </ol>
            </div>
        </div>
        
        <!-- Footer -->
        <div class="report-footer">
            <p><strong>این گزارش به صورت خودکار توسط سامانه تحلیل کیفیت داده تولید شده است.</strong></p>
            <p>برای ذخیره به صورت PDF: دکمه بالا را بزنید یا از مرورگر با کلیدهای <kbd>Ctrl + P</kbd> چاپ کنید</p>
            <p style="margin-top: 10px;">سامانه هوشمند پایش و تحلیل گاز | {jalali_date}</p>
        </div>
    </div>
</body>
</html>
"""
    
    return html


def main():
    print("=" * 60)
    print("🎨 تولید گزارش وب زیبا")
    print("=" * 60)
    
    # بارگذاری داده‌ها
    data = load_metrics()
    if not data:
        return
    
    # تولید HTML
    print("\n📝 تولید HTML...")
    html = generate_html(data)
    
    # ذخیره فایل
    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n✅ گزارش ذخیره شد: {OUTPUT_HTML}")
    print("\n📄 نحوه استفاده:")
    print("   1. فایل Data_Quality_Report.html را در مرورگر باز کنید")
    print("   2. روی دکمه '🖨️ ذخیره به صورت PDF' کلیک کنید")
    print("   3. در پنجره چاپ، گزینه 'Save as PDF' را انتخاب کنید")
    print("   4. فایل نهایی یک گزارش حرفه‌ای خواهد بود!")
    
    print("\n✨ ویژگی‌های گزارش:")
    print("   - فونت فارسی وزیرمتن")
    print("   - جداول استایل‌دار با ردیف‌های متناوب")
    print("   - کارت‌های امتیاز با رنگ‌بندی")
    print("   - بهینه‌شده برای چاپ و تبدیل به PDF")


if __name__ == "__main__":
    main()