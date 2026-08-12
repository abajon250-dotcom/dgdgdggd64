import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Импортируем роутеры
from handlers import start


# Если есть дополнительные модули (например, admin или vk), раскомментируй:
# from handlers import admin, vk_accs

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )

    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        raise ValueError("Параметр BOT_TOKEN не найден в .env файле!")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем роутер старта и функционала
    dp.include_router(start.router)

    # Регистрация других роутеров (если есть)
    # dp.include_router(admin.router)
    # dp.include_router(vk_accs.router)

    # Удаляем незавершенные апдейты и старт
    await bot.delete_webhook(drop_pending_updates=True)

    print("🚀 Бот успешно запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Бот остановлен!")