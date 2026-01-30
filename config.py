import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
BYBIT_API_URL = os.getenv('BYBIT_API_URL', 'https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 60))
