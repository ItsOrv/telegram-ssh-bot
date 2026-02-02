# گزارش بررسی عمیق - مشکلات باقی‌مانده

> **سند به‌روز:** برای وضعیت فعلی پروژه به `PROJECT_REVIEW.md` مراجعه کنید.

## 🔍 مشکلات شناسایی شده در بررسی عمیق

### 1. فایل Duplicate باقی‌مانده
**موقعیت:** `database/async_db.py`
- این فایل duplicate است و باید حذف شود
- `utils/db_helpers.py` همان functionality را دارد

### 2. تابع استفاده نشده
**موقعیت:** `ssh/executor.py:101` - `execute_interactive`
- این تابع تعریف شده اما هیچ جا استفاده نمی‌شود
- باید حذف شود یا استفاده شود

### 3. Model استفاده نشده
**موقعیت:** `database/models.py:78` - `BlockedCommand`
- Model تعریف شده اما هیچ query یا استفاده‌ای ندارد
- باید حذف شود یا استفاده شود

### 4. Import های استفاده نشده
**موقعیت:** 
- `handlers/server_handlers.py:2` - `InlineKeyboardButton, InlineKeyboardMarkup` (استفاده مستقیم در خط 870+)
- `handlers/server_handlers.py:25` - `get_success_message` (استفاده نمی‌شود)
- `handlers/preset_handlers.py:15` - `get_success_message` (استفاده نمی‌شود)
- `handlers/admin_handlers.py:8` - `get_success_message` (استفاده نمی‌شود)
- `handlers/server_handlers.py:4` - `Dict` (استفاده نمی‌شود)
- `handlers/server_handlers.py:5` - `asyncio` (استفاده نمی‌شود - همه جا از run_db_operation استفاده می‌شود)

### 5. استفاده مستقیم از exec_command بدون helper
**موقعیت:** `ssh/executor.py:48-51`
- در fallback case هنوز از exec_command مستقیم استفاده می‌شود
- باید از `execute_ssh_command_safe` استفاده شود

### 6. استفاده مستقیم از edit_message_text/reply_text
**موقعیت:** 
- `handlers/command_handlers.py:64, 70` - `execute_command_menu`
- `handlers/server_handlers.py:48` - `servers_menu`
- `bot.py:275-324` - `callback_query_handler` (بخش‌هایی)
- باید از `safe_edit_message` یا `safe_reply_or_edit` استفاده شود

### 7. Magic numbers باقی‌مانده
**موقعیت:**
- `ssh/executor.py:130` - `time.sleep(0.1)` باید از constant استفاده کند
- `handlers/command_handlers.py:23` - `max_workers=10` باید از constant استفاده کند
- `database/connection.py:28-31` - pool settings باید از constants استفاده کنند

### 8. Exception handling خیلی عمومی
**موقعیت:** 
- بسیاری از `except Exception as e:` که فقط `pass` می‌کنند
- باید specific exceptions catch شوند

### 9. عدم استفاده از constants در برخی جاها
**موقعیت:**
- `ssh/executor.py:274` - `max_no_change` باید از `MAX_NO_CHANGE_COUNT` استفاده کند
- `ssh/manager.py:163` - `SSH_SCREEN_CHECK_TIMEOUT` import نشده

### 10. Code duplication در bot.py
**موقعیت:** `bot.py:325-334` و `349-358`
- کد cancel connection دو بار تکرار شده
- باید به helper function تبدیل شود

### 11. عدم cleanup برای rate limiting
**موقعیت:** `bot.py:93-125`
- `user_requests` و `command_executions` dictionaries هیچ cleanup ندارند
- می‌توانند memory leak ایجاد کنند

### 12. Type hints ناقص
**موقعیت:** 
- `bot.py:231` - `callback_query_handler` type hint ندارد
- `bot.py:127` - `check_access` return type ندارد
- بسیاری از handler functions type hints ندارند

### 13. Import درون function
**موقعیت:**
- `handlers/server_handlers.py:605` - `import threading` درون function
- `handlers/command_handlers.py:86` - `from bot import check_command_rate_limit` درون function
- باید در بالای فایل باشند

### 14. استفاده از get_session_direct
**موقعیت:** `database/connection.py:65-69`
- این method تعریف شده اما استفاده نمی‌شود
- باید حذف شود یا استفاده شود

### 15. Context user_data cleanup ناقص
**موقعیت:** 
- در برخی جاها `context.user_data.clear()` استفاده می‌شود که همه چیز را پاک می‌کند
- باید فقط keys مربوطه پاک شوند

### 16. Error messages انگلیسی
**موقعیت:** 
- برخی error messages انگلیسی هستند در حالی که بقیه فارسی هستند
- باید یکسان شوند

### 17. Logging ناقص
**موقعیت:**
- برخی exception ها log نمی‌شوند
- برخی فقط `logger.debug` استفاده می‌کنند که در production دیده نمی‌شوند

### 18. Race condition potential
**موقعیت:** `handlers/command_handlers.py:143`
- `context.user_data[f"latest_status_msg_{user_id}"]` ممکن است race condition داشته باشد
- باید lock استفاده شود

### 19. Memory leak potential
**موقعیت:** `handlers/command_handlers.py:346`
- `context.user_data[f"command_task_{user_id}"]` ممکن است cleanup نشود
- باید در finally block cleanup شود

### 20. Incomplete error handling
**موقعیت:** `ssh/executor.py:48-51`
- در fallback case streams بسته نمی‌شوند
- باید از helper function استفاده شود

---

## 📊 آمار مشکلات باقی‌مانده

- **فایل‌های duplicate:** 1
- **توابع استفاده نشده:** 2
- **Import های استفاده نشده:** 6+
- **Magic numbers:** 5+
- **Exception handling ناقص:** 10+
- **Type hints ناقص:** 5+
- **Code duplication:** 2
- **Memory leaks potential:** 2
- **Race conditions:** 1

**جمع کل:** 34+ مشکل باقی‌مانده


