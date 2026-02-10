
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Bot
from services.price_watcher import start_price_watcher
from services.storage import UserStorage
from services.bybit import get_btc_price, get_15m_candles
from services.trading import manager as trading_manager
from services.bybit_eth import get_eth_price
from services.bybit_trade import get_balance, get_open_orders, create_order, cancel_order, normalize_qty
from config import OWNER_TELEGRAM_ID
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from .keyboards import main_menu, notify_menu, btc_menu, eth_menu, inline_price, trade_menu
import logging

router = Router()



class PriceStates(StatesGroup):
    waiting_for_price = State()
    waiting_for_new_price = State()
    waiting_for_price_eth = State()
    waiting_for_new_price_eth = State()


class TradeOpenStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_leverage = State()




@router.message(Command('start'))
async def cmd_start(message: Message, state: FSMContext):
    await message.answer(
        'Добро пожаловать! Выберите раздел:',
        reply_markup=main_menu
    )
    await state.clear()


@router.message(F.text.lower() == "уведомления")
async def notify_section(message: Message, state: FSMContext):
    await message.answer('Выберите инструмент:', reply_markup=notify_menu)
    await state.clear()


@router.message(F.text.lower() == "торговля")
async def trade_section(message: Message, state: FSMContext):
    await message.answer('Торговля:', reply_markup=trade_menu)
    await state.clear()


@router.message(F.text.lower() == "данные по свечам 15мин. eth")
async def trade_candle_data(message: Message, state: FSMContext):
    try:
        # request 3 most recent 15m klines: [current_incomplete, last_closed, prev_closed]
        klines = await get_15m_candles(symbol='ETHUSDT', limit=3)
        if not klines or len(klines) < 3:
            await message.answer('Недостаточно данных о свечах.', reply_markup=trade_menu)
            await state.clear()
            return

        # Most recent first: klines[0] may be current incomplete candle.
        # We need two penultimate closed candles: earlier = klines[2], later = klines[1]
        earlier = klines[2]
        later = klines[1]

        from datetime import datetime, timezone, timedelta

        def fmt_time_ms(ts_ms):
            try:
                t = int(ts_ms)
                # Bybit returns ms
                if t > 1_000_000_000_000:
                    dt = datetime.fromtimestamp(t / 1000, tz=timezone.utc)
                else:
                    dt = datetime.fromtimestamp(t, tz=timezone.utc)
                dt = dt.astimezone(timezone(timedelta(hours=5)))
                return dt.strftime('%H:%M (GMT+5)')
            except Exception:
                return str(ts_ms)

        lines = []
        lines.append('Две предпоследние закрытые свечи:')
        lines.append('1.1) ' + fmt_time_ms(earlier.get('open_time')))
        lines.append('1.2) open_1: ' + str(earlier.get('open')))
        lines.append('1.3) high_1: ' + str(earlier.get('high')))
        lines.append('1.4) low_1: ' + str(earlier.get('low')))
        lines.append('1.5) close_1: ' + str(earlier.get('close')))
        lines.append('---')
        lines.append('2.1) ' + fmt_time_ms(later.get('open_time')))
        lines.append('2.2) open_2: ' + str(later.get('open')))
        lines.append('2.3) high_2: ' + str(later.get('high')))
        lines.append('2.4) low_2: ' + str(later.get('low')))
        lines.append('2.5) close_2: ' + str(later.get('close')))

        try:
            high_1 = float(earlier.get('high'))
            high_2 = float(later.get('high'))
            low_1 = float(earlier.get('low'))
            low_2 = float(later.get('low'))
            if high_2 > high_1:
                lines.append('\nПроизошло повышение MAX')
            if low_2 < low_1:
                lines.append('\nПроизошло снижение MIN')
        except Exception:
            pass

        await message.answer('\n'.join(lines), reply_markup=trade_menu)
    except Exception as e:
        logging.error(f'Error fetching ETH 15m candles: {e}')
        await message.answer('Ошибка получения данных о свечах. Попробуйте позже.', reply_markup=trade_menu)
    await state.clear()


@router.message(F.text.regexp(r'(?i)^\s*открыть\s+сделку\s*$'))
async def trade_open_order(message: Message, state: FSMContext):
    logging.info(f'Invoked trade_open_order by user {message.from_user.id} text={message.text!r}')
    await state.set_state(TradeOpenStates.waiting_for_amount)
    await message.answer('• На какую сумму вы хотите открыть сделку в $ ?')
