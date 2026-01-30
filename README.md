# BTC Price Notifier Telegram Bot

A production-ready Telegram bot that notifies you when the price of Bitcoin (BTC) reaches your target value. Built with Python, aiogram, and Bybit API.

## Features
- Удобное меню с разделами "Уведомления" и "Торговля"
- Реальное отслеживание цен BTC и ETH через Bybit API
- Установка и изменение целевой цены для BTC и ETH
- Запрос текущей цены BTC и ETH в любой момент
- Просмотр и удаление своей цели для BTC и ETH
- Telegram-уведомления при достижении цели
- Фоновая проверка цен каждые N секунд
- Логирование событий и обработка ошибок

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/btc-price-notifier.git
   cd btc-price-notifier/project
   ```
2. **Create and activate a virtual environment (optional but recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure environment variables:**
   - Copy `.env.example` to `.env` and fill in your values.
   ```bash
   cp .env.example .env
   ```

## Usage

1. **Run the bot:**
   ```bash
   python main.py
   ```
2. **Interact in Telegram:**
    - После запуска используйте главное меню с кнопками:
       - "Уведомления" — откроет меню для BTC и ETH
       - "Торговля" — пока не реализовано
    - В разделе "Уведомления" доступны:
       - "Цена BTC":
          - "Текущая цена BTC"
          - "Моя текущая цель BTC"
          - "Изменить цель BTC"
          - "Удалить мою цель BTC"
       - "Цена ETH":
          - "Текущая цена ETH"
          - "Моя текущая цель ETH"
          - "Изменить цель ETH"
          - "Удалить мою цель ETH"
    - Все действия доступны через кнопки, команды не требуются

## Example .env
```
TELEGRAM_BOT_TOKEN=your_telegram_token_here
BYBIT_API_URL=https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT
CHECK_INTERVAL=60
```

## Project Structure
```
project/
 ├── bot/
 │   ├── handlers.py
 │   ├── keyboards.py
 ├── services/
 │   ├── bybit.py
 │   ├── bybit_eth.py
 │   ├── price_watcher.py
 │   ├── storage.py
 ├── config.py
 ├── main.py
 ├── requirements.txt
 ├── .env.example
 ├── README.md
```

## License
MIT
