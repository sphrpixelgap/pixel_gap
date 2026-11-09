# 🤖 Telegram Auto Forward Bot | ربات فوروارد خودکار تلگرام

یک ربات تلگرامی سبک، سریع و بهینه‌شده برای **فوروارد خودکار تمام پیام‌ها از چندین کانال و گروه به یک گروه مقصد** با امکان استقرار ۲۴ ساعته روی سرور **Railway**.

A lightweight, production-ready Telegram bot that automatically forwards every new message from multiple source channels/groups to a designated target group. Built for 24/7 deployment on Railway.

---

## 📋 ویژگی‌ها | Features

- ⚡️ فوروارد آنی متن، عکس، ویدیو، وویس، فایل، استیکر و سایر پیام‌ها
- 📢 پشتیبانی همزمان از چندین کانال و گروه مبدأ (نامحدود)
- 🔒 تفکیک هوشمند پیام‌های واقعی از پیام‌های سیستمی (حذف اعلان‌های عضویت، تغییر عکس گروه و ...)
- 🛡️ محافظت در برابر حلقه تکرار پیام‌ها (Loop Guard)
- 🔁 مدیریت خودکار خطاهای شبکه و محدودیت نرخ تلگرام (Retry-After)
- 🆔 راهنما و دستور `/id` برای دریافت آسان آیدی عددی کانال‌ها و گروه‌ها
- 🔎 تشخیص خودکار آیدی کانال فقط با فوروارد یک پیام به ربات
- 🚀 آماده استقرار روی Railway با داکر یا Nixpacks

---

## ⚡️ شروع سریع (Quick Start)

### ۱. پیش‌نیازها
- یک توکن ربات از [BotFather@](https://t.me/BotFather) در تلگرام
- آیدی عددی کانال‌های مبدأ و گروه مقصد
- حساب رایگان در [Railway](https://railway.com) (یا GitHub)

### ۲. تنظیم متغیرهای محیطی

فایل `.env.example` را کپی کرده و به نام `.env` ذخیره کنید:

```ini
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456789
SOURCE_CHAT_IDS=-1001234567890, -1009876543210
TARGET_CHAT_ID=-1009999999999
FORWARD_SILENT=false
LOG_LEVEL=INFO
```

### ۳. اجرای محلی

```bash
git clone <repo-url>
cd telegram-forward-bot

python3 -m venv .venv
source .venv/bin/activate    # در ویندوز: .venv\Scripts\activate
pip install -r requirements.txt

python main.py
```

### ۴. استقرار روی Railway (۳ کلیک)

1. کد را در یک مخزن **GitHub** عمومی یا خصوصی پوش کنید.
2. وارد [Railway](https://railway.com) شوید و روی **New Project → Deploy from GitHub repo** کلیک کنید.
3. مخزن خود را انتخاب کنید.
4. در تب **Variables** مقادیر `BOT_TOKEN`, `SOURCE_CHAT_IDS`, `TARGET_CHAT_ID` را وارد کنید.
5. استقرار به طور خودکار شروع می‌شود و ربات ۲۴ ساعته فعال خواهد بود!

> 📖 **راهنمای فارسی کامل و گام‌به‌گام تصویری:** فایل [GUIDE_FA.md](GUIDE_FA.md) را مطالعه کنید.

---

## ⚙️ متغیرهای محیطی | Environment Variables

| نام متغیر | اجباری | توضیح |
|-----------|---------|-------|
| `BOT_TOKEN` | ✅ | توکن ربات تلگرام از BotFather@ |
| `SOURCE_CHAT_IDS` | ✅ | لیست آیدی کانال‌ها/گروه‌های مبدأ با ویرگول (عددی یا نام کاربری) |
| `TARGET_CHAT_ID` | ✅ | آیدی عددی یا نام کاربری گروه مقصد |
| `FORWARD_SILENT` | ❌ | ارسال بدون صدا (`false` پیش‌فرض) |
| `LOG_LEVEL` | ❌ | سطح لاگ (`INFO`, `DEBUG`, `WARNING`) |

---

## 🧪 تست‌ها | Tests

```bash
python3 -m unittest -v tests/test_bot.py
```

تمام ۲۲ تست واحد شامل تست‌های منطق فوروارد، مدیریت خطا، پارس مقادیر محیطی و کامندها به صورت خودکار اجرا می‌شوند.

---

## 📦 ساختار پروژه

```
telegram-forward-bot/
├── main.py              # منطق اصلی ربات و هندلرهای فوروارد
├── config.py            # بارگذاری و اعتبارسنجی تنظیمات
├── requirements.txt     # کتابخانه‌های پایتون
├── Dockerfile           # فایل ساخت کانتینر برای Railway
├── Procfile             # نوع پروسه worker برای Railway
├── railway.json         # پیکربندی استقرار Railway
├── .env.example         # الگوی متغیرهای محیطی
├── tests/test_bot.py    # ۲۲ تست واحد
└── GUIDE_FA.md          # راهنمای کامل گام‌به‌گام به زبان فارسی
```

---

## ⚠️ نکات مهم

1. **ادمین بودن ربات الزامی است:** ربات باید در تمام کانال‌ها و گروه‌های مبدأ و گروه مقصد ادمین باشد تا بتواند پیام‌ها را بخواند و ارسال کند.
2. **غیرفعال کردن Group Privacy:** در BotFather به مسیر `/mybots → نام ربات → Bot Settings → Group Privacy` بروید و آن را **Turn off** کنید (اگر ربات در گروه ادمین کامل باشد این کار اختیاری است اما توصیه می‌شود).
3. **کانال‌های محافظت‌شده:** کانال‌هایی که گزینه «Restrict saving content» در آن‌ها فعال است، طبق قوانین تلگرام پیام‌هایشان قابل فوروارد نیست؛ ربات این پیام‌ها را شناسایی کرده و بدون کرش از آن‌ها رد می‌شود.
