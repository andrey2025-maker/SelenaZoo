from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import logging
import asyncio
from typing import List, Dict
from backup_utils import backup_manager
import os

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

# ========== СОСТОЯНИЯ ДЛЯ РАССЫЛКИ ==========
class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirmation = State()

# ========== СОСТОЯНИЯ ДЛЯ ЧАТА ==========
class ChatStates(StatesGroup):
    waiting_for_user = State()
    chatting = State()

# ========== СОСТОЯНИЯ ДЛЯ ИСКЛЮЧЕНИЙ ==========
class ExceptionStates(StatesGroup):
    waiting_for_user_input = State()

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ДЛЯ ПАГИНАЦИИ ==========
USER_PER_PAGE = 10

# ========== ГЛОБАЛЬНЫЙ СЛОВАРЬ ДЛЯ АКТИВНЫХ ЧАТОВ ==========
active_chats = {}  # {user_id: admin_id}

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

async def get_user_page(page: int = 0) -> tuple[str, InlineKeyboardMarkup, int]:
    """Получение страницы пользователей"""
    users = db.get_all_users()
    total_pages = (len(users) + USER_PER_PAGE - 1) // USER_PER_PAGE if users else 1
    
    start_idx = page * USER_PER_PAGE
    end_idx = start_idx + USER_PER_PAGE
    page_users = users[start_idx:end_idx] if users else []
    
    text = f"📋 <b>Список пользователей ({len(users)})</b>\n"
    text += f"📄 Страница {page + 1}/{total_pages or 1}\n\n"
    
    if page_users:
        for i, user in enumerate(page_users, start_idx + 1):
            status = "✅" if user.get("is_subscribed") else "❌"
            user_id = user["user_id"]
            
            if user.get("username"):
                user_link = f"<a href='https://t.me/{user['username']}'>@{user['username']}</a>"
            else:
                user_link = f"<a href='tg://user?id={user_id}'>Пользователь {user_id}</a>"
            
            text += f"{i}. {user_link} - {status}\n"
    else:
        text += "📭 Нет пользователей\n"
    
    # Статистика
    active_count = sum(1 for u in users if u.get("is_subscribed"))
    if users:
        text += f"\n📊 <b>Статистика:</b>\n"
        text += f"• Активных: {active_count}/{len(users)}\n"
        text += f"• Процент: {active_count/len(users)*100:.1f}%"
    
    # Клавиатура пагинации
    keyboard_buttons = []
    
    if total_pages > 1:
        row_buttons = []
        if page > 0:
            row_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"userlist_page_{page-1}"))
        
        row_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="current_page"))
        
        if page < total_pages - 1:
            row_buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"userlist_page_{page+1}"))
        
        keyboard_buttons.append(row_buttons)
    
    keyboard_buttons.extend([
        [
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast_menu"),
            InlineKeyboardButton(text="💬 Связаться", callback_data="admin_start_chat")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="🛠️ Админ-панель", callback_data="admin_panel")
        ]
    ])
    
    return text, InlineKeyboardMarkup(inline_keyboard=keyboard_buttons), total_pages

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
                InlineKeyboardButton(text="📋 Полный список", callback_data="admin_userlist")
            ],
            [
                InlineKeyboardButton(text="📊 Детальная статистика", callback_data="admin_detailed_stats"),
                InlineKeyboardButton(text="🛠️ Админ-панель", callback_data="admin_panel")
            ],
            [
                InlineKeyboardButton(text="📋 Исключения", callback_data="admin_exceptions"),
                InlineKeyboardButton(text="💬 Связаться", callback_data="admin_start_chat")
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
        f"📋 Админов: {len(ADMIN_IDS)}\n"
        f"💬 Активных чатов: {len(active_chats)}\n\n"
        "Выберите действие:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="📋 Список", callback_data="admin_userlist")
        ],
        [
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast_menu"),
            InlineKeyboardButton(text="💬 Связаться", callback_data="admin_start_chat")
        ],
        [
            InlineKeyboardButton(text="📋 Исключения", callback_data="admin_exceptions"),
            InlineKeyboardButton(text="🔍 Поиск", callback_data="admin_search")
        ],
        [
            InlineKeyboardButton(text="🧹 Очистка", callback_data="admin_cleanup"),
            InlineKeyboardButton(text="🛠️ Утилиты", callback_data="admin_utils")
        ],
        [
            InlineKeyboardButton(text="💾 Бэкапы", callback_data="admin_backup_menu")
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

@router.callback_query(F.data.startswith("userlist_page_"))
async def userlist_page_callback(callback: types.CallbackQuery):
    """Переключение страниц списка пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    
    page = int(callback.data.split("_")[-1])
    text, keyboard, total_pages = await get_user_page(page)
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    
    await callback.answer()

@router.callback_query(F.data == "admin_userlist")
async def admin_userlist_callback(callback: types.CallbackQuery):
    """Кнопка списка пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    
    text, keyboard, _ = await get_user_page(0)
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    
    await callback.answer()

# ========== СИСТЕМА РАССЫЛКИ ==========

async def broadcast_by_language(message_or_callback, state: FSMContext, lang_filter: str = None):
    """Рассылка с фильтром по языку"""
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
    
    users = db.get_all_users()
    
    if lang_filter:
        if lang_filter == "RUS":
            filtered_users = [u for u in users if u.get("language") == "RUS"]
            lang_text = "русский"
        else:
            filtered_users = [u for u in users if u.get("language") == "ENG"]
            lang_text = "английский"
    else:
        filtered_users = users
        lang_text = "все"
    
    if not filtered_users:
        if isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.answer(f"❌ Нет пользователей с языком {lang_text}", show_alert=True)
        else:
            await message.answer(f"❌ Нет пользователей с языком {lang_text}")
        return
    
    if isinstance(message_or_callback, types.CallbackQuery):
        msg = await message.answer(
            f"📢 <b>Рассылка ({lang_text} язык)</b>\n\n"
            f"👥 Получателей: {len(filtered_users)}\n"
            f"✅ Активных: {sum(1 for u in filtered_users if u.get('is_subscribed'))}\n\n"
            f"<b>Отправьте сообщение для рассылки:</b>\n"
            f"(текст, фото, видео, документ)\n\n"
            f"❌ Для отмены отправьте /cancel",
            parse_mode="HTML"
        )
    else:
        msg = message
    
    await state.update_data(
        broadcast_admin_id=user_id,
        broadcast_start_time=datetime.now().strftime("%H:%M:%S"),
        broadcast_filter_lang=lang_filter,
        broadcast_users=filtered_users
    )
    
    await state.set_state(BroadcastStates.waiting_for_message)

@router.callback_query(F.data == "admin_broadcast_menu")
async def broadcast_menu_callback(callback: types.CallbackQuery):
    """Меню выбора рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русским", callback_data="admin_broadcast_rus"),
            InlineKeyboardButton(text="🇺🇸 Английским", callback_data="admin_broadcast_eng")
        ],
        [
            InlineKeyboardButton(text="🌍 Всем", callback_data="admin_broadcast_all")
        ],
        [
            InlineKeyboardButton(text="🛠️ Админ-панель", callback_data="admin_panel")
        ]
    ])
    
    await callback.message.edit_text(
        "📢 <b>Выберите тип рассылки:</b>\n\n"
        "🇷🇺 <b>Русским</b> - только пользователям с русским языком\n"
        "🇺🇸 <b>Английским</b> - только пользователям с английским языком\n"
        "🌍 <b>Всем</b> - всем пользователям независимо от языка",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "admin_broadcast_rus")
async def broadcast_rus_callback(callback: types.CallbackQuery, state: FSMContext):
    """Рассылка только на русском"""
    await broadcast_by_language(callback, state, "RUS")
    await callback.answer()

@router.callback_query(F.data == "admin_broadcast_eng")
async def broadcast_eng_callback(callback: types.CallbackQuery, state: FSMContext):
    """Рассылка только на английском"""
    await broadcast_by_language(callback, state, "ENG")
    await callback.answer()

@router.callback_query(F.data == "admin_broadcast_all")
async def broadcast_all_callback(callback: types.CallbackQuery, state: FSMContext):
    """Рассылка всем"""
    await broadcast_by_language(callback, state)
    await callback.answer()

@router.message(Command("cancel"))
async def cancel_operation(message: Message, state: FSMContext):
    """Отмена любой операции"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора")
        return
    
    current_state = await state.get_state()
    
    if current_state is None:
        await message.answer("❌ Нет активных операций для отмены")
        return
    
    if "BroadcastStates" in str(current_state):
        await state.clear()
        await message.answer("🚫 Рассылка отменена")
    elif "ChatStates" in str(current_state):
        await state.clear()
        await message.answer("🚫 Чат отменен")
    elif "ExceptionStates" in str(current_state):
        await state.clear()
        await message.answer("🚫 Операция с исключениями отменена")
    else:
        await state.clear()
        await message.answer("🚫 Операция отменена")

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
    
    # Получаем пользователей для рассылки
    users = data.get("broadcast_users", [])
    
    if not users:
        await message.answer("❌ Нет пользователей для рассылки")
        await state.clear()
        return
    
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
    users = data.get("broadcast_users", [])
    
    if callback.from_user.id != admin_id:
        await callback.answer("❌ Вы не инициировали рассылку", show_alert=True)
        return
    
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

