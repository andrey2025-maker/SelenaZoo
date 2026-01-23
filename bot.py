import asyncio
import logging
import sys
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile

from config import Config
from database import Database
from utils.subscription import daily_subscription_check
from handlers.start import get_user_language

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def create_backup():
    """Простая функция создания бэкапа"""
    try:
        import shutil
        import gzip
        
        backup_dir = "database_backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"database_backup_{timestamp}.db.gz"
        backup_path = os.path.join(backup_dir, backup_name)
        
        with open("database.db", 'rb') as f_in:
            with gzip.open(backup_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        file_size = os.path.getsize(backup_path)
        logger.info(f"💾 Бэкап создан: {backup_name} ({file_size:,} байт)")
        return backup_path
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания бэкапа: {e}")
        return None

async def send_backup_to_admin(bot: Bot, backup_path: str):
    """Отправка бэкапа администратору"""
    try:
        if not os.path.exists(backup_path):
            logger.error(f"❌ Файл не найден: {backup_path}")
            return False
        
        file_size = os.path.getsize(backup_path)
        file_size_mb = file_size / (1024 * 1024)
        
        if file_size_mb > 48:  # Telegram лимит 50MB
            logger.warning(f"⚠️ Файл слишком большой: {file_size_mb:.1f} MB")
            return False
        
        # Читаем файл и создаем BufferedInputFile
        with open(backup_path, 'rb') as file:
            file_data = file.read()
            
        input_file = BufferedInputFile(
            file=file_data,
            filename=os.path.basename(backup_path)
        )
        
        await bot.send_document(
            chat_id=Config.ADMIN_ID,
            document=input_file,
            caption=f"💾 Бэкап базы данных\nРазмер: {file_size_mb:.2f} MB\nДата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        logger.info("✅ Бэкап отправлен администратору")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки бэкапа: {e}")
        return False

async def auto_backup_task(bot: Bot):
    """Задача автоматических бэкапов"""
    # Ждем 1 минуту после запуска
    await asyncio.sleep(60)
    
    # Создаем первый бэкап при запуске
    try:
        logger.info("🔄 Создаю стартовый бэкап...")
        backup_path = await create_backup()
        if backup_path:
            await send_backup_to_admin(bot, backup_path)
    except Exception as e:
        logger.error(f"❌ Ошибка стартового бэкапа: {e}")
    
    # Основной цикл
    while True:
        try:
            now = datetime.now()
            
            # Бэкап каждый день в 3:00 (для теста - каждый час)
            if now.hour == 3 and now.minute == 0:  # Каждый час в 00 минут
                logger.info("🔄 Создаю автоматический бэкап...")
                backup_path = await create_backup()
                
                if backup_path:
                    await send_backup_to_admin(bot, backup_path)
            
            # Ждем 1 минуту перед следующей проверкой
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в задаче бэкапа: {e}")
            await asyncio.sleep(300)

async def main():
    """Основная функция запуска бота"""
    if not Config.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден!")
        return
    
    # Проверяем наличие базы данных
    if not os.path.exists(Config.DATABASE_PATH):
        logger.warning(f"⚠️ База данных {Config.DATABASE_PATH} не найдена")
        logger.info("🆕 Создаю новую базу...")
        try:
            db = Database()  # Инициализация создаст базу
            logger.info("✅ Новая база создана")
        except Exception as e:
            logger.error(f"❌ Не удалось создать базу: {e}")
            return
    else:
        # Инициализация существующей БД
        try:
            db = Database()
            logger.info("✅ База данных инициализирована")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
            return
    
    # Создаем бота
    bot = Bot(
        token=Config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Проверяем доступ к каналу
    try:
        chat = await bot.get_chat(Config.SOURCE_CHANNEL_ID)
        logger.info(f"✅ Бот имеет доступ к каналу: {chat.title}")
    except Exception as e:
        logger.warning(f"⚠️ Нет доступа к каналу {Config.SOURCE_CHANNEL_ID}: {e}")
    
    # Создаем диспетчер
    dp = Dispatcher()

    # Регистрируем роутеры
    try:
        from handlers.start import router as start_router
        from handlers.settings import router as settings_router
        from handlers.admin import router as admin_router
        from handlers.channel import router as channel_router
        from handlers.group_commands import router as group_commands_router
        from handlers.publish import router as publish_router
        
        dp.include_router(group_commands_router)
        dp.include_router(start_router)
        dp.include_router(settings_router)
        dp.include_router(admin_router)
        dp.include_router(channel_router)
        dp.include_router(publish_router)
        
        logger.info("✅ Все роутеры зарегистрированы")
        
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта роутера: {e}")
        return
    
    # Запускаем фоновые задачи
    try:
        asyncio.create_task(daily_subscription_check(bot))
        logger.info("✅ Проверка подписок запущена")
        
        # Автобэкапы
        asyncio.create_task(auto_backup_task(bot))
        logger.info("✅ Автобэкапы запущены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска фоновых задач: {e}")
    
    # Запуск бота
    logger.info("🤖 Бот запущен и готов к работе!")
    
    try:
        bot_info = await bot.get_me()
        logger.info(f"👤 Бот: @{bot_info.username}")
        
        await dp.start_polling(bot)
        
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
        
        # Финальный бэкап
        try:
            logger.info("🔄 Создаю финальный бэкап...")
            backup_path = await create_backup()
            if backup_path:
                await send_backup_to_admin(bot, backup_path)
        except Exception as e:
            logger.error(f"❌ Ошибка финального бэкапа: {e}")
            
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        
    finally:
        await bot.session.close()
        logger.info("👋 Сессия бота закрыта")

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 BUILD A ZOO NOTIFICATION BOT")
    print("=" * 50)
    print("📢 Функции:")
    print("• Уведомления о фруктах и тотемах")
    print("• Админ-панель с рассылкой")
    print("• Автоматические бэкапы")
    print("=" * 50)
    
    asyncio.run(main())