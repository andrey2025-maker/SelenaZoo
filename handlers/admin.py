from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import logging
import asyncio

from database import Database
from config import Config
from utils.messages import locale_manager

logger = logging.getLogger(__name__)
router = Router()
db = Database()

# ========== СПИСОК АДМИНИСТРАТОРОВ ==========
ADMIN_IDS = [1835558263]  # ВАШ ID

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS
# ========== КОНЕЦ СПИСКА АДМИНОВ ==========

class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirmation = State()

# ========== ОСНОВНЫЕ АДМИН КОМАНДЫ ==========

async def show_stats(message_or_callback):
    """Показ статистики - работает и с Message и с CallbackQuery"""
    if isinstance(message_or_callback, types.CallbackQuery):
        user_id = message_or_callback.from_user.id
        message = message_or_callback.message
    else:
        user_id = message_or_callback.from_user.id
        message = message_or_callback
    
    if not is_admin(user_id):
        if isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        else:
            await message.answer("⛔ У вас нет прав администратора")
        return
    
    try:
        stats = db.get_statistics()
        
        # Форматируем статистику фруктов
        fruit_stats_text = ""
        if stats["fruit_stats"]:
            for fruit, count in stats["fruit_stats"].items():
                fruit_display = locale_manager.translate_fruit(fruit, "RUS") if fruit != "all" else "Все фрукты"
                fruit_stats_text += f"  • {fruit_display}: {count}\n"
        else:
            fruit_stats_text = "  • Нет данных\n"
        
        # Получаем пользователей за последние 7 дней
        week_ago = datetime.now() - timedelta(days=7)
        all_users = db.get_all_users()
        recent_users = []
        
        for user in all_users:
            created = user.get("created_at")
            if isinstance(created, str):
                try:
                    created = datetime.strptime(created, "%Y-%m-%d %H:%M:%S")
                    if created > week_ago:
                        recent_users.append(user)
                except:
                    pass
        
        text = locale_manager.get_text("ru", "admin.stats",
            total_users=stats["total_users"],
            active_subscribers=stats["active_subscribers"],
            fruit_stats=fruit_stats_text,
            free_totems=stats["free_totems"],
            paid_totems=stats["paid_totems"]
        )
        
        # Добавляем дополнительную статистику
        text += f"\n📈 За последние 7 дней: {len(recent_users)} новых"
        text += f"\n📊 Подписка: {stats['active_subscribers']}/{stats['total_users']} ({stats['active_subscribers']/stats['total_users']*100:.1f}%)"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить статистику", callback_data="admin_refresh_stats"),
                InlineKeyboardButton(text="📋 Полный список", callback_data="admin_userlist_full")
            ],
            [
                InlineKeyboardButton(text="📊 Детальная статистика", callback_data="admin_detailed_stats"),
                InlineKeyboardButton(text="🛠️ Админ-панель", callback_data="admin_panel")
            ]
        ])
        
        if isinstance(message_or_callback, types.CallbackQuery):
            try:
                await message.edit_text(text, reply_markup=keyboard)
            except:
                await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в show_stats: {e}")
        if isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)
        else:
            await message.answer(f"❌ Ошибка при получении статистики")

async def show_admin_panel(message_or_callback):
    """Показ админ-панели - работает и с Message и с CallbackQuery"""
    if isinstance(message_or_callback, types.CallbackQuery):
        user_id = message_or_callback.from_user.id
        message = message_or_callback.message
    else:
        user_id = message_or_callback.from_user.id
        message = message_or_callback
    
    if not is_admin(user_id):
        if isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        else:
            await message.answer("⛔ У вас нет прав администратора")
        return
    
    text = (
        "🛠️ <b>Панель администратора</b>\n\n"
        f"👑 Ваш ID: {user_id}\n"
        f"📋 Админов: {len(ADMIN_IDS)}\n\n"
        "Выберите действие:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="📋 Список", callback_data="admin_userlist")
        ],
        [
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="🔍 Поиск", callback_data="admin_search")
        ],
        [
            InlineKeyboardButton(text="🧹 Очистка", callback_data="admin_cleanup"),
            InlineKeyboardButton(text="🛠️ Утилиты", callback_data="admin_utils")
        ],
        [
            InlineKeyboardButton(text="ℹ️ О боте", callback_data="admin_about"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_refresh")
        ]
    ])
    
    if isinstance(message_or_callback, types.CallbackQuery):
        try:
            await message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        except:
            await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

