from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton



main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Уведомления"), KeyboardButton(text="Торговля")],
    ],
    resize_keyboard=True
)

notify_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Цена BTC"), KeyboardButton(text="Цена ETH")],
        [KeyboardButton(text="Назад")],
    ],
    resize_keyboard=True
)

btc_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Текущая цена BTC"), KeyboardButton(text="Моя текущая цель BTC")],
        [KeyboardButton(text="Изменить цель BTC"), KeyboardButton(text="Удалить мою цель BTC")],
        [KeyboardButton(text="Назад")],
    ],
    resize_keyboard=True
)

eth_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Текущая цена ETH"), KeyboardButton(text="Моя текущая цель ETH")],
        [KeyboardButton(text="Изменить цель ETH"), KeyboardButton(text="Удалить мою цель ETH")],
        [KeyboardButton(text="Назад")],
    ],
    resize_keyboard=True
)

inline_price = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Обновить цену", callback_data="refresh_price")
        ]
    ]
)


trade_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Данные по свечам 15мин. ETH"), KeyboardButton(text="Открыть сделку")],
        [KeyboardButton(text="Старт торговли"), KeyboardButton(text="Стоп торговли"), KeyboardButton(text="Закрыть сделку")],
        [KeyboardButton(text="Статус торговли")],
        [KeyboardButton(text="Назад")],
    ],
    resize_keyboard=True
)