@router.message(TradeOpenStates.waiting_for_amount)
async def handle_trade_amount(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        amount = float(text.replace(',', '.'))
        if amount <= 0:
            raise ValueError()
    except Exception:
        await message.answer('Введите корректную положительную сумму в $ (например: 1)')
        return
    await state.update_data(trade_amount=amount)
    await state.set_state(TradeOpenStates.waiting_for_leverage)
    await message.answer('• с каким плечом вы хотите открыть сделку?')


@router.message(TradeOpenStates.waiting_for_leverage)
async def handle_trade_leverage(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        leverage = float(text)
        if leverage <= 0:
            raise ValueError()
    except Exception:
        await message.answer('Введите корректный положительный размер плеча (например: 10)')
        return
    data = await state.get_data()
    amount = data.get('trade_amount')
    # fetch current futures price for ETH
    try:
        from services.bybit import get_futures_price
        price = await get_futures_price(symbol='ETHUSDT')
    except Exception as e:
        logging.error(f'Error fetching futures price: {e}')
        await message.answer('Ошибка получения текущей цены ETH. Попробуйте позже.', reply_markup=trade_menu)
        await state.clear()
        return

    # compute projected qty and validate minimum size immediately after leverage
    try:
        notional = amount * float(leverage)
        qty = notional / float(price)
        rounded_qty, ok = normalize_qty(qty, min_size=0.01, step=0.001)
        if not ok:
            await state.clear()
            await message.answer('Слишком маленький размер позиции. Увеличьте сумму сделки или плечо.', reply_markup=trade_menu)
            return
    except Exception as e:
        logging.error(f'Error computing qty for leverage check: {e}')
        await message.answer('Ошибка проверки размера позиции. Попробуйте ещё раз.', reply_markup=trade_menu)
        await state.clear()
        return

    # show confirmation and inline buttons
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='🟩 Открыть ЛОНГ', callback_data=f'trade_exec|LONG|{amount}|{leverage}'),
        InlineKeyboardButton(text='🟥 Открыть ШОРТ', callback_data=f'trade_exec|SHORT|{amount}|{leverage}'),
    ],[
        InlineKeyboardButton(text='🟦 Отмена', callback_data='trade_exec|CANCEL')
    ]])

    msg = (f'Текущая цена ETH: {price}\n'
           f'Сумма позиции (USD): {amount}\n'
           f'Размер плеча: {leverage}\n\n'
           f'Нажмите кнопку для открытия позиции:')
    await message.answer(msg, reply_markup=kb)
    await state.clear()


@router.message(F.text.lower() == "старт торговли")
async def start_trading_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    await trading_manager.start(user_id, bot)
    await state.clear()


@router.message(F.text.lower() == "стоп торговли")
async def stop_trading_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    await trading_manager.stop(user_id, bot)
    await state.clear()


@router.message(F.text.lower() == "закрыть сделку")
async def close_trade_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    await trading_manager.close_position(user_id, bot)
    await state.clear()


@router.message(F.text.lower() == "статус торговли")
async def trading_status_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    await trading_manager.status(user_id, bot)
    await state.clear()


def _is_owner(user_id: int) -> bool:
    return OWNER_TELEGRAM_ID is not None and int(user_id) == int(OWNER_TELEGRAM_ID)


@router.message(Command('balance'))
async def cmd_balance(message: Message):
    user_id = message.from_user.id
    if not _is_owner(user_id):
        await message.answer('Доступ запрещён')
        return
    try:
        res = await get_balance()
        await message.answer(f'Баланс: {res}')
    except Exception as e:
        logging.error(f'Balance error: {e}')
        await message.answer('Ошибка получения баланса')


@router.message(Command('orders'))
async def cmd_orders(message: Message):
    user_id = message.from_user.id
    if not _is_owner(user_id):
        await message.answer('Доступ запрещён')
        return
    try:
        res = await get_open_orders()
        await message.answer(f'Open orders: {res}')
    except Exception as e:
        logging.error(f'Orders error: {e}')
        await message.answer('Ошибка получения ордеров')


@router.message(Command('buy'))
async def cmd_buy(message: Message):
    user_id = message.from_user.id
    if not _is_owner(user_id):
        await message.answer('Доступ запрещён')
        return
    # expected: /buy SYMBOL QTY [PRICE]
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer('Использование: /buy SYMBOL QTY [PRICE]')
        return
    symbol = parts[1]
    qty = parts[2]
    price = None
    order_type = 'Market'
    if len(parts) >= 4:
        price = parts[3]
        order_type = 'Limit'

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Подтвердить', callback_data=f'confirm_order|BUY|{symbol}|{qty}|{price or ""}|{order_type}'),
        InlineKeyboardButton(text='Отменить', callback_data='confirm_order|CANCEL')
    ]])
    await message.answer(f'Подтвердите BUY {symbol} qty={qty} price={price or "market"}', reply_markup=kb)


