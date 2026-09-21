# Frontend Architecture

## نمای کلی (Overview)

Single-page application با vanilla JavaScript و ساختار ماژولار.
بدون فریم‌ورک اضافه. تمرکز بر سادگی، سرعت، و قابلیت نگهداری.

**چرا فریم‌ورک نه؟**
- پروژه فعلی HTML/JS ساده است
- اضافه کردن فریم‌ورک جدید پیچیدگی غیرضروری می‌آورد
- با ساختار ماژولار، قابلیت توسعه حفظ می‌شود

## ساختار پوشه‌ها

```
frontend/
├── index.html              # App Shell + Entry Point
├── styles/
│   ├── tokens.css          # Design tokens (رنگ‌ها، فونت‌ها)
│   ├── base.css            # Reset + استایل‌های پایه
│   ├── components.css      # استایل کامپوننت‌ها
│   └── pages.css           # استایل‌های مخصوص صفحات
├── js/
│   ├── app.js              # Bootstrap + Router
│   ├── core/
│   │   ├── api.js          # API client مرکزی
│   │   ├── state.js        # Global state
│   │   └── router.js       # Hash-based router
│   ├── components/
│   │   ├── sidebar.js
│   │   ├── header.js
│   │   ├── kpi-card.js
│   │   ├── chart-wrapper.js
│   │   └── data-table.js
│   ├── modules/
│   │   ├── overview.js
│   │   ├── consumption.js
│   │   ├── forecast.js
│   │   ├── temperature.js
│   │   ├── scenarios.js
│   │   ├── anomalies.js
│   │   ├── ai-assistant.js
│   │   └── data-quality.js
│   └── utils/
│       ├── format.js       # فرمت اعداد و تاریخ
│       └── fa.js           # ابزارهای فارسی‌سازی
└── assets/
    └── icons/              # آیکون‌های Lucide
```

## استراتژی مسیریابی (Routing)

Hash-based برای سادگی و عدم نیاز به پیکربندی سرور:

```
#/                     → نمای کلی (Overview)
#/consumption          → تحلیل مصرف
#/production           → تولید و پالایش
#/balance              → تراز عملیاتی
#/forecast             → مرکز پیش‌بینی
#/temperature          → تحلیل دما
#/scenarios            → تحلیل سناریو
#/anomalies            → ناهنجاری‌ها
#/stations             → ایستگاه‌ها
#/models               → مانیتورینگ مدل
#/ai                   → دستیار هوشمند (workspace کامل)
#/reports              → گزارش‌ها
#/quality              → کیفیت داده
#/settings             → تنظیمات
```

## مدیریت حالت (State Management)

Simple pub/sub pattern بدون کتابخانه:

```javascript
const state = {
  theme: 'light',
  sidebarCollapsed: false,
  filters: {
    dateRange: '30d',
    province: null,
    consumptionType: null
  },
  data: {
    summary: null,
    trend: null,
    forecast: null,
    anomalies: null
  }
};
```

## یکپارچگی با API

- همه درخواست‌ها از طریق `core/api.js` انجام شود
- یک خطایابی سراسری برای مدیریت خطاها
- جلوگیری از درخواست‌های تکراری با AbortController
- کش در حافظه با عمر ۳۰ ثانیه

**قانون مهم:** آدرس بک‌اند از طریق متغیر کانفیگ باشد، نه هاردکد:

```javascript
const API_URL = window.APP_CONFIG?.API_URL || 'http://127.0.0.1:8000';
```

## قوانین کارایی (Performance)

1. **Lazy load ماژول‌ها**: فقط ماژول فعال لود شود
2. **چرخه حیات چارت‌ها**: در تغییر مسیر، destroy شوند
3. **Debounce**: برای تغییر فیلترها (۳۰۰ میلی‌ثانیه)
4. **Skeleton اول**: قبل از لود داده، اسکلت نشان داده شود
5. **یک درخواست یک نقطه**: از درخواست‌های تکراری پرهیز شود

## چک‌لیست دسترسی‌پذیری (Accessibility)

- [ ] همه عناصر تعاملی با کیبورد قابل پیمایش
- [ ] Focus قابل مشاهده
- [ ] آیکون‌ها دارای `aria-label`
- [ ] HTML معنایی (nav, main, section)
- [ ] رنگ تنها نشانه نباشد
- [ ] رعایت `prefers-reduced-motion`
- [ ] لینک "پرش به محتوای اصلی"
- [ ] ARIA live regions برای محتوای پویا

## استراتژی تست

- تست دستی در ۴ سایز: موبایل، تبلت، لپ‌تاپ، دسکتاپ
- بررسی کنتراست رنگ با ابزارهای توسعه مرورگر
- تست کیبورد بدون موس