# ========== СИСТЕМА ИСКЛЮЧЕНИЙ (РАБОЧАЯ) ==========

@router.callback_query(F.data == "admin_exceptions")
async def admin_exceptions_callback(callback: types.CallbackQuery):
    """Управление исключениями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    
    exceptions = db.get_exceptions() if hasattr(db, 'get_exceptions') else []
    
    text = "📋 <b>Управление исключениями</b>\n\n"
    
    if not exceptions:
        text += "📭 Нет пользователей в списке исключений."
    else:
        text += f"👥 Всего исключений: {len(exceptions)}\n\n"
        
        for i, exc in enumerate(exceptions[:10], 1):
            user_id = exc.get("user_id", "N/A")
            username = exc.get("username", "без username")
            
            text += f"{i}. @{username} (ID: {user_id})\n"
        
        if len(exceptions) > 10:
            text += f"\n... и еще {len(exceptions) - 10}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить", callback_data="exc_add_start"),
            InlineKeyboardButton(text="➖ Удалить", callback_data="exc_remove_start")
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_exceptions"),
            InlineKeyboardButton(text="🛠️ Админ-панель", callback_data="admin_panel")
        ]
    ])
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    
    await callback.answer()


@router.callback_query(F.data == "exc_add_start")
async def exc_add_start_callback(callback: types.CallbackQuery, state: FSMContext):
    """Начало добавления исключения"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    
    text = (
        "➕ <b>Добавление исключения</b>\n\n"
        "Введите @username или ID пользователя:\n\n"
        "📝 <b>Примеры:</b>\n"
        "• @sakyrbaevnaa\n"
        "• 1012045768\n\n"
        "❌ Для отмены отправьте /cancel"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_exceptions")]
    ])
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    
    # Устанавливаем состояние и сохраняем действие
    await state.set_state(ExceptionStates.waiting_for_user_input)
    await state.update_data(action="add", admin_id=callback.from_user.id)
    
    await callback.answer()