# ========== КОМАНДЫ ЧАТА ==========

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Команда /admin"""
    await show_admin_panel(message)

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Команда /stats"""
    await show_stats(message)

# ========== CALLBACK ОБРАБОТЧИКИ ==========

@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: types.CallbackQuery):
    """Кнопка статистики"""
    await show_stats(callback)
    await callback.answer()

@router.callback_query(F.data == "admin_back_to_stats")
async def back_to_stats(callback: types.CallbackQuery):
    """Вернуться к статистике"""
    await show_stats(callback)
    await callback.answer("✅ Возврат к статистике")

@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: types.CallbackQuery):
    """Вернуться в админ-панель"""
    await show_admin_panel(callback)
    await callback.answer()

@router.callback_query(F.data == "admin_refresh_stats")
async def refresh_stats(callback: types.CallbackQuery):
    """Обновление статистики"""
    await show_stats(callback)
    await callback.answer("✅ Статистика обновлена!")

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: types.CallbackQuery, state: FSMContext):
    """Кнопка рассылки - ЗАПУСК РАССЫЛКИ"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    
    users = db.get_all_users()
    
    if not users:
        await callback.answer("❌ В базе нет пользователей", show_alert=True)
        return
    
    await callback.message.answer(
        f"📢 <b>Готов к рассылке!</b>\n\n"
        f"👥 Получателей: {len(users)}\n"
        f"✅ Активных: {sum(1 for u in users if u.get('is_subscribed'))}\n\n"
        f"<b>Отправьте сообщение для рассылки:</b>\n"
        f"(текст, фото, видео, документ)\n\n"
        f"❌ Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    
    # Сохраняем информацию для рассылки
    await state.update_data(
        broadcast_admin_id=callback.from_user.id,
        broadcast_start_time=datetime.now().strftime("%H:%M:%S")
    )
    
    # Устанавливаем состояние ожидания сообщения
    await state.set_state(BroadcastStates.waiting_for_message)
    await callback.answer("📢 Ожидаю сообщение для рассылки...")

@router.message(Command("cancel"))
async def cancel_broadcast(message: Message, state: FSMContext):
    """Отмена рассылки"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора")
        return
    
    current_state = await state.get_state()
    
    if current_state is None:
        await message.answer("❌ Нет активных операций для отмены")
        return
    
    if "BroadcastStates" in current_state:
        await state.clear()
        await message.answer("🚫 Рассылка отменена")
    else:
        await message.answer("❌ Нет активной рассылки для отмены")

