import asyncio
import logging
from config import CHECK_INTERVAL

from services.bybit import get_btc_price
from services.bybit_eth import get_eth_price
from services.storage import UserStorage

_watchers = {}
_watchers_eth = {}

async def start_price_watcher(user_id: int, target_price: float, bot):
    if user_id in _watchers:
        _watchers[user_id]['active'] = False
    _watchers[user_id] = {'active': True}
    async def watcher():
        logging.info(f'Start watching for user {user_id} at price {target_price}')
        while _watchers[user_id]['active']:
            try:
                price = await get_btc_price()
                logging.info(f'User {user_id}: Current BTC price: {price}, Target: {target_price}')
                if price >= target_price:
                    await bot.send_message(user_id, f'🚀 Цена BTC достигла цели: <b>{price}</b>!')
                    _watchers[user_id]['active'] = False
                    UserStorage.clear_target(user_id)
                    break
            except Exception as e:
                logging.error(f'Error in watcher for user {user_id}: {e}')
            await asyncio.sleep(CHECK_INTERVAL)
    asyncio.create_task(watcher())

async def start_price_watcher_eth(user_id: int, target_price: float, bot):
    if user_id in _watchers_eth:
        _watchers_eth[user_id]['active'] = False
    _watchers_eth[user_id] = {'active': True}
    async def watcher():
        logging.info(f'Start watching ETH for user {user_id} at price {target_price}')
        while _watchers_eth[user_id]['active']:
            try:
                price = await get_eth_price()
                logging.info(f'User {user_id}: Current ETH price: {price}, Target: {target_price}')
                if price >= target_price:
                    await bot.send_message(user_id, f'🚀 Цена ETH достигла цели: <b>{price}</b>!')
                    _watchers_eth[user_id]['active'] = False
                    UserStorage.clear_target(user_id, coin="ETH")
                    break
            except Exception as e:
                logging.error(f'Error in ETH watcher for user {user_id}: {e}')
            await asyncio.sleep(CHECK_INTERVAL)
    asyncio.create_task(watcher())