@router.callback_query(F.data == "exc_remove_start")
async def exc_remove_start_callback(callback: types.CallbackQuery, state: FSMContext):
    """Начало удаления исключения"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    
    exceptions = db.get_exceptions() if hasattr(db, 'get_exceptions') else []
    
    if not exceptions:
        text = "📭 Нет исключений для удаления"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_exceptions")]
        ])
        
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        except:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
        
        await callback.answer()
        return
    
    text = (
        "➖ <b>Удаление исключения</b>\n\n"
        "Введите @username или ID пользователя:\n\n"
        "📝 <b>Примеры:</b>\n"
        "• @sakyrbaevnaa\n"
        "• 1012045768\n\n"
        "❌ Для отмены отправьте /cancel"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_exceptions")]
    ])
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    
    # Устанавливаем состояние и сохраняем действие
    await state.set_state(ExceptionStates.waiting_for_user_input)
    await state.update_data(action="remove", admin_id=callback.from_user.id)
    
    await callback.answer()


@router.message(ExceptionStates.waiting_for_user_input)
async def process_exception_input(message: Message, state: FSMContext):
    """Обработка ввода для исключений"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    data = await state.get_data()
    action = data.get("action")
    admin_id = data.get("admin_id")
    
    # Проверяем, что это тот же админ
    if message.from_user.id != admin_id:
        await message.answer("❌ Вы не инициировали эту операцию")
        await state.clear()
        return
    
    input_text = message.text.strip()
    
    # Проверка на отмену
    if input_text == "/cancel":
        await message.answer("🚫 Операция отменена")
        await state.clear()
        return
    
    logger.info(f"🔍 Обработка исключения: действие={action}, ввод={input_text}")
    
    # Ищем пользователя
    user = None
    
    # Поиск по @username
    if input_text.startswith('@'):
        username = input_text[1:].lower()
        logger.info(f"Поиск по username: {username}")
        
        users = db.get_all_users()
        for u in users:
            if u.get("username") and u["username"].lower() == username:
                user = u
                logger.info(f"Найден пользователь: @{u['username']}")
                break
        
        if not user:
            await message.answer(f"❌ Пользователь @{username} не найден.")
            return
    
    # Поиск по ID
    elif input_text.isdigit():
        user_id = int(input_text)
        logger.info(f"Поиск по ID: {user_id}")
        
        user = db.get_user(user_id)
        
        if not user:
            await message.answer(f"❌ Пользователь с ID {user_id} не найден.")
            return
        else:
            logger.info(f"Найден пользователь: ID {user_id}")
    
    else:
        await message.answer("❌ Неверный формат. Введите @username или ID пользователя.")
        return
    
    # Выполняем действие
    user_id = user["user_id"]
    username = user.get("username", "без username")
    
    if action == "add":
        # Проверяем, есть ли уже исключение
        if db.is_exception(user_id):
            await message.answer(f"⚠️ Пользователь @{username} уже в исключениях!")
        else:
            # Добавляем исключение
            success = db.add_exception(user_id, message.from_user.id)
            if success:
                await message.answer(f"✅ Пользователь @{username} добавлен в исключения!")
            else:
                await message.answer("❌ Ошибка при добавлении в исключения")
    
    elif action == "remove":
        # Удаляем исключение
        success = db.remove_exception(user_id)
        if success:
            await message.answer(f"✅ Пользователь @{username} удален из исключений!")
        else:
            await message.answer(f"❌ Пользователь @{username} не найден в исключениях")
    
    # Очищаем состояние
    await state.clear()
    
    # Возвращаемся к списку исключений
    await admin_exceptions_callback(types.CallbackQuery(
        id="return_to_exceptions",
        from_user=message.from_user,
        chat_instance="return",
        message=message,
        data="admin_exceptions"
    ))

