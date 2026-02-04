# Telegram SSH Bot

Telegram bot to manage and run commands on SSH servers.

## Features

- **Servers**: Add, edit, delete; IP/hostname and credentials validated; passwords stored encrypted.
- **Connection**: One active connection per user; connect from list or direct; idle timeout.
- **Commands**: Run commands on the connected server; interactive support; dangerous commands blocked; length limits.
- **Presets**: Save and run frequent commands.
- **Access**: Admin-only by default; optional public mode; data per user.

## Installation and Setup

### Prerequisites

- Python 3.9 or higher
- PostgreSQL
- A Telegram bot (from [@BotFather](https://t.me/BotFather))

### Installation Steps

1. **Clone or download the project**

```bash
cd telegram-ssh-bot
```

2. **Create virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Setup PostgreSQL database**

```bash
# Create database
createdb telegram_ssh_bot

# Or using psql
psql -U postgres
CREATE DATABASE telegram_ssh_bot;
```

5. **Configure environment variables**

Copy `.env.example` and rename to `.env`:

```bash
cp .env.example .env
```

Then edit `.env` file:

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

# Optional: thread pool size (default 15; increase on powerful servers)
# THREAD_POOL_MAX_WORKERS=15
```

**Important Notes:**
- `TELEGRAM_TOKEN`: Get bot token from [@BotFather](https://t.me/BotFather)
- `ADMIN_IDS`: Numeric admin IDs separated by comma (get from [@userinfobot](https://t.me/userinfobot))
- `MASTER_ENCRYPTION_KEY`: A random string at least 32 characters for encryption
- `DATABASE_URL`: PostgreSQL connection address

6. **Run the bot**

```bash
python bot.py
```

## Usage

### Getting Started

1. Find the bot in Telegram and send `/start`
2. Select options from the main menu

### Adding Server

1. From main menu, select "🖥️ Server Management"
2. Select "➕ Add Server"
3. Enter server information in order:
   - Server name
   - IP address or Hostname
   - Port (default: 22)
   - Username
   - Password

### Connecting to Server

1. From "🖥️ Server Management" menu, select "🔌 Connect"
2. Select desired server from list
3. After successful connection, you can execute commands

### Executing Commands

1. From main menu, select "⚡ Execute Command"
2. Enter the command
3. Command output will be displayed

### Preset Commands

1. From main menu, select "📝 Preset Commands"
2. You can add frequently used commands
3. For quick execution, use preset commands list

Tuning (slow bot or low RAM): see `PERFORMANCE.md`. You can set `THREAD_POOL_MAX_WORKERS` in `.env` (default 15).

### Public Mode

To enable bot for all users:

1. Admin should use main menu (or `/admin` command)
2. Select "🌐 Public Mode"
3. Bot will be active for all users

## Security

Passwords are encrypted (AES-256-GCM). Commands are validated and dangerous ones (e.g. `rm -rf /`, `mkfs`, `dd if=`) are blocked. Input is sanitized; rate limit and timeouts apply.

## Project Structure

```
telegram-ssh-bot/
├── bot.py                 # Main entry point
├── config/
│   ├── __init__.py
│   └── settings.py        # Settings management
├── database/
│   ├── __init__.py
│   ├── models.py          # Database models
│   └── connection.py      # Connection management
├── security/
│   ├── __init__.py
│   ├── encryption.py      # Encryption
│   └── validator.py       # Validation
├── ssh/
│   ├── __init__.py
│   ├── manager.py         # SSH management
│   └── executor.py        # Command execution
├── handlers/
│   ├── __init__.py
│   ├── server_handlers.py # Server management
│   ├── command_handlers.py # Command execution
│   ├── preset_handlers.py  # Preset commands
│   └── admin_handlers.py   # Admin management
├── utils/
│   ├── __init__.py
│   ├── keyboards.py       # Keyboards
│   └── messages.py        # Messages
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Advanced Settings

### Change Timeout

In `.env` file:
```env
COMMAND_TIMEOUT=300        # Command execution time (seconds)
CONNECTION_TIMEOUT=1800   # Idle connection time (seconds)
```

### Change Limits

```env
MAX_COMMAND_LENGTH=1000           # Maximum command length
RATE_LIMIT_PER_MINUTE=30         # Requests per minute
```

## Troubleshooting

### Database Connection Error

- Check that PostgreSQL is running
- Verify connection address and credentials in `.env`
- Ensure database is created

### SSH Connection Error

- Verify IP and port are correct
- Check username and password
- Ensure SSH server is accessible

### Bot Not Responding

- Check that bot token is correct
- Check logs
- Ensure bot is running

## License

MIT.