@router.message(Command('sell'))
async def cmd_sell(message: Message):
    user_id = message.from_user.id
    if not _is_owner(user_id):
        await message.answer('Доступ запрещён')
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer('Использование: /sell SYMBOL QTY [PRICE]')
        return
    symbol = parts[1]
    qty = parts[2]
    price = None
    order_type = 'Market'
    if len(parts) >= 4:
        price = parts[3]
        order_type = 'Limit'

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Подтвердить', callback_data=f'confirm_order|SELL|{symbol}|{qty}|{price or ""}|{order_type}'),
        InlineKeyboardButton(text='Отменить', callback_data='confirm_order|CANCEL')
    ]])
    await message.answer(f'Подтвердите SELL {symbol} qty={qty} price={price or "market"}', reply_markup=kb)


@router.message(Command('cancel'))
async def cmd_cancel(message: Message):
    user_id = message.from_user.id
    if not _is_owner(user_id):
        await message.answer('Доступ запрещён')
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer('Использование: /cancel SYMBOL ORDER_LINK_ID')
        return
    symbol = parts[1]
    order_id = parts[2]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Подтвердить', callback_data=f'confirm_cancel|{symbol}|{order_id}'),
        InlineKeyboardButton(text='Отменить', callback_data='confirm_cancel|CANCEL')
    ]])
    await message.answer(f'Подтвердите отмену ордера {order_id} для {symbol}', reply_markup=kb)


@router.callback_query(F.data.startswith('confirm_order'))
async def confirm_order_callback(call: CallbackQuery):
    user_id = call.from_user.id
    if not _is_owner(user_id):
        await call.answer('Доступ запрещён', show_alert=True)
        return
    parts = call.data.split('|')
    if len(parts) < 2 or parts[1] == 'CANCEL':
        await call.message.edit_text('Операция отменена.')
        await call.answer()
        return
    # format: confirm_order|BUY|SYMBOL|QTY|PRICE|TYPE
    _, action, symbol, qty, price, order_type = parts
    try:
        if price == '':
            price_val = None
        else:
            price_val = float(price)
        qty_val = float(qty)
    except Exception:
        await call.message.edit_text('Неправильные параметры ордера.')
        await call.answer()
        return

    try:
        res = await create_order(symbol=symbol, side=action, qty=qty_val, order_type=order_type, price=price_val)
        await call.message.edit_text(f'Результат: {res}')
        await call.answer('Ордер отправлен')
    except Exception as e:
        logging.error(f'Create order error: {e}')
        await call.message.edit_text('Ошибка создания ордера')
        await call.answer()