# ========== СИСТЕМА ДВУСТОРОННЕЙ СВЯЗИ ==========

@router.callback_query(F.data == "admin_start_chat")
async def start_chat_with_user(callback: types.CallbackQuery, state: FSMContext):
    """Начало чата с пользователем"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    
    await callback.message.answer(
        "💬 <b>Выберите пользователя для связи:</b>\n\n"
        "Отправьте:\n"
        "• Номер пользователя из списка (например, 15)\n"
        "• @username пользователя\n"
        "• Или ID пользователя\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(ChatStates.waiting_for_user)
    await callback.answer()

@router.message(ChatStates.waiting_for_user)
async def process_user_selection(message: Message, state: FSMContext):
    """Обработка выбора пользователя"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    input_text = message.text.strip()
    
    # Проверка на отмену
    if input_text == "/cancel":
        await message.answer("🚫 Операция отменена")
        await state.clear()
        return
    
    # Ищем пользователя
    user = None
    users = db.get_all_users()
    
    # По номеру
    if input_text.isdigit() and len(input_text) < 6:  # Номер из списка
        try:
            idx = int(input_text) - 1
            if 0 <= idx < len(users):
                user = users[idx]
        except:
            pass
    
    # По @username
    elif input_text.startswith('@'):
        username = input_text[1:]
        for u in users:
            if u.get("username") and u["username"].lower() == username.lower():
                user = u
                break
    
    # По ID (прямой ID пользователя)
    elif input_text.isdigit() and len(input_text) >= 6:
        user_id = int(input_text)
        user = db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Пользователь не найден. Попробуйте еще раз или отправьте /cancel")
        return
    
    user_id = user["user_id"]
    admin_id = message.from_user.id
    
    # Сохраняем активный чат
    active_chats[user_id] = admin_id
    
    # Уведомляем пользователя
    user_lang = user.get("language", "RUS")
    lang_code = "ru" if user_lang == "RUS" else "en"
    
    if lang_code == "ru":
        notification = "👤 <b>С Вами связался администратор</b>"
    else:
        notification = "👤 <b>An administrator has contacted you</b>"
    
    try:
        await message.bot.send_message(user_id, notification, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить уведомление пользователю: {e}")
        # Удаляем из активных чатов
        if user_id in active_chats:
            del active_chats[user_id]
        await state.clear()
        return
    
    # Информация для администратора
    user_info = f"ID: {user_id}"
    if user.get("username"):
        user_info += f" (@{user['username']})"
    
    await message.answer(
        f"✅ Чат начат с пользователем {user_info}\n\n"
        f"Все ваши сообщения будут пересылаться пользователю.\n"
        f"Для завершения диалога отправьте /stop\n\n"
        f"Напишите первое сообщение:"
    )
    
    await state.set_state(ChatStates.chatting)
    await state.update_data(chat_with_user=user_id)

@router.message(ChatStates.chatting)
async def forward_admin_message(message: Message, state: FSMContext):
    """Пересылка сообщений администратора пользователю"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    data = await state.get_data()
    user_id = data.get("chat_with_user")
    
    if not user_id:
        await state.clear()
        return
    
    # Проверяем, есть ли еще активный чат
    if user_id not in active_chats or active_chats[user_id] != message.from_user.id:
        await message.answer("❌ Чат с пользователем не активен или был завершен")
        await state.clear()
        return
    
    if message.text == "/stop":
        # Завершаем чат
        user = db.get_user(user_id)
        user_lang = user.get("language", "RUS") if user else "RUS"
        lang_code = "ru" if user_lang == "RUS" else "en"
        
        if lang_code == "ru":
            end_msg = "Диалог завершен администратором."
        else:
            end_msg = "Conversation ended by administrator."
        
        try:
            await message.bot.send_message(user_id, end_msg)
        except:
            pass
        
        # Удаляем из активных чатов
        if user_id in active_chats:
            del active_chats[user_id]
        
        await message.answer("✅ Диалог завершен.")
        await state.clear()
        return
    
    # Пересылаем сообщение пользователю
    try:
        await message.copy_to(user_id)
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить сообщение: {e}")
        if "Forbidden" in str(e) or "blocked" in str(e):
            # Пользователь заблокировал бота
            if user_id in active_chats:
                del active_chats[user_id]
            await state.clear()

# ========== ОБРАБОТКА СООБЩЕНИЙ ОТ ПОЛЬЗОВАТЕЛЕЙ АДМИНИСТРАТОРАМ ==========

@router.message(F.chat.type == "private")
async def handle_user_to_admin(message: Message):
    """Обработка сообщений от пользователей администратору"""
    user_id = message.from_user.id
    
    # Проверяем, не является ли отправитель администратором
    if is_admin(user_id):
        return
    
    # Проверяем, есть ли активный чат с этим пользователем
    if user_id not in active_chats:
        # Нет активного чата - игнорируем
        return
    
    admin_id = active_chats[user_id]
    
    # Проверяем команду /stop
    if message.text and message.text.strip() == "/stop":
        # Пользователь завершил чат
        try:
            user_info = f"ID: {user_id}"
            user = db.get_user(user_id)
            if user and user.get("username"):
                user_info += f" (@{user['username']})"
            
            await message.bot.send_message(
                admin_id,
                f"❌ Пользователь {user_info} завершил диалог командой /stop"
            )
        except:
            pass
        
        # Удаляем из активных чатов
        del active_chats[user_id]
        return
    
    try:
        # Получаем информацию о пользователе
        user_info = f"ID: {user_id}"
        user = db.get_user(user_id)
        if user and user.get("username"):
            user_info += f" (@{user['username']})"
        
        # Пересылаем сообщение админу
        await message.forward(admin_id)
        
        # Отправляем админу информацию о пользователе
        await message.bot.send_message(
            admin_id,
            f"📨 <b>Сообщение от пользователя:</b>\n{user_info}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")
        # Если админ заблокировал бота или чат не найден
        if "Forbidden" in str(e) or "chat not found" in str(e):
            del active_chats[user_id]

# ========== ДРУГИЕ CALLBACK ОБРАБОТЧИКИ ==========

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
        f"<b>Версия:</b> 2.0\n"
        f"<b>Ваш ID:</b> {callback.from_user.id}\n"
        f"<b>Админов:</b> {len(ADMIN_IDS)}\n"
        f"<b>Канал:</b> {Config.SOURCE_CHANNEL_ID}\n"
        f"<b>Активных чатов:</b> {len(active_chats)}\n\n"
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
    await show_admin_panel(callback)
    await callback.answer("🔄 Панель обновлена!")

@router.callback_query(F.data == "admin_detailed_stats")
async def admin_detailed_stats_callback(callback: types.CallbackQuery):
    """Детальная статистика"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    
    stats = db.get_statistics()
    exceptions = db.get_exceptions() if hasattr(db, 'get_exceptions') else []
    
    text = "📊 <b>Детальная статистика:</b>\n\n"
    text += f"👥 <b>Общая информация:</b>\n"
    text += f"• Всего пользователей: {stats['total_users']}\n"
    text += f"• Активных подписчиков: {stats['active_subscribers']}\n"
    text += f"• Исключений: {len(exceptions)}\n"
    text += f"• Активных чатов: {len(active_chats)}\n\n"
    
    text += f"🗿 <b>Настройки тотемов:</b>\n"
    text += f"• Free тотемы: {stats['free_totems']}\n"
    text += f"• Paid тотемы: {stats['paid_totems']}\n\n"
    
    text += f"🍎 <b>Популярность фруктов:</b>\n"
    if stats["fruit_stats"]:
        for fruit, count in stats["fruit_stats"].items():
            text += f"• {fruit}: {count}\n"
    else:
        text += "Нет данных\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Назад к статистике", callback_data="admin_stats")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

