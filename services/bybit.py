import httpx
import logging
from config import BYBIT_API_URL

async def get_btc_price() -> float:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(BYBIT_API_URL)
            resp.raise_for_status()
            data = resp.json()
            price = float(data['result']['list'][0]['lastPrice'])
            return price
    except Exception as e:
        logging.error(f'Bybit API error: {e}')
        raise RuntimeError('Ошибка получения цены BTC с Bybit')


async def get_30m_candles(symbol: str = 'BTCUSDT', limit: int = 3):
    """Fetch recent 30-minute klines for a given symbol from Bybit.

    Returns the parsed list of klines (most recent first). Each kline is
    returned as a dict with keys: open_time, open, high, low, close, volume.
    """
    url = f'https://api.bybit.com/v5/market/kline?category=spot&symbol={symbol}&interval=30&limit={limit}'
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            # Expected structure: data['result']['list'] -> list of lists
            klines = []
            items = data.get('result', {}).get('list', [])
            for item in items:
                # item may be list like [open_time, open, high, low, close, volume]
                if isinstance(item, (list, tuple)) and len(item) >= 6:
                    open_time = item[0]
                    open_p = item[1]
                    high_p = item[2]
                    low_p = item[3]
                    close_p = item[4]
                    volume = item[5]
                elif isinstance(item, dict):
                    open_time = item.get('open_time') or item.get('start_at')
                    open_p = item.get('open')
                    high_p = item.get('high')
                    low_p = item.get('low')
                    close_p = item.get('close')
                    volume = item.get('volume')
                else:
                    continue
                klines.append({
                    'open_time': open_time,
                    'open': open_p,
                    'high': high_p,
                    'low': low_p,
                    'close': close_p,
                    'volume': volume,
                })
            return klines
    except Exception as e:
        logging.error(f'Bybit Kline API error: {e}')
        raise RuntimeError('Ошибка получения свечей с Bybit')


async def get_15m_candles(symbol: str = 'ETHUSDT', limit: int = 5):
    """Fetch recent 15-minute klines for a given symbol from Bybit.

    Returns the parsed list of klines (most recent first). Each kline is
    returned as a dict with keys: open_time, open, high, low, close, volume.
    """
    url = f'https://api.bybit.com/v5/market/kline?category=spot&symbol={symbol}&interval=15&limit={limit}'
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            klines = []
            items = data.get('result', {}).get('list', [])
            for item in items:
                if isinstance(item, (list, tuple)) and len(item) >= 6:
                    open_time = item[0]
                    open_p = item[1]
                    high_p = item[2]
                    low_p = item[3]
                    close_p = item[4]
                    volume = item[5]
                elif isinstance(item, dict):
                    open_time = item.get('open_time') or item.get('start_at')
                    open_p = item.get('open')
                    high_p = item.get('high')
                    low_p = item.get('low')
                    close_p = item.get('close')
                    volume = item.get('volume')
                else:
                    continue
                klines.append({
                    'open_time': open_time,
                    'open': open_p,
                    'high': high_p,
                    'low': low_p,
                    'close': close_p,
                    'volume': volume,
                })
            return klines
    except Exception as e:
        logging.error(f'Bybit 15m Kline API error: {e}')
        raise RuntimeError('Ошибка получения 15m свечей с Bybit')


async def get_futures_15m_candles(symbol: str = 'ETHUSDT', limit: int = 5):
    url = f'https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval=15&limit={limit}'
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            klines = []
            items = data.get('result', {}).get('list', [])
            for item in items:
                if isinstance(item, (list, tuple)) and len(item) >= 6:
                    open_time = item[0]
                    open_p = item[1]
                    high_p = item[2]
                    low_p = item[3]
                    close_p = item[4]
                    volume = item[5]
                elif isinstance(item, dict):
                    open_time = item.get('open_time') or item.get('start_at')
                    open_p = item.get('open')
                    high_p = item.get('high')
                    low_p = item.get('low')
                    close_p = item.get('close')
                    volume = item.get('volume')
                else:
                    continue
                klines.append({
                    'open_time': open_time,
                    'open': open_p,
                    'high': high_p,
                    'low': low_p,
                    'close': close_p,
                    'volume': volume,
                })
            return klines
    except Exception as e:
        logging.error(f'Bybit futures 15m Kline API error: {e}')
        raise RuntimeError('Ошибка получения фьючерсных 15m свечей с Bybit')


async def get_futures_price(symbol: str = 'ETHUSDT') -> float:
    url = f'https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}'
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            price = float(data['result']['list'][0]['lastPrice'])
            return price
    except Exception as e:
        logging.error(f'Bybit futures price API error: {e}')
        raise RuntimeError('Ошибка получения цены фьючерса с Bybit')