@router.callback_query(F.data.startswith('trade_exec'))
async def trade_exec_callback(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not _is_owner(user_id):
        await call.answer('Доступ запрещён', show_alert=True)
        return
    parts = call.data.split('|')
    if len(parts) < 2 or parts[1] == 'CANCEL':
        await state.clear()
        await call.message.edit_text('Операция отменена.')
        await call.message.answer('Торговля:', reply_markup=trade_menu)
        await call.answer()
        return
    # trade_exec|LONG|{amount}|{leverage}
    _, side, amount_s, lev_s = parts
    try:
        amount = float(amount_s)
        leverage = float(lev_s)
    except Exception:
        await call.message.edit_text('Некорректные параметры сделки.')
        await call.answer()
        return

    # get current futures price
    try:
        from services.bybit import get_futures_price
        price = await get_futures_price(symbol='ETHUSDT')
    except Exception as e:
        logging.error(f'Error fetching futures price for exec: {e}')
        await call.message.edit_text('Ошибка получения цены ETH. Попробуйте позже.')
        await call.message.answer('Торговля:', reply_markup=trade_menu)
        await call.answer()
        return

    # Compute qty in base currency: notional = amount * leverage
    notional = amount * leverage
    qty = notional / float(price)

    # Normalize qty to allowed step and minimum size
    rounded_qty, ok = normalize_qty(qty, min_size=0.01, step=0.001)
    if not ok:
        await state.clear()
        await call.message.edit_text('Слишком маленький размер позиции. Увеличьте сумму сделки или плечо.')
        await call.message.answer('Торговля:', reply_markup=trade_menu)
        await call.answer()
        return

    try:
        if side == 'LONG':
            action = 'Buy'
        else:
            action = 'Sell'
        res = await create_order(symbol='ETHUSDT', side=action, qty=qty, order_type='Market', price=None, category='linear')
        await state.clear()
        await call.message.edit_text(f'Ваша {"ЛОНГ" if side=="LONG" else "ШОРТ"} позиция открыта.\nРезультат: {res}')
        await call.message.answer('Торговля:', reply_markup=trade_menu)
        await call.answer()
    except Exception as e:
        logging.error(f'Trade exec error: {e}')
        await state.clear()
        await call.message.edit_text('Ошибка при открытии позиции.')
        await call.message.answer('Торговля:', reply_markup=trade_menu)
        await call.answer()


@router.callback_query(F.data.startswith('confirm_cancel'))
async def confirm_cancel_callback(call: CallbackQuery):
    user_id = call.from_user.id
    if not _is_owner(user_id):
        await call.answer('Доступ запрещён', show_alert=True)
        return
    parts = call.data.split('|')
    if len(parts) < 2 or parts[1] == 'CANCEL':
        await call.message.edit_text('Операция отменена.')
        await call.answer()
        return
    _, symbol, order_id = parts
    try:
        res = await cancel_order(symbol=symbol, order_id=order_id)
        await call.message.edit_text(f'Отмена: {res}')
        await call.answer('Отменено')
    except Exception as e:
        logging.error(f'Cancel order error: {e}')
        await call.message.edit_text('Ошибка отмены ордера')
        await call.answer()


@router.message(F.text.lower() == "цена btc")
async def btc_section(message: Message, state: FSMContext):
    await message.answer('Меню BTC:', reply_markup=btc_menu)
    await state.clear()


@router.message(F.text.lower() == "цена eth")
async def eth_section(message: Message, state: FSMContext):
    await message.answer('Меню ETH:', reply_markup=eth_menu)
    await state.clear()


@router.message(F.text.lower() == "назад")
async def go_back(message: Message, state: FSMContext):
    await message.answer('Главное меню:', reply_markup=main_menu)
    await state.clear()





@router.message(Command('price'))
@router.message(F.text.lower() == "текущая цена btc")
async def cmd_price(message: Message):
    try:
        price = await get_btc_price()
        await message.answer(f'Текущая цена BTC: <b>{price}</b>', reply_markup=inline_price)
    except Exception as e:
        await message.answer('Ошибка получения цены BTC. Попробуйте позже.')


@router.message(F.text.lower() == "текущая цена eth")
async def cmd_price_eth(message: Message):
    try:
        price = await get_eth_price()
        await message.answer(f'Текущая цена ETH: <b>{price}</b>', reply_markup=inline_price)
    except Exception as e:
        await message.answer('Ошибка получения цены ETH. Попробуйте позже.')



@router.message(F.text.lower() == "моя текущая цель btc")
async def my_target_btc(message: Message):
    user_id = message.from_user.id
    target = UserStorage.get_target(user_id)
    if target is not None:
        await message.answer(f'Ваша текущая цель BTC: <b>{target}</b>', reply_markup=btc_menu)
    else:
        await message.answer('Цели BTC ещё нет', reply_markup=btc_menu)


@router.message(F.text.lower() == "моя текущая цель eth")
async def my_target_eth(message: Message):
    user_id = message.from_user.id
    target = UserStorage.get_target(user_id, coin="ETH")
    if target is not None:
        await message.answer(f'Ваша текущая цель ETH: <b>{target}</b>', reply_markup=eth_menu)
    else:
        await message.answer('Цели ETH ещё нет', reply_markup=eth_menu)



@router.message(F.text.lower() == "удалить мою цель btc")
async def delete_target_btc(message: Message):
    user_id = message.from_user.id
    if UserStorage.get_target(user_id) is not None:
        UserStorage.clear_target(user_id)
        await message.answer('Ваша цель BTC удалена.', reply_markup=btc_menu)
    else:
        await message.answer('Цели BTC для удаления нет.', reply_markup=btc_menu)


@router.message(F.text.lower() == "удалить мою цель eth")
async def delete_target_eth(message: Message):
    user_id = message.from_user.id
    if UserStorage.get_target(user_id, coin="ETH") is not None:
        UserStorage.clear_target(user_id, coin="ETH")
        await message.answer('Ваша цель ETH удалена.', reply_markup=eth_menu)
    else:
        await message.answer('Цели ETH для удаления нет.', reply_markup=eth_menu)


@router.callback_query(F.data == "refresh_price")
async def refresh_price_callback(call: CallbackQuery):
    try:
        price = await get_btc_price()
        await call.message.edit_text(f'Текущая цена BTC: <b>{price}</b>', reply_markup=inline_price)
        await call.answer("Цена обновлена")
    except Exception:
        await call.answer('Ошибка получения цены', show_alert=True)




@router.message(Command('setprice'))
@router.message(F.text.lower() == "изменить цель btc")
async def cmd_setprice_btc(message: Message, state: FSMContext):
    await message.answer('Введите новую целевую цену BTC:', reply_markup=btc_menu)
    await state.set_state(PriceStates.waiting_for_new_price)


@router.message(F.text.lower() == "изменить цель eth")
async def cmd_setprice_eth(message: Message, state: FSMContext):
    await message.answer('Введите новую целевую цену ETH:', reply_markup=eth_menu)
    await state.set_state(PriceStates.waiting_for_new_price_eth)




@router.message(PriceStates.waiting_for_price, F.text.regexp(r'^\d+(\.\d+)?$'))
async def set_target_price_btc(message: Message, state: FSMContext, bot: Bot):
    price = float(message.text)
    user_id = message.from_user.id
    UserStorage.set_target(user_id, price)
    await message.answer(
        f'Целевая цена BTC установлена: <b>{price}</b>\nЯ сообщу, когда цена будет достигнута.',
        reply_markup=btc_menu
    )
    await state.clear()
    await start_price_watcher(user_id, price, bot)


@router.message(PriceStates.waiting_for_new_price, F.text.regexp(r'^\d+(\.\d+)?$'))
async def update_target_price_btc(message: Message, state: FSMContext, bot: Bot):
    price = float(message.text)
    user_id = message.from_user.id
    UserStorage.set_target(user_id, price)
    await message.answer(
        f'Новая целевая цена BTC установлена: <b>{price}</b>\nЯ сообщу, когда цена будет достигнута.',
        reply_markup=btc_menu
    )
    await state.clear()
    await start_price_watcher(user_id, price, bot)



from services.price_watcher import start_price_watcher_eth

@router.message(PriceStates.waiting_for_price_eth, F.text.regexp(r'^\d+(\.\d+)?$'))
async def set_target_price_eth(message: Message, state: FSMContext, bot: Bot):
    price = float(message.text)
    user_id = message.from_user.id
    UserStorage.set_target(user_id, price, coin="ETH")
    await message.answer(
        f'Целевая цена ETH установлена: <b>{price}</b>\nЯ сообщу, когда цена будет достигнута.',
        reply_markup=eth_menu
    )
    await state.clear()
    await start_price_watcher_eth(user_id, price, bot)



@router.message(PriceStates.waiting_for_new_price_eth, F.text.regexp(r'^\d+(\.\d+)?$'))
async def update_target_price_eth(message: Message, state: FSMContext, bot: Bot):
    price = float(message.text)
    user_id = message.from_user.id
    UserStorage.set_target(user_id, price, coin="ETH")
    await message.answer(
        f'Новая целевая цена ETH установлена: <b>{price}</b>\nЯ сообщу, когда цена будет достигнута.',
        reply_markup=eth_menu
    )
    await state.clear()
    await start_price_watcher_eth(user_id, price, bot)



@router.message(PriceStates.waiting_for_new_price, F.text.regexp(r'^\d+(\.\d+)?$'))
async def update_target_price(message: Message, state: FSMContext, bot: Bot):
    price = float(message.text)
    user_id = message.from_user.id
    UserStorage.set_target(user_id, price)
    await message.answer(
        f'Новая целевая цена BTC установлена: <b>{price}</b>\nЯ сообщу, когда цена будет достигнута.',
        reply_markup=main_menu
    )
    await state.clear()
    await start_price_watcher(user_id, price, bot)




@router.message(PriceStates.waiting_for_price)
async def invalid_price_btc(message: Message):
    await message.answer('Пожалуйста, введите корректное число (например, 45000).', reply_markup=btc_menu)


@router.message(PriceStates.waiting_for_new_price)
async def invalid_new_price_btc(message: Message):
    await message.answer('Пожалуйста, введите корректное число (например, 45000).', reply_markup=btc_menu)


@router.message(PriceStates.waiting_for_price_eth)
async def invalid_price_eth(message: Message):
    await message.answer('Пожалуйста, введите корректное число (например, 3500).', reply_markup=eth_menu)


@router.message(PriceStates.waiting_for_new_price_eth)
async def invalid_new_price_eth(message: Message):
    await message.answer('Пожалуйста, введите корректное число (например, 3500).', reply_markup=eth_menu)


@router.message(PriceStates.waiting_for_new_price)
async def invalid_new_price(message: Message):
    await message.answer('Пожалуйста, введите корректное число (например, 45000).', reply_markup=main_menu)

def register_handlers(dp):
    dp.include_router(router)
