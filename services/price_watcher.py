import asyncio
import logging
from config import CHECK_INTERVAL

from services.bybit import get_btc_price
from services.bybit_eth import get_eth_price
from services.storage import UserStorage

_watchers = {}
_watchers_eth = {}


def _cancel_task(task):
    try:
        if task and not task.done():
            task.cancel()
    except Exception:
        pass


async def start_price_watcher(user_id: int, target_price: float, bot):
    # cancel previous task if exists
    prev = _watchers.get(user_id)
    if prev:
        _cancel_task(prev.get('task'))

    async def watcher():
        logging.info(f'Start watching for user {user_id} at price {target_price}')
        try:
            # get starting price to determine direction
            try:
                start_price = float(await get_btc_price())
            except Exception:
                start_price = None

            try:
                target = float(target_price)
            except Exception:
                logging.error(f'Invalid target price for user {user_id}: {target_price}')
                return

            if start_price is None:
                direction_up = True
            else:
                if target > start_price:
                    direction_up = True
                elif target < start_price:
                    direction_up = False
                else:
                    # target equals current price -> notify immediately
                    await bot.send_message(user_id, f'🚀 Цена BTC достигла цели: <b>{start_price}</b>!')
                    UserStorage.clear_target(user_id)
                    return

            while True:
                try:
                    price = float(await get_btc_price())
                    logging.info(f'User {user_id}: Current BTC price: {price}, Target: {target_price}, start: {start_price}, dir_up: {direction_up}')
                    if direction_up:
                        if price >= target and (start_price is None or price > start_price):
                            await bot.send_message(user_id, f'🚀 Цена BTC достигла цели: <b>{price}</b>!')
                            UserStorage.clear_target(user_id)
                            break
                    else:
                        if price <= target and (start_price is None or price < start_price):
                            await bot.send_message(user_id, f'📉 Цена BTC опустилась до цели: <b>{price}</b>!')
                            UserStorage.clear_target(user_id)
                            break
                except Exception as e:
                    logging.error(f'Error in watcher for user {user_id}: {e}')
                await asyncio.sleep(CHECK_INTERVAL)
        except asyncio.CancelledError:
            logging.info(f'Watcher for user {user_id} cancelled')
            return

    task = asyncio.create_task(watcher())
    _watchers[user_id] = {'task': task}


async def start_price_watcher_eth(user_id: int, target_price: float, bot):
    prev = _watchers_eth.get(user_id)
    if prev:
        _cancel_task(prev.get('task'))

    async def watcher():
        logging.info(f'Start watching ETH for user {user_id} at price {target_price}')
        try:
            # get starting price to determine direction
            try:
                start_price = float(await get_eth_price())
            except Exception:
                start_price = None

            try:
                target = float(target_price)
            except Exception:
                logging.error(f'Invalid ETH target price for user {user_id}: {target_price}')
                return

            if start_price is None:
                direction_up = True
            else:
                if target > start_price:
                    direction_up = True
                elif target < start_price:
                    direction_up = False
                else:
                    await bot.send_message(user_id, f'🚀 Цена ETH достигла цели: <b>{start_price}</b>!')
                    UserStorage.clear_target(user_id, coin="ETH")
                    return

            while True:
                try:
                    price = float(await get_eth_price())
                    logging.info(f'User {user_id}: Current ETH price: {price}, Target: {target_price}, start: {start_price}, dir_up: {direction_up}')
                    if direction_up:
                        if price >= target and (start_price is None or price > start_price):
                            await bot.send_message(user_id, f'🚀 Цена ETH достигла цели: <b>{price}</b>!')
                            UserStorage.clear_target(user_id, coin="ETH")
                            break
                    else:
                        if price <= target and (start_price is None or price < start_price):
                            await bot.send_message(user_id, f'📉 Цена ETH опустилась до цели: <b>{price}</b>!')
                            UserStorage.clear_target(user_id, coin="ETH")
                            break
                except Exception as e:
                    logging.error(f'Error in ETH watcher for user {user_id}: {e}')
                await asyncio.sleep(CHECK_INTERVAL)
        except asyncio.CancelledError:
            logging.info(f'ETH watcher for user {user_id} cancelled')
            return

    task = asyncio.create_task(watcher())
    _watchers_eth[user_id] = {'task': task}
