import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
BYBIT_API_URL = os.getenv('BYBIT_API_URL', 'https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 60))
BYBIT_BASE_URL = os.getenv('BYBIT_BASE_URL', 'https://api.bybit.com')
BYBIT_API_KEY = os.getenv('BYBIT_API_KEY')
BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET')
# Telegram user id allowed to use trading commands
OWNER_TELEGRAM_ID = int(os.getenv('OWNER_TELEGRAM_ID')) if os.getenv('OWNER_TELEGRAM_ID') else None