@router.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Обработка сообщения для рассылки"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора")
        await state.clear()
        return
    
    data = await state.get_data()
    admin_id = data.get("broadcast_admin_id")
    
    # Проверяем, что это тот же админ
    if message.from_user.id != admin_id:
        await message.answer("❌ Вы не инициировали рассылку")
        await state.clear()
        return
    
    # Получаем всех пользователей
    users = db.get_all_users()
    
    # Показываем подтверждение
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, разослать", callback_data="broadcast_confirm"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="broadcast_cancel")
        ]
    ])
    
    # Сохраняем информацию о сообщении
    message_info = {
        "content_type": message.content_type,
        "has_text": bool(message.text or message.caption),
        "text_preview": (message.text or message.caption or "")[:100] + ("..." if len(message.text or message.caption or "") > 100 else "")
    }
    
    await state.update_data(
        broadcast_message_id=message.message_id,
        broadcast_chat_id=message.chat.id,
        broadcast_message_info=message_info
    )
    
    await message.answer(
        f"📢 <b>Подтверждение рассылки</b>\n\n"
        f"👥 Получателей: {len(users)}\n"
        f"📝 Тип: {message.content_type}\n"
        f"📄 Текст: {message_info['text_preview']}\n\n"
        f"<i>Разослать это сообщение всем пользователям?</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.callback_query(F.data.in_(["broadcast_confirm", "broadcast_cancel"]))
async def broadcast_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение или отмена рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    
    if callback.data == "broadcast_cancel":
        await callback.message.edit_text("🚫 Рассылка отменена")
        await state.clear()
        await callback.answer("🚫 Рассылка отменена")
        return
    
    # Получаем сохраненные данные
    data = await state.get_data()
    admin_id = data.get("broadcast_admin_id")
    message_id = data.get("broadcast_message_id")
    chat_id = data.get("broadcast_chat_id")
    
    if callback.from_user.id != admin_id:
        await callback.answer("❌ Вы не инициировали рассылку", show_alert=True)
        return
    
    users = db.get_all_users()
    total_users = len(users)
    
    # Редактируем сообщение о начале рассылки
    await callback.message.edit_text(f"🔄 Рассылка начата для {total_users} пользователей...")
    
    success_count = 0
    failed_count = 0
    failed_list = []
    
    # Рассылаем сообщение
    for user in users:
        try:
            # Получаем оригинальное сообщение
            original_message = await callback.bot.copy_message(
                chat_id=user["user_id"],
                from_chat_id=chat_id,
                message_id=message_id
            )
            success_count += 1
            
            # Задержка чтобы не превысить лимиты Telegram
            await asyncio.sleep(0.05)
            
        except Exception as e:
            failed_count += 1
            error_msg = str(e)
            user_info = f"ID: {user['user_id']}"
            
            if user.get("username"):
                user_info += f" (@{user['username']})"
            
            if "Forbidden" in error_msg or "bot was blocked" in error_msg:
                failed_list.append(f"{user_info} (заблокировал бота)")
            elif "chat not found" in error_msg:
                failed_list.append(f"{user_info} (чат не найден)")
            else:
                failed_list.append(f"{user_info} ({error_msg[:30]}...)")
    
    # Формируем отчет
    report = (
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📊 <b>Результаты:</b>\n"
        f"• Всего получателей: {total_users}\n"
        f"• Успешно отправлено: {success_count}\n"
        f"• Не удалось отправить: {failed_count}\n"
    )
    
    if failed_list:
        report += f"\n❌ <b>Ошибки отправки:</b>\n"
        for i, failed in enumerate(failed_list[:5], 1):
            report += f"{i}. {failed}\n"
        
        if len(failed_list) > 5:
            report += f"... и еще {len(failed_list) - 5} ошибок\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠️ В админ-панель", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(report, parse_mode="HTML", reply_markup=keyboard)
    await state.clear()
    await callback.answer("✅ Рассылка завершена")

# ========== ДРУГИЕ CALLBACK ОБРАБОТЧИКИ ==========

@router.callback_query(F.data == "admin_userlist")
async def admin_userlist_callback(callback: types.CallbackQuery):
    """Кнопка списка пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    await show_user_list(callback)
    await callback.answer()

async def show_user_list(callback: types.CallbackQuery):
    """Показ списка пользователей с ссылками"""
    users = db.get_all_users()
    
    if not users:
        await callback.message.answer("📭 В базе нет пользователей.")
        await callback.answer()
        return
    
    text = f"📋 <b>Список пользователей ({len(users)}):</b>\n\n"
    
    for i, user in enumerate(users[:10], 1):  # Показываем первые 10
        status = "✅" if user.get("is_subscribed") else "❌"
        user_id = user["user_id"]
        
        # Формируем ссылку на пользователя
        if user.get("username"):
            user_link = f"<a href='https://t.me/{user['username']}'>@{user['username']}</a>"
        else:
            user_link = f"<a href='tg://user?id={user_id}'>Пользователь {user_id}</a>"
        
        text += f"{i}. {user_link} - {status}\n"
    
    if len(users) > 10:
        text += f"\n... и еще {len(users) - 10} пользователей"
    
    # Добавляем статистику
    active_count = sum(1 for u in users if u.get("is_subscribed"))
    text += f"\n\n📊 <b>Статистика:</b>\n"
    text += f"• Активных: {active_count}/{len(users)}\n"
    text += f"• Процент: {active_count/len(users)*100:.1f}%"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="admin_broadcast")],
        [
            InlineKeyboardButton(text="📊 Назад к статистике", callback_data="admin_stats"),
            InlineKeyboardButton(text="🛠️ Админ-панель", callback_data="admin_panel")
        ]
    ])
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)

@router.callback_query(F.data == "admin_search")
async def admin_search_callback(callback: types.CallbackQuery):
    """Кнопка поиска"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    await callback.answer("🔍 Функция в разработке")
    await callback.message.answer("🔍 Поиск пользователей будет доступен в следующем обновлении.")

@router.callback_query(F.data == "admin_cleanup")
async def admin_cleanup_callback(callback: types.CallbackQuery):
    """Кнопка очистки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    await callback.answer("🧹 Функция в разработке")
    await callback.message.answer("🧹 Очистка базы будет доступна в следующем обновлении.")

@router.callback_query(F.data == "admin_utils")
async def admin_utils_callback(callback: types.CallbackQuery):
    """Кнопка утилит"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    await callback.answer("🛠️ Функция в разработке")
    await callback.message.answer("🛠️ Утилиты будут доступны в следующем обновлении.")

@router.callback_query(F.data == "admin_about")
async def admin_about_callback(callback: types.CallbackQuery):
    """Кнопка информации о боте"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    text = (
        "🤖 <b>Build a Zoo Notification Bot</b>\n\n"
        f"<b>Версия:</b> 1.0\n"
        f"<b>Разработчик:</b> Администратор\n"
        f"<b>Ваш ID:</b> {callback.from_user.id}\n"
        f"<b>Админов:</b> {len(ADMIN_IDS)}\n"
        f"<b>Канал:</b> {Config.SOURCE_CHANNEL_ID}\n\n"
        f"<i>Бот для уведомлений о фруктах и тотемах в Build a Zoo</i>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠️ В админ-панель", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "admin_refresh")
async def admin_refresh_callback(callback: types.CallbackQuery):
    """Кнопка обновления"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    await callback.answer("🔄 Панель обновлена!")

@router.callback_query(F.data == "admin_detailed_stats")
async def admin_detailed_stats_callback(callback: types.CallbackQuery):
    """Детальная статистика"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    await callback.answer("📊 Функция в разработке")
    await callback.message.answer("📊 Детальная статистика будет доступна в следующем обновлении.")

@router.callback_query(F.data == "admin_userlist_full")
async def admin_userlist_full_callback(callback: types.CallbackQuery):
    """Полный список пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    await show_user_list(callback)
    await callback.answer()

# ========== ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ==========

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    """Команда рассылки"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора")
        return
    
    users = db.get_all_users()
    
    await message.answer(
        f"📢 <b>Команда рассылки</b>\n\n"
        f"👥 Получателей: {len(users)}\n\n"
        f"Отправьте сообщение для рассылки, или нажмите кнопку в админ-панели.",
        parse_mode="HTML"
    )
    
    # Активируем режим рассылки
    await state.update_data(broadcast_admin_id=message.from_user.id)
    await state.set_state(BroadcastStates.waiting_for_message)

@router.message(Command("help_admin"))
async def cmd_help_admin(message: Message):
    """Справка по админ-командам"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора")
        return
    
    help_text = (
        "🛠️ <b>Админ-команды:</b>\n\n"
        "<b>/admin</b> - 🛠️ Главная панель администратора\n"
        "<b>/stats</b> - 📊 Статистика бота\n"
        "<b>/broadcast</b> - 📢 Рассылка сообщений\n"
        "<b>/help_admin</b> - ❓ Эта справка\n\n"
        "<b>📋 В админ-панели:</b>\n"
        "• 📊 Статистика\n"
        "• 📋 Список пользователей\n"
        "• 📢 Рассылка\n"
        "• 🔍 Поиск\n"
        "• 🧹 Очистка\n"
        "• 🛠️ Утилиты\n"
        "• ℹ️ О боте\n\n"
        f"<b>👑 Администраторы:</b> {len(ADMIN_IDS)}"
    )
    
    await message.answer(help_text, parse_mode="HTML")