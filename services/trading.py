import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from services.bybit import get_futures_15m_candles, get_futures_price
from services.storage import UserStorage


class TradingManager:
    """Simple in-memory trading simulation manager per user."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._states = {}  # user_id -> state dict

    async def start(self, user_id: int, bot):
        async with self._lock:
            state = self._states.get(user_id, {})
            if state.get('running'):
                await bot.send_message(user_id, 'Торговля уже запущена.')
                return
            state.update({'running': True, 'bot': bot, 'task': None, 'order': None, 'position': None, 'monitor_task': None})
            self._states[user_id] = state
            task = asyncio.create_task(self._run_trading_loop(user_id))
            state['task'] = task
            # persist
            UserStorage.set_trading_state(user_id, state)
        await bot.send_message(user_id, 'Торговля запущена')

    async def stop(self, user_id: int, bot):
        async with self._lock:
            state = self._states.get(user_id)
            if not state or not state.get('running'):
                await bot.send_message(user_id, 'Торговля остановлена')
                return
            task = state.get('task')
            if task:
                task.cancel()
            state['running'] = False
            state['task'] = None
            # persist
            UserStorage.set_trading_state(user_id, state)
        await bot.send_message(user_id, 'Торговля остановлена')

    async def close_position(self, user_id: int, bot):
        async with self._lock:
            state = self._states.get(user_id)
            if not state:
                await bot.send_message(user_id, 'Торговля остановлена')
                return
            pos = state.get('position')
            order = state.get('order')
            if order and not order.get('executed'):
                state['order'] = None
                # persist
                UserStorage.set_trading_state(user_id, state)
                await bot.send_message(user_id, 'Лимитный ордер отменен и не был исполнен')
                return
            if pos:
                state['position'] = None
                UserStorage.set_trading_state(user_id, state)
                await bot.send_message(user_id, f'Позиция закрыта: {pos.get("side")}')
                return
            await bot.send_message(user_id, 'Сделок нет')

    async def status(self, user_id: int, bot):
        state = self._states.get(user_id, {})
        if not state.get('running'):
            await bot.send_message(user_id, 'Торговля остановлена')
            return
        order = state.get('order')
        pos = state.get('position')
        if pos:
            await bot.send_message(user_id, f"Торговля запущена,\n{pos.get('side')} позиция с параметрами:\nТВХ: {pos.get('tvx')}\nStop-loss: {pos.get('sl')}\nTake-profit: {pos.get('tp')}")
            return
        if order:
            await bot.send_message(user_id, f"Торговля запущена,\nВыставлен лимитный ордер на {order.get('side')} позицию с параметрами:\nТВХ: {order.get('tvx')}\nStop-loss: {order.get('sl')}\nTake-profit: {order.get('tp')}")
            return
        await bot.send_message(user_id, 'Торговля запущена, сделок нет')

    async def _run_trading_loop(self, user_id: int):
        """Main loop: wait until next 15m boundary +1s, then every 15m fetch candles and current price and decide."""
        state = self._states.get(user_id)
        bot = state.get('bot')
        try:
            # compute sleep until next 15m boundary +1s
            now = datetime.now(timezone.utc)
            epoch = int(now.timestamp())
            # next multiple of 900 seconds
            next_ts = ((epoch // 900) + 1) * 900 + 1
            to_sleep = next_ts - epoch
            await asyncio.sleep(to_sleep)
            while True:
                # fetch 3 klines and current price
                try:
                    klines = await get_futures_15m_candles(symbol='ETHUSDT', limit=3)
                    price = float(await get_futures_price(symbol='ETHUSDT'))
                except Exception as e:
                    logging.error(f'Trading loop fetch error for {user_id}: {e}')
                    await asyncio.sleep(900)
                    continue

                # klines: most recent first, we need two penultimate closed: earlier=klines[2], later=klines[1]
                if not klines or len(klines) < 3:
                    await asyncio.sleep(900)
                    continue
                earlier = klines[2]
                later = klines[1]

                # parse values
                try:
                    high_1 = float(earlier.get('high'))
                    low_1 = float(earlier.get('low'))
                    high_2 = float(later.get('high'))
                    low_2 = float(later.get('low'))
                except Exception:
                    await asyncio.sleep(900)
                    continue

                # decision
                # LONG
                if high_2 > high_1 and low_2 > low_1:
                    tvx = low_2 + (high_2 - low_2) / 2
                    sl = tvx - (high_2 - low_2)
                    tp = tvx + (high_2 - low_2)
                    await self._handle_order_or_open(user_id, bot, 'LONG', tvx, sl, tp, price)

                # SHORT
                elif high_2 < high_1 and low_2 < low_1:
                    tvx = high_2 - (high_2 - low_2) / 2
                    sl = tvx + (high_2 - low_2)
                    tp = tvx - (high_2 - low_2)
                    await self._handle_order_or_open(user_id, bot, 'SHORT', tvx, sl, tp, price)

                # else do nothing

                await asyncio.sleep(900)
        except asyncio.CancelledError:
            logging.info(f'Trading loop cancelled for {user_id}')
            return

    async def _handle_order_or_open(self, user_id: int, bot, side: str, tvx: float, sl: float, tp: float, current_price: float):
        """Decide limit vs market and set order/position and start monitoring per-minute."""
        async with self._lock:
            state = self._states.get(user_id)
            if not state or not state.get('running'):
                return
            # reset existing order/position only if none exist
            if state.get('position'):
                # already in position, ignore
                return
            if side == 'LONG':
                if tvx < current_price:
                    # place limit order
                    order = {'side': 'LONG', 'tvx': tvx, 'sl': sl, 'tp': tp, 'executed': False}
                    state['order'] = order
                    # persist
                    UserStorage.set_trading_state(user_id, state)
                    await bot.send_message(user_id, f"Выставлен лимитный ордер на ЛОНГ позицию с параметрами:\nТВХ: {tvx}\nStop-loss: {sl}\nTake-profit: {tp}")
                else:
                    # open market long
                    pos = {'side': 'LONG', 'tvx': current_price, 'sl': sl, 'tp': tp}
                    state['position'] = pos
                    UserStorage.set_trading_state(user_id, state)
                    await bot.send_message(user_id, f"Открыта ЛОНГ позиция:\nТВХ: {current_price}\nStop-loss: {sl}\nTake-profit: {tp}")

            else:  # SHORT
                if tvx > current_price:
                    order = {'side': 'SHORT', 'tvx': tvx, 'sl': sl, 'tp': tp, 'executed': False}
                    state['order'] = order
                    UserStorage.set_trading_state(user_id, state)
                    await bot.send_message(user_id, f"Выставлен лимитный ордер на ШОРТ позицию с параметрами:\nТВХ: {tvx}\nStop-loss: {sl}\nTake-profit: {tp}")
                else:
                    pos = {'side': 'SHORT', 'tvx': current_price, 'sl': sl, 'tp': tp}
                    state['position'] = pos
                    UserStorage.set_trading_state(user_id, state)
                    await bot.send_message(user_id, f"Открыта ШОРТ позиция:\nТВХ: {current_price}\nStop-loss: {sl}\nTake-profit: {tp}")

            # start per-minute monitor if not started
            monitor = state.get('monitor_task')
            if not monitor:
                mt = asyncio.create_task(self._monitor_orders(user_id))
                state['monitor_task'] = mt
                UserStorage.set_trading_state(user_id, state)

    async def _monitor_orders(self, user_id: int):
        """Per-minute monitoring for order execution or cancellation.
        - If order exists and executed condition met -> execute and notify
        - If order exists and cancellation condition met (per spec) -> cancel and notify
        """
        try:
            while True:
                await asyncio.sleep(60)
                async with self._lock:
                    state = self._states.get(user_id)
                    if not state or not state.get('running'):
                        return
                    order = state.get('order')
                    pos = state.get('position')
                try:
                    price = float(await get_futures_price(symbol='ETHUSDT'))
                except Exception as e:
                    logging.error(f'Monitor fetch price error for {user_id}: {e}')
                    continue

                async with self._lock:
                    state = self._states.get(user_id)
                    if not state:
                        return
                    order = state.get('order')
                    pos = state.get('position')

                    if order and not order.get('executed'):
                        side = order['side']
                        tvx = float(order['tvx'])
                        tp = float(order['tp'])
                        if side == 'LONG':
                            # check execution: market price falls to tvx or below
                            if price <= tvx:
                                # execute
                                state['position'] = {'side': 'LONG', 'tvx': tvx, 'sl': order['sl'], 'tp': order['tp']}
                                order['executed'] = True
                                state['order'] = None
                                # persist
                                UserStorage.set_trading_state(user_id, state)
                                await state['bot'].send_message(user_id, f"Открыта ЛОНГ позиция:\nТВХ: {tvx}\nStop-loss: {order['sl']}\nTake-profit: {order['tp']}")
                                continue
                            # cancellation condition per spec: if current price > take-profit, cancel
                            if price > tp:
                                state['order'] = None
                                UserStorage.set_trading_state(user_id, state)
                                await state['bot'].send_message(user_id, 'Лимитный ордер на ЛОНГ позицию отменен')
                                continue
                        else:  # SHORT
                            if price >= tvx:
                                state['position'] = {'side': 'SHORT', 'tvx': tvx, 'sl': order['sl'], 'tp': order['tp']}
                                order['executed'] = True
                                state['order'] = None
                                UserStorage.set_trading_state(user_id, state)
                                await state['bot'].send_message(user_id, f"Открыта ШОРТ позиция:\nТВХ: {tvx}\nStop-loss: {order['sl']}\nTake-profit: {order['tp']}")
                                continue
                            if price < tp:
                                state['order'] = None
                                UserStorage.set_trading_state(user_id, state)
                                await state['bot'].send_message(user_id, 'Лимитный ордер на ШОРТ позицию отменен')
                                continue

                    # if position exists, nothing automatic to do unless closed by user
        except asyncio.CancelledError:
            logging.info(f'Monitor task cancelled for {user_id}')
            return


manager = TradingManager()

    
async def restore_all(bot):
    """Restore persisted trading states and restart loops for running users."""
    states = UserStorage.list_trading_states()
    for uid_str, st in states.items():
        try:
            uid = int(uid_str)
        except Exception:
            continue
        if st.get('running'):
            # initialize in-memory state
            async with manager._lock:
                state = manager._states.get(uid, {})
                state.update({'running': True, 'bot': bot, 'task': None, 'order': st.get('order'), 'position': st.get('position'), 'monitor_task': None})
                manager._states[uid] = state
                # start trading loop
                task = asyncio.create_task(manager._run_trading_loop(uid))
                state['task'] = task
                # start monitor task if there is order/position
                if state.get('order') or state.get('position'):
                    mt = asyncio.create_task(manager._monitor_orders(uid))
                    state['monitor_task'] = mt

