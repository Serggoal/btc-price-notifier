
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Bot
from services.price_watcher import start_price_watcher
from services.storage import UserStorage
from services.bybit import get_btc_price
from services.bybit_eth import get_eth_price
from .keyboards import main_menu, notify_menu, btc_menu, eth_menu, inline_price
import logging

router = Router()



class PriceStates(StatesGroup):
    waiting_for_price = State()
    waiting_for_new_price = State()
    waiting_for_price_eth = State()
    waiting_for_new_price_eth = State()




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
    await message.answer('Раздел "Торговля" пока не реализован.', reply_markup=main_menu)
    await state.clear()


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
