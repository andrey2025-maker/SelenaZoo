import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import Config
from database import Database
from utils.subscription import daily_subscription_check

# Настройка логирования - БОЛЕЕ ПОДРОБНОЕ
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Включаем логирование для aiogram
logging.getLogger("aiogram").setLevel(logging.INFO)

async def main():
    """Основная функция запуска бота"""
    # Проверяем наличие токена
    if not Config.BOT_TOKEN:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        logger.error("Создайте файл .env и добавьте BOT_TOKEN=ваш_токен")
        return
    
    # Инициализация базы данных
    try:
        db = Database()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return
    
    # Создаем бота и диспетчер
    bot = Bot(
        token=Config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Проверяем доступ к каналу
    try:
        chat = await bot.get_chat(Config.SOURCE_CHANNEL_ID)
        logger.info(f"✅ Бот имеет доступ к каналу: {chat.title} (ID: {chat.id})")
    except Exception as e:
        logger.error(f"❌ Бот НЕ имеет доступа к каналу {Config.SOURCE_CHANNEL_ID}: {e}")
        logger.error("Добавьте бота в канал как администратора!")
        logger.warning("⚠️ Бот продолжает работу, но не будет получать сообщения из канала")
    
    dp = Dispatcher()
    
    # Импортируем и регистрируем роутеры
    try:
        # Импорт роутеров
        from handlers.start import router as start_router
        from handlers.settings import router as settings_router
        from handlers.admin import router as admin_router
        from handlers.channel import router as channel_router
        
        # Регистрируем роутеры
        dp.include_router(start_router)
        dp.include_router(settings_router)
        dp.include_router(admin_router)
        dp.include_router(channel_router)
        
        logger.info("✅ Все роутеры зарегистрированы")
        
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта роутера: {e}")
        logger.error(f"Подробности: {e.__class__.__name__}: {str(e)}")
        logger.error("Проверьте структуру папок и файлов handlers/")
        return
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации роутеров: {e}")
        logger.error(f"Тип ошибки: {type(e).__name__}")
        logger.error(f"Подробности: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return
    
    # Запускаем фоновую задачу проверки подписок
    try:
        asyncio.create_task(daily_subscription_check(bot))
        logger.info("✅ Фоновая задача проверки подписок запущена")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска фоновой задачи: {e}")
    
    logger.info("🤖 Бот запущен и готов к работе!")
    logger.info(f"📊 ID канала для мониторинга: {Config.SOURCE_CHANNEL_ID}")
    
    try:
        # Показываем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"👤 Бот: @{bot_info.username} ({bot_info.full_name})")
        logger.info(f"🆔 ID бота: {bot_info.id}")
        
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)
    finally:
        await bot.session.close()
        logger.info("👋 Сессия бота закрыта")

if __name__ == "__main__":
    asyncio.run(main())