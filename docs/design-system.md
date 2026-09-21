# Design System - Gas Intelligence Platform

## ۱. اصول طراحی (Design Principles)

1. **Analytical Clarity** - هر المان باید یک سؤال تجاری را پاسخ دهد
2. **Calm Intelligence** - آرام، دقیق، بدون نویز بصری
3. **Progressive Disclosure** - اطلاعات بیشتر هنگام نیاز
4. **Decision-First** - اولویت با KPI های تصمیم‌ساز
5. **Industrial Trust** - حس اعتماد صنعتی/energy sector

## ۲. سیستم رنگ (Color System)

### Light Mode (حالت روشن)

```css
:root {
  /* Surfaces - سطوح */
  --surface-base: #F8FAFC;
  --surface-elevated: #FFFFFF;
  --surface-sunken: #F1F5F9;
  --surface-hover: #F1F5F9;
  
  /* Primary - Industrial Blue */
  --primary-50: #EFF6FF;
  --primary-100: #DBEAFE;
  --primary-500: #0F4C81;
  --primary-600: #0C3F6B;
  --primary-700: #093154;
  --primary-900: #061E33;
  
  /* Accent - Energy Amber */
  --accent-500: #D97706;
  --accent-600: #B45309;
  
  /* Semantic Colors */
  --success: #059669;
  --success-bg: #ECFDF5;
  --warning: #D97706;
  --warning-bg: #FFFBEB;
  --danger: #DC2626;
  --danger-bg: #FEF2F2;
  --info: #0284C7;
  --info-bg: #F0F9FF;
  
  /* Text */
  --text-primary: #0F172A;
  --text-secondary: #475569;
  --text-muted: #94A3B8;
  --text-inverse: #FFFFFF;
  
  /* Borders */
  --border-subtle: #E2E8F0;
  --border-default: #CBD5E1;
  --border-strong: #94A3B8;
}
```

### Dark Mode (حالت تاریک)

```css
[data-theme="dark"] {
  --surface-base: #0B1120;
  --surface-elevated: #111827;
  --surface-sunken: #020617;
  --surface-hover: #1F2937;
  
  --primary-500: #3B82F6;
  --accent-500: #F59E0B;
  
  --text-primary: #F1F5F9;
  --text-secondary: #CBD5E1;
  --text-muted: #64748B;
  
  --border-subtle: #1F2937;
  --border-default: #334155;
}
```

## ۳. تایپوگرافی (Typography Scale)

فونت اصلی: **Vazirmatn** (فارسی)

| Token | اندازه | وزن | کاربرد |
|:---|:---:|:---:|:---|
| `display` | 32px | 700 | عناوین اصلی صفحه |
| `h1` | 24px | 700 | عنوان بخش‌ها |
| `h2` | 20px | 600 | عنوان زیربخش |
| `h3` | 16px | 600 | عنوان کارت‌ها |
| `body` | 14px | 400 | متن پیش‌فرض |
| `body-small` | 12px | 400 | توضیحات |
| `caption` | 11px | 500 | برچسب‌ها |
| `kpi-lg` | 36px | 700 | KPI اصلی |
| `kpi-md` | 28px | 700 | KPI ثانویه |
| `kpi-sm` | 18px | 600 | KPI سوم |
| `mono` | 13px | 500 | اعداد tabular |

**قانون مهم:** همه اعداد تحلیلی باید از `font-variant-numeric: tabular-nums` استفاده کنند تا ارقام در یک خط تراز شوند.

## ۴. فاصله‌گذاری (Spacing Scale)

مبنای ۴ پیکسل:

```css
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 20px;
--space-6: 24px;
--space-8: 32px;
--space-10: 40px;
--space-12: 48px;
```

## ۵. ارتفاع (Elevation)

| سطح | کاربرد | Shadow |
|:---:|:---|:---|
| 0 | Sunken (داخلی) | inset shadow |
| 1 | کارت‌های معمولی | 0 1px 2px |
| 2 | کارت‌های برجسته | 0 2px 4px |
| 3 | Modals/Popovers | 0 8px 16px |

## ۶. نقاط شکست (Breakpoints)

| نام | حداقل عرض | هدف |
|:---|:---:|:---|
| `mobile` | 320px | موبایل |
| `tablet` | 768px | تبلت پرتره |
| `desktop` | 1200px | لپ‌تاپ |
| `large` | 1440px | دسکتاپ |

## ۷. قوانین آیکون‌ها

- استفاده از **Lucide Icons** (کتابخانه SVG)
- اندازه پیش‌فرض: 18px × 18px
- اندازه کوچک: 14px × 14px
- اندازه بزرگ: 24px × 24px
- **emoji فقط در موارد خاص** (مثل لوگوی 🔥)
- emoji نباید به عنوان آیکون navigation استفاده شود

## ۸. انیمیشن و حرکت (Motion)

```css
--transition-fast: 120ms ease-out;
--transition-normal: 200ms ease-out;
--transition-slow: 300ms ease-out;
```

**قانون:** اگر کاربر `prefers-reduced-motion: reduce` را فعال کرده باشد، همه انیمیشن‌ها غیرفعال شوند.

## ۹. قوانین کلی

1. هیچ رنگ، فونت، یا فاصله ad-hoc نباید استفاده شود
2. همه چیز از طریق CSS variables قابل تنظیم باشد
3. Dark mode باید به صورت یک سیستم جداگانه طراحی شود (نه معکوس کردن رنگ‌ها)
4. Contrast در هر دو حالت باید WCAG AA را رعایت کند