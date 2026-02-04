"""Constants to replace magic numbers throughout the codebase"""

# Time intervals (in seconds)
POLL_INTERVAL = 0.5  # Interval for polling SSH output
UPDATE_INTERVAL = 1.0  # Interval for updating message display
COMMAND_WAIT_TIME = 0.5  # Wait time after sending command to screen
SCREEN_INIT_WAIT = 0.5  # Wait time for screen session initialization
SCREEN_KILL_WAIT = 1.0  # Wait time after killing screen session
HEALTH_CHECK_TIMEOUT = 2  # Timeout for health check commands
CANCEL_CHECK_INTERVAL = 0.1  # Interval for checking cancellation during connection retries

# SSH Command timeouts (in seconds)
SSH_COMMAND_TIMEOUT = 3  # Default timeout for SSH commands
SSH_SCREEN_CHECK_TIMEOUT = 3  # Timeout for screen session checks
SSH_LOG_READ_TIMEOUT = 2  # Timeout for reading log files
SSH_CONNECTION_TIMEOUT = 15  # Timeout for SSH connection

# Polling constants
MAX_NO_CHANGE_COUNT = 6  # Max consecutive polls with no change before considering command finished
CONTINUOUS_COMMAND_THRESHOLD = 5  # Seconds since last output to consider command continuous

# Output limits
MAX_OUTPUT_LENGTH = 4000  # Maximum length for Telegram messages
MAX_ERROR_LENGTH = 3500  # Maximum length for error messages
MAX_COMMAND_LOG_LENGTH = 1000  # Maximum length for command in database log
LAST_LINES_COUNT = 4  # Number of last lines to show in real-time output

# Rate limiting
COMMAND_RATE_LIMIT_DIVISOR = 3  # Divisor for command rate limit (general_rate_limit / this)
MIN_COMMAND_RATE_LIMIT = 10  # Minimum command executions per minute

THREAD_POOL_MAX_WORKERS = 15
MAX_CONCURRENT_SSH_CONNECTIONS = 10

# Screen session
SCREEN_SESSION_PREFIX = "sshbot_"  # Prefix for screen session names
SCREEN_SESSION_HASH_LENGTH = 8  # Length of hash in screen session name

# conversation user_data keys
ADD_SERVER_KEYS = ("new_server_name", "new_server_host", "new_server_port", "new_server_username", "new_server_password")
DIRECT_CONNECT_KEYS = ("direct_host", "direct_port", "direct_username", "direct_password")
EDIT_SERVER_KEYS = ("edit_server_id", "edit_field")
PRESET_KEYS = ("new_preset_name", "new_preset_command")

