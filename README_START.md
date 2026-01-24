# راهنمای اجرای ربات

## اجرای ربات

### روش 1: استفاده از اسکریپت start.sh
```bash
./start.sh
```

### روش 2: اجرای دستی
```bash
source venv/bin/activate
python3 bot.py
```

## نکات مهم

1. **Virtual Environment**: همیشه باید virtual environment را فعال کنید قبل از اجرای ربات
2. **فایل .env**: مطمئن شوید که فایل `.env` با تنظیمات صحیح وجود دارد
3. **JobQueue (اختیاری)**: برای periodic cleanup، می‌توانید نصب کنید:
   ```bash
   source venv/bin/activate
   pip install "python-telegram-bot[job-queue]"
   ```

## مشکلات رایج

### ModuleNotFoundError: No module named 'telegram'
**راه حل**: Virtual environment را فعال کنید:
```bash
source venv/bin/activate
```

### JobQueue not available
**راه حل**: این یک warning است و ربات بدون آن هم کار می‌کند. برای فعال کردن:
```bash
source venv/bin/activate
pip install "python-telegram-bot[job-queue]"
```

