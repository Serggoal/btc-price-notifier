
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from config import TELEGRAM_BOT_TOKEN
from bot.handlers import register_handlers
from services.trading import restore_all

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

async def main():
    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher()
    register_handlers(dp)
    # restore trading state (start any persisted trading loops)
    await restore_all(bot)
    logging.info('Bot started')
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
