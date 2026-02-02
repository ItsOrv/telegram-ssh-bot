# بررسی کلی پروژه (Project Review)

**این سند جایگزین:** `CODE_REVIEW_REPORT.md`, `DEEP_REVIEW_REMAINING_ISSUES.md`, `FINAL_REVIEW_SUMMARY.md` (موارد تکراری در اینجا ادغام شده‌اند.)

## خلاصه
پروژه بات تلگرام برای مدیریت و اجرای دستورات SSH است. ساختار کلی مناسب است؛ موارد شناسایی‌شده در بررسی‌های قبلی اعمال شده‌اند.

---

## ۱. مشکلات امنیتی و طراحی

### ۱.۱ IP_WHITELIST استفاده نشده
- **فایل:** `config/settings.py`
- **مشکل:** `IP_WHITELIST` تعریف شده اما در هیچ جای کد چک نمی‌شود؛ درخواست‌ها بر اساس IP محدود نمی‌شوند.
- **پیشنهاد:** یا پیاده‌سازی چک IP در نقطهٔ ورود (مثلاً قبل از handlerها) یا حذف از تنظیمات و مستند کردن به‌عنوان «آینده».

### ۱.۲ رمز عبور در Direct Connect
- **فایل:** `handlers/server_handlers.py` (Direct Connect)
- **مشکل:** رمز مستقیم با `encrypt_password` ذخیره می‌شود اما در `temp_server_data` فقط برای یک اتصال استفاده می‌شود و بعد از اتصال در حافظه می‌ماند.
- **وضعیت:** قابل قبول برای سناریوی اتصال موقت؛ در صورت ذخیرهٔ سرور در DB باید رمز رمزنگاری‌شده ذخیره شود (الان برای سرورهای ذخیره‌شده درست است).

### ۱.۳ لاگ دستورات
- **فایل:** `utils/logger.py`
- **وضعیت:** دستور قبل از لاگ سانیتایز می‌شود (الگوی password/token حذف می‌شود). مناسب است.

---

## ۲. دیتابیس و مدل‌ها

### ۲.۱ استفاده از `datetime.utcnow` (منسوخ در Python 3.12)
- **فایل‌ها:** `database/models.py`, `utils/logger.py`
- **مشکل:** `datetime.utcnow` در Python 3.12 منسوخ شده؛ بهتر است از `datetime.now(timezone.utc)` استفاده شود.
- **اقدام:** در همین بررسی اصلاح شده است.

### ۲.۲ مدل BlockedCommand بدون استفاده
- **فایل:** `database/models.py`
- **وضعیت:** مدل نگه داشته شده؛ docstring اضافه شده که برای استفادهٔ آینده (الگوی مسدود از DB) رزرو شده و validator فعلاً از `DANGEROUS_COMMANDS` استفاده می‌کند.

### ۲.۳ ایندکس اضافه روی کلید اصلی
- **فایل:** `database/models.py` – `Server.__table_args__`
- **مشکل:** `Index('idx_servers_id', 'id')` روی ستون primary key است؛ در اکثر موتورها PK خودش ایندکس دارد.
- **پیشنهاد:** حذف این ایندکس برای تمیزتر شدن اسکیم.

### ۲.۴ متد get_session_direct بدون استفاده
- **فایل:** `database/connection.py`
- **وضعیت:** حذف شده؛ استفاده‌ای نداشت و احتمال نشتی session وجود داشت.

---

## ۳. امنیت و رمزنگاری

### ۳.۱ cryptography backend
- **فایل:** `security/encryption.py`
- **وضعیت:** اصلاح شده؛ `default_backend()` حذف شده و از `hashes.Hash(hashes.SHA256())` بدون backend استفاده می‌شود.

### ۳.۲ اعتبارسنجی دستور و ورودی
- **فایل:** `security/validator.py`
- **وضعیت:** لیست دستورات خطرناک، محدودیت طول، حذف کاراکترهای کنترلی و اعتبار host/port در نظر گرفته شده؛ مناسب است.

---

## ۴. عملکرد و منابع

### ۴.۱ کش public_mode
- **وضعیت:** قبلاً اضافه شده؛ تعداد کوئری‌های تکراری کم شده است.

### ۴.۲ یک thread pool و THREAD_POOL_MAX_WORKERS
- **وضعیت:** قبلاً اصلاح شده؛ با توجه به ۱ هستهٔ CPU پیشنهاد `THREAD_POOL_MAX_WORKERS=5` در `.env` داده شده.

