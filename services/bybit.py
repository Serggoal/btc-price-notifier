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
