# ربات تلگرام SSH

ربات تلگرام برای مدیریت و اجرای دستور روی سرورهای SSH.

## ویژگی‌ها

- **سرورها**: افزودن، ویرایش، حذف؛ اعتبارسنجی IP و ورود؛ رمزها رمزنگاری ذخیره می‌شوند.
- **اتصال**: یک اتصال فعال به ازای هر کاربر؛ اتصال از لیست یا مستقیم؛ قطع خودکار بعد از idle.
- **دستورات**: اجرا روی سرور متصل؛ پشتیبانی interactive؛ دستورات خطرناک مسدود؛ محدودیت طول.
- **پیش‌فرض**: ذخیره و اجرای سریع دستورات پرکاربرد.
- **دسترسی**: فقط ادمین به‌صورت پیش‌فرض؛ حالت عمومی اختیاری؛ داده‌ها به‌ازای هر کاربر جدا.

## نصب و راه‌اندازی

### پیش‌نیازها

- Python 3.9 یا بالاتر
- PostgreSQL
- یک ربات تلگرام (از [@BotFather](https://t.me/BotFather))

### مراحل نصب

1. **کلون کردن یا دانلود پروژه**

```bash
cd telegram-ssh-bot
```

2. **ایجاد محیط مجازی**

```bash
python3 -m venv venv
source venv/bin/activate  # در Windows: venv\Scripts\activate
```

3. **نصب وابستگی‌ها**

```bash
pip install -r requirements.txt
```

4. **راه‌اندازی پایگاه داده PostgreSQL**

```bash
# ایجاد پایگاه داده
createdb telegram_ssh_bot

# یا با استفاده از psql
psql -U postgres
CREATE DATABASE telegram_ssh_bot;
```

5. **تنظیم متغیرهای محیطی**

فایل `.env.example` را کپی کرده و به `.env` تغییر نام دهید:

```bash
cp .env.example .env
```

سپس فایل `.env` را ویرایش کنید:

```env
# Telegram Bot Configuration
TELEGRAM_TOKEN=your_bot_token_here

# Admin Configuration (comma-separated user IDs)
ADMIN_IDS=123456789,987654321

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/telegram_ssh_bot

# Security Settings
MASTER_ENCRYPTION_KEY=your_master_key_here_32_chars_minimum

# Bot Settings
COMMAND_TIMEOUT=300
CONNECTION_TIMEOUT=1800
MAX_COMMAND_LENGTH=1000
RATE_LIMIT_PER_MINUTE=30
```

**نکات مهم:**
- `TELEGRAM_TOKEN`: توکن ربات را از [@BotFather](https://t.me/BotFather) دریافت کنید
- `ADMIN_IDS`: شناسه‌های عددی ادمین‌ها را با کاما جدا کنید (می‌توانید از [@userinfobot](https://t.me/userinfobot) دریافت کنید)
- `MASTER_ENCRYPTION_KEY`: یک رشته تصادفی حداقل 32 کاراکتری برای رمزنگاری
- `DATABASE_URL`: آدرس اتصال به پایگاه داده PostgreSQL

6. **راه‌اندازی ربات**

```bash
python bot.py
```

## استفاده

### شروع کار

1. ربات را در تلگرام پیدا کنید و `/start` را ارسال کنید
2. از منوی اصلی، گزینه‌های مختلف را انتخاب کنید

### افزودن سرور

1. از منوی اصلی، "🖥️ مدیریت سرورها" را انتخاب کنید
2. "➕ افزودن سرور" را انتخاب کنید
3. اطلاعات سرور را به ترتیب وارد کنید:
   - نام سرور
   - آدرس IP یا Hostname
   - پورت (پیش‌فرض: 22)
   - نام کاربری
   - رمز عبور

### اتصال به سرور

1. از منوی "🖥️ مدیریت سرورها"، "🔌 اتصال" را انتخاب کنید
2. سرور مورد نظر را از لیست انتخاب کنید
3. پس از اتصال موفق، می‌توانید دستورات را اجرا کنید

### اجرای دستور

1. از منوی اصلی، "⚡ اجرای دستور" را انتخاب کنید
2. دستور مورد نظر را وارد کنید
3. خروجی دستور نمایش داده می‌شود

### دستورات پیش‌فرض

1. از منوی اصلی، "📝 دستورات پیش‌فرض" را انتخاب کنید
2. می‌توانید دستورات پرکاربرد را اضافه کنید
3. برای اجرای سریع، از لیست دستورات پیش‌فرض استفاده کنید

### حالت عمومی

برای فعال کردن ربات برای همه کاربران:

1. ادمین باید از منوی اصلی (یا دستور `/admin`) استفاده کند
2. "🌐 حالت عمومی" را انتخاب کند
3. ربات برای همه کاربران فعال می‌شود

## امنیت

رمزها با AES-256-GCM رمزنگاری می‌شوند. دستورات اعتبارسنجی می‌شوند و موارد خطرناک (مثل `rm -rf /`, `mkfs`, `dd if=`) مسدودند. ورودی سانیتایز می‌شود؛ rate limit و timeout اعمال می‌شود.

## ساختار پروژه

```
telegram-ssh-bot/
├── bot.py                 # نقطه ورود اصلی
├── config/
│   ├── __init__.py
│   └── settings.py        # مدیریت تنظیمات
├── database/
│   ├── __init__.py
│   ├── models.py          # مدل‌های پایگاه داده
│   └── connection.py      # مدیریت اتصال
├── security/
│   ├── __init__.py
│   ├── encryption.py      # رمزنگاری
│   └── validator.py       # اعتبارسنجی
├── ssh/
│   ├── __init__.py
│   ├── manager.py         # مدیریت SSH
│   └── executor.py        # اجرای دستورات
├── handlers/
│   ├── __init__.py
│   ├── server_handlers.py # مدیریت سرورها
│   ├── command_handlers.py # اجرای دستورات
│   ├── preset_handlers.py  # دستورات پیش‌فرض
│   └── admin_handlers.py   # مدیریت ادمین
├── utils/
│   ├── __init__.py
│   ├── keyboards.py       # کیبوردها
│   └── messages.py        # پیام‌ها
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## تنظیمات پیشرفته

### تغییر Timeout

در فایل `.env`:
```env
COMMAND_TIMEOUT=300        # زمان اجرای دستور (ثانیه)
CONNECTION_TIMEOUT=1800   # زمان اتصال idle (ثانیه)
```

### تغییر محدودیت‌ها

```env
MAX_COMMAND_LENGTH=1000           # حداکثر طول دستور
RATE_LIMIT_PER_MINUTE=30         # تعداد درخواست در دقیقه
```

## عیب‌یابی

### خطای اتصال به پایگاه داده

- بررسی کنید که PostgreSQL در حال اجرا است
- آدرس و اطلاعات اتصال در `.env` را بررسی کنید
- اطمینان حاصل کنید که پایگاه داده ایجاد شده است

### خطای اتصال SSH

- بررسی کنید که IP و پورت صحیح هستند
- نام کاربری و رمز عبور را بررسی کنید
- اطمینان حاصل کنید که سرور SSH در دسترس است

### ربات پاسخ نمی‌دهد

- بررسی کنید که توکن ربات صحیح است
- لاگ‌ها را بررسی کنید
- اطمینان حاصل کنید که ربات در حال اجرا است

## مجوز

MIT.