# ========== БЭКАПЫ (РАБОЧАЯ ВЕРСИЯ) ==========

@router.callback_query(F.data == "admin_backup_menu")
async def admin_backup_callback(callback: types.CallbackQuery):
    """Меню управления бэкапами"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    
    stats = backup_manager.get_backup_stats()
    
    text = (
        "💾 <b>Управление бэкапами базы данных</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Всего бэкапов: {stats['total_backups']}\n"
        f"• Общий размер: {stats.get('total_size_formatted', '0 байт')}\n"
    )
    
    if stats['oldest_backup']:
        text += f"• Самый старый: {stats['oldest_backup'].strftime('%d.%m.%Y %H:%M')}\n"
    if stats['newest_backup']:
        text += f"• Самый новый: {stats['newest_backup'].strftime('%d.%m.%Y %H:%M')}\n"
    
    text += "\n📁 <b>Типы файлов:</b>\n"
    for file_type, count in stats.get('backup_types', {}).items():
        if count > 0:
            text += f"• {file_type}: {count}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📥 Создать бэкап (DB)", callback_data="create_db_backup"),
            InlineKeyboardButton(text="📦 Создать бэкап (сжатый)", callback_data="create_compressed_backup")
        ],
        [
            InlineKeyboardButton(text="📄 Создать JSON бэкап", callback_data="create_json_backup"),
            InlineKeyboardButton(text="📋 Список бэкапов", callback_data="list_backups")
        ],
        [
            InlineKeyboardButton(text="🛠️ Админ-панель", callback_data="admin_panel")
        ]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("create_"))
async def create_backup_handler(callback: types.CallbackQuery):
    """Создание бэкапа - ТАК ЖЕ КАК AUTOBACKUP"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    
    backup_type = callback.data.replace("create_", "").replace("_backup", "")
    
    await callback.message.edit_text("🔄 Создаю бэкап...")
    
    if backup_type == "db":
        backup_path = backup_manager.create_backup(compress=False)
        backup_type_name = "обычный"
        file_emoji = "💾"
    elif backup_type == "compressed":
        backup_path = backup_manager.create_backup(compress=True)
        backup_type_name = "сжатый"
        file_emoji = "📦"
    elif backup_type == "json":
        backup_path = backup_manager.create_json_backup()
        backup_type_name = "JSON"
        file_emoji = "📄"
    else:
        await callback.message.edit_text("❌ Неизвестный тип бэкапа")
        return
    
    if not backup_path or not os.path.exists(backup_path):
        await callback.message.edit_text("❌ Ошибка создания бэкапа")
        return
    
    # Отправляем файл администратору - ТАК ЖЕ КАК В AUTOBACKUP
    try:
        file_size = os.path.getsize(backup_path)
        file_size_mb = file_size / (1024 * 1024)
        
        if file_size_mb > 48:  # Telegram лимит 50MB
            await callback.message.edit_text(
                f"❌ Файл слишком большой: {file_size_mb:.1f} MB\n"
                f"Лимит Telegram: 50 MB\n\n"
                f"Файл сохранен локально: {os.path.basename(backup_path)}"
            )
            return
        
        # Читаем файл и создаем BufferedInputFile - ТАК ЖЕ КАК В AUTOBACKUP
        with open(backup_path, 'rb') as file:
            file_data = file.read()
            
        input_file = types.BufferedInputFile(
            file=file_data,
            filename=os.path.basename(backup_path)
        )
        
        await callback.bot.send_document(
            chat_id=callback.from_user.id,
            document=input_file,
            caption=f"{file_emoji} {backup_type_name.capitalize()} бэкап базы данных\nРазмер: {file_size_mb:.2f} MB\nДата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        await callback.message.edit_text(f"✅ {backup_type_name.capitalize()} бэкап создан и отправлен!")
        
    except Exception as e:
        logger.error(f"Ошибка отправки бэкапа: {e}")
        await callback.message.edit_text(f"✅ Бэкап создан, но ошибка отправки: {e}")

@router.callback_query(F.data == "list_backups")
async def list_backups_handler(callback: types.CallbackQuery):
    """Показать список бэкапов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    
    backups = backup_manager.list_backups()
    
    if not backups:
        await callback.message.edit_text("📭 Нет доступных бэкапов")
        return
    
    text = "📋 <b>Список бэкапов:</b>\n\n"
    
    for i, backup in enumerate(backups[:10], 1):
        filename = backup["filename"]
        size = backup["size_formatted"]
        modified = backup["modified"].strftime("%d.%m.%Y %H:%M")
        file_type = backup["type"]
        
        # Определяем эмодзи для типа файла
        if file_type == "compressed":
            emoji = "📦"
        elif file_type == "json":
            emoji = "📄"
        elif file_type == "database":
            emoji = "💾"
        else:
            emoji = "📁"
        
        text += f"{i}. {emoji} <code>{filename}</code>\n"
        text += f"   📏 {size} | 🕐 {modified}\n\n"
    
    if len(backups) > 10:
        text += f"\n... и еще {len(backups) - 10} бэкапов"
    
    keyboard_buttons = []
    
    if backups:
        row = []
        for i in range(min(3, len(backups))):
            backup = backups[i]
            # Определяем эмодзи для кнопки
            if backup["type"] == "compressed":
                btn_emoji = "📦"
            elif backup["type"] == "json":
                btn_emoji = "📄"
            else:
                btn_emoji = "💾"
            
            row.append(
                InlineKeyboardButton(
                    text=f"{btn_emoji} {i+1}",
                    callback_data=f"send_backup_{backup['filename']}"
                )
            )
        keyboard_buttons.append(row)
    
    keyboard_buttons.extend([
        [InlineKeyboardButton(text="🔄 Обновить список", callback_data="list_backups")],
        [InlineKeyboardButton(text="📥 Создать новый", callback_data="admin_backup_menu")],
        [InlineKeyboardButton(text="🛠️ Админ-панель", callback_data="admin_panel")]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("send_backup_"))
async def send_backup_handler(callback: types.CallbackQuery):
    """Отправка конкретного бэкапа - ТАК ЖЕ КАК AUTOBACKUP"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return
    
    filename = callback.data.replace("send_backup_", "")
    backup_path = os.path.join("database_backups", filename)
    
    if not os.path.exists(backup_path):
        await callback.answer("❌ Файл не найден", show_alert=True)
        return
    
    await callback.message.edit_text(f"📤 Отправляю {filename}...")
    
    try:
        file_size = os.path.getsize(backup_path)
        file_size_mb = file_size / (1024 * 1024)
        
        if file_size_mb > 48:
            await callback.message.edit_text(
                f"❌ Файл слишком большой: {file_size_mb:.1f} MB\n"
                f"Лимит Telegram: 50 MB"
            )
            return
        
        # Определяем тип файла для эмодзи
        if filename.endswith('.gz'):
            file_emoji = "📦"
            file_type = "сжатый"
        elif filename.endswith('.json'):
            file_emoji = "📄"
            file_type = "JSON"
        else:
            file_emoji = "💾"
            file_type = "обычный"
        
        # Читаем файл и создаем BufferedInputFile - ТАК ЖЕ КАК В AUTOBACKUP
        with open(backup_path, 'rb') as file:
            file_data = file.read()
            
        input_file = types.BufferedInputFile(
            file=file_data,
            filename=filename
        )
        
        await callback.bot.send_document(
            chat_id=callback.from_user.id,
            document=input_file,
            caption=f"{file_emoji} {file_type} бэкап: {filename}\nРазмер: {file_size_mb:.2f} MB\nДата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        await callback.message.edit_text(f"✅ Бэкап {filename} отправлен!")
        
    except Exception as e:
        logger.error(f"Ошибка отправки бэкапа: {e}")
        await callback.message.edit_text(f"❌ Ошибка отправки: {e}")


@router.message(Command("backup"))
async def cmd_backup(message: Message):
    """Создание и отправка бэкапа администратору"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора")
        return
    
    await message.answer("🔄 Создаю бэкап базы данных...")
    
    # Используем ту же функцию что и в autobackup
    import shutil
    import gzip
    from datetime import datetime
    
    try:
        backup_dir = "database_backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"database_backup_{timestamp}.db.gz"
        backup_path = os.path.join(backup_dir, backup_name)
        
        with open("database.db", 'rb') as f_in:
            with gzip.open(backup_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Отправка как в autobackup
        file_size = os.path.getsize(backup_path)
        file_size_mb = file_size / (1024 * 1024)
        
        # Читаем файл и создаем BufferedInputFile
        with open(backup_path, 'rb') as file:
            file_data = file.read()
            
        input_file = types.BufferedInputFile(
            file=file_data,
            filename=backup_name
        )
        
        await message.bot.send_document(
            chat_id=message.from_user.id,
            document=input_file,
            caption=f"💾 Бэкап базы данных\nРазмер: {file_size_mb:.2f} MB\nДата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        await message.answer("✅ Бэкап создан и отправлен!")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("backup_json"))
async def cmd_backup_json(message: Message):
    """Команда создания JSON бэкапа"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора")
        return
    
    backup_path = backup_manager.create_json_backup()
    
    if not backup_path or not os.path.exists(backup_path):
        await message.answer("❌ Ошибка создания JSON бэкапа")
        return
    
    try:
        file_size = os.path.getsize(backup_path)
        file_size_mb = file_size / (1024 * 1024)
        
        # Читаем файл и создаем BufferedInputFile
        with open(backup_path, 'rb') as file:
            file_data = file.read()
            
        input_file = types.BufferedInputFile(
            file=file_data,
            filename=os.path.basename(backup_path)
        )
        
        await message.bot.send_document(
            chat_id=message.from_user.id,
            document=input_file,
            caption=f"📄 JSON бэкап базы данных\nРазмер: {file_size_mb:.2f} MB\nДата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        await message.answer("✅ JSON бэкап создан и отправлен!")
        
    except Exception as e:
        await message.answer(f"✅ JSON бэкап создан, но ошибка отправки: {e}")


@router.message(Command("backup_stats"))
async def cmd_backup_stats(message: Message):
    """Статистика по бэкапам"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора")
        return
    
    stats = backup_manager.get_backup_stats()
    
    text = (
        "📊 <b>Статистика бэкапов:</b>\n\n"
        f"• Всего бэкапов: {stats['total_backups']}\n"
        f"• Общий размер: {stats.get('total_size_formatted', '0 байт')}\n"
    )
    
    if stats['oldest_backup']:
        text += f"• Самый старый: {stats['oldest_backup'].strftime('%d.%m.%Y %H:%M')}\n"
    if stats['newest_backup']:
        text += f"• Самый новый: {stats['newest_backup'].strftime('%d.%m.%Y %H:%M')}\n"
    
    text += "\n📁 <b>Типы файлов:</b>\n"
    for file_type, count in stats.get('backup_types', {}).items():
        if count > 0:
            emoji = "📦" if file_type == "db.gz" else "📄" if file_type == "json" else "💾"
            text += f"• {emoji} {file_type}: {count}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Создать бэкап", callback_data="admin_backup_menu")],
        [InlineKeyboardButton(text="📋 Список бэкапов", callback_data="list_backups")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


# ========== ПРОСТЫЕ КОМАНДЫ ДЛЯ ТЕСТА ==========

@router.message(Command("reset_state"))
async def cmd_reset_state(message: Message, state: FSMContext):
    """Сброс состояния пользователя"""
    if not is_admin(message.from_user.id):
        return
    
    await state.clear()
    await message.answer("✅ Все состояния сброшены!")


@router.message(Command("test_exception"))
async def cmd_test_exception(message: Message):
    """Тест исключений"""
    if not is_admin(message.from_user.id):
        return
    
    user_id = 1012045768  # @sakyrbaevnaa
    is_exc = db.is_exception(user_id)
    
    await message.answer(f"🔍 Проверка исключения для {user_id}: {'✅ ЕСТЬ' if is_exc else '❌ НЕТ'}")

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
        f"Для выбора типа рассылки используйте админ-панель или команды:\n"
        f"/broadcast_rus - рассылка русским\n"
        f"/broadcast_eng - рассылка английским\n"
        f"/broadcast_all - рассылка всем",
        parse_mode="HTML"
    )

@router.message(Command("exceptions"))
async def cmd_exceptions(message: Message):
    """Команда управления исключениями"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора")
        return
    
    await admin_exceptions_callback(types.CallbackQuery(
        id="manual",
        from_user=message.from_user,
        chat_instance="manual",
        message=message,
        data="admin_exceptions"
    ))

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
        "<b>/broadcast</b> - 📢 Меню рассылки\n"
        "<b>/broadcast_rus</b> - 🇷🇺 Рассылка русским\n"
        "<b>/broadcast_eng</b> - 🇺🇸 Рассылка английским\n"
        "<b>/broadcast_all</b> - 🌍 Рассылка всем\n"
        "<b>/exceptions</b> - 📋 Управление исключениями\n"
        "<b>/active_chats</b> - 💬 Показать активные чаты\n"
        "<b>/help_admin</b> - ❓ Эта справка\n\n"
        f"<b>💬 Активных чатов:</b> {len(active_chats)}\n"
        f"<b>👑 Администраторы:</b> {len(ADMIN_IDS)}\n"
        f"<b>🔧 Версия:</b> 2.0"
    )
    
    await message.answer(help_text, parse_mode="HTML")