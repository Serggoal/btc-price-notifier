import httpx
import logging
from config import BYBIT_API_URL

ETH_API_URL = 'https://api.bybit.com/v5/market/tickers?category=spot&symbol=ETHUSDT'

async def get_eth_price() -> float:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(ETH_API_URL)
            resp.raise_for_status()
            data = resp.json()
            price = float(data['result']['list'][0]['lastPrice'])
            return price
    except Exception as e:
        logging.error(f'Bybit ETH API error: {e}')
        raise RuntimeError('Ошибка получения цены ETH с Bybit')
