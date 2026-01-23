from datetime import datetime, timedelta
import asyncio
from aiogram import Bot
from database import Database
from config import Config
from utils.messages import locale_manager

db = Database()

async def check_user_subscription(user_id: int, group_id: int, bot: Bot, ignore_exceptions: bool = False) -> bool:
    """Проверка подписки с учетом исключений"""
    # Проверяем, есть ли пользователь в исключениях
    if not ignore_exceptions and db.is_exception(user_id):
        return True
    
    try:
        chat_member = await bot.get_chat_member(group_id, user_id)
        return chat_member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Error checking subscription for {user_id}: {e}")
        return False

async def daily_subscription_check(bot: Bot):
    """Ежедневная проверка подписок всех пользователей"""
    while True:
        try:
            users = db.get_all_users()
            unsubscribed_users = []
            
            for user in users:
                user_id = user["user_id"]
                
                # Проверяем подписку (игнорируем исключения для проверки)
                is_subscribed = await check_user_subscription(
                    user_id, 
                    Config.REQUIRED_GROUP_ID, 
                    bot,
                    ignore_exceptions=True  # Игнорируем исключения для проверки
                )
                
                # Проверяем, есть ли пользователь в исключениях
                is_exception = db.is_exception(user_id)
                
                # Если пользователь в исключениях, считаем его подписанным
                if is_exception:
                    is_subscribed = True
                
                # Обновляем статус в БД
                db.update_subscription(user_id, is_subscribed)
                
                # Если пользователь отписался и не в исключениях, отправляем уведомление
                if user["is_subscribed"] and not is_subscribed and not is_exception:
                    unsubscribed_users.append(user_id)
            
            # Отправляем уведомления отписавшимся пользователям
            for user_id in unsubscribed_users:
                user = db.get_user(user_id)
                lang = user.get("language", "RUS")
                lang_code = "ru" if lang == "RUS" else "en"
                
                try:
                    text = locale_manager.get_text(lang_code, "notifications.unsubscribed")
                    await bot.send_message(user_id, text)
                except Exception as e:
                    print(f"Failed to send unsubscription notification to {user_id}: {e}")
            
            print(f"Daily subscription check completed. Checked {len(users)} users.")
            
        except Exception as e:
            print(f"Error in daily subscription check: {e}")
        
        # Ждем 24 часа до следующей проверки
        await asyncio.sleep(Config.SUBSCRIPTION_CHECK_INTERVAL)