### ۴.۳ لاگ به DB در پس‌زمینه
- **فایل:** `utils/logger.py` – `log_command_execution`
- **مشکل:** با `threading.Thread(..., daemon=True)` یک thread جدید برای هر لاگ ساخته می‌شود؛ در بار زیاد می‌تواند تعداد threadها زیاد شود.
- **پیشنهاد:** استفاده از همان thread pool اصلی (مثلاً `asyncio.to_thread` یا `run_in_executor`) تا تعداد workerها محدود بماند.

---

## ۵. کیفیت کد و نگهداری

### ۵.۱ فایل نمونهٔ .env
- **مشکل:** در README گفته شده «کپی .env.example» اما در مخزن فقط `.env` وجود دارد (و معمولاً در gitignore است).
- **اقدام:** اضافه کردن `.env.example` با متغیرهای لازم و بدون مقدار حساس.

### ۵.۲ یکپارچگی زبان پیام‌ها
- **مشکل:** بعضی پیام‌ها انگلیسی و بعضی فارسی هستند (مثلاً در `get_users_info.py` و برخی handlerها).
- **پیشنهاد:** تعیین یک زبان پیش‌فرض برای کاربر نهایی و متمرکز کردن متن‌ها در `utils/messages.py` یا فایل ترجمه.

### ۵.۳ Importهای استفاده‌نشده
- **وضعیت:** import تکراری `safe_reply_or_edit` از داخل `execute_command_menu` به بالای `command_handlers.py` منتقل شده؛ `server_handlers` از `asyncio` استفاده می‌کند و نگه داشته شده.

### ۵.۴ فایل‌های قدیمی بررسی
- **وضعیت:** این سند (PROJECT_REVIEW.md) به‌عنوان سند اصلی بررسی در نظر گرفته شده؛ فایل‌های قدیمی برای مرجع نگه داشته شده‌اند.

---

## ۶. تست و استقرار

### ۶.۱ تست خودکار
- **وضعیت:** تست واحد یا یکپارچگی در مخزن دیده نشد.
- **پیشنهاد:** اضافه کردن حداقل چند تست برای validator، encryption و DB helpers.

### ۶.۲ اسکریپت‌های start/stop
- **فایل‌ها:** `start_bot.sh`, `stop_bot.sh`, `start.sh`
- **پیشنهاد:** اطمینان از مسیر صحیح `python`/`venv` و اینکه `stop` به درستی PID را پیدا و متوقف می‌کند.

---

## ۷. خلاصهٔ اولویت‌ها

| اولویت | مورد | اقدام پیشنهادی |
|--------|------|-----------------|
| بالا | `datetime.utcnow` | جایگزینی با `datetime.now(timezone.utc)` (انجام شد) |
| بالا | نبود `.env.example` | اضافه کردن فایل نمونه (انجام شد) |
| متوسط | ایندکس اضافه `idx_servers_id` | حذف ایندکس (انجام شد) |
| متوسط | لاگ با thread جدید در logger | استفاده از thread pool مشترک (انجام شد) |
| متوسط | مدل BlockedCommand | docstring برای آینده (انجام شد) |
| پایین | IP_WHITELIST | پیاده‌سازی یا حذف از تنظیمات |
| پایین | get_session_direct | حذف شده |
| پایین | یکسان‌سازی زبان پیام‌ها | تمرکز در messages و ترجمه (فعلاً باز) |

---

## تغییرات اعمال‌شده در به‌روزرسانی اخیر

- حذف `get_session_direct` از `database/connection.py`
- لاگ به DB: استفاده از `run_in_executor` در صورت وجود event loop، در غیر این صورت daemon thread
- حذف `default_backend` از `security/encryption.py`
- توضیح برای `IP_WHITELIST` و docstring برای مدل `BlockedCommand`
- پاکسازی کلیدهای مکالمه: به‌جای `context.user_data.clear()` استفاده از توابع `clear_*_keys` و `clear_all_conversation_keys` در `utils/connection_helpers.py` با ثابت‌های کلید در `utils/constants.py`
- استفاده از `safe_edit_message` در `presets_menu` و یکپارچه‌سازی با `safe_reply_or_edit` در `cancel_preset` و انتقال import `safe_reply_or_edit` به بالای `command_handlers.py`

---

این سند بر اساس وضعیت فعلی کد نوشته شده و با هر تغییر بزرگ بهتر است دوباره به‌روز شود.
