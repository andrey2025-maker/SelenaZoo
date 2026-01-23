"""
handlers/publish.py - Система публикации сообщений в группу
"""

from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import re
import logging
import asyncio

from config import Config
from database import Database

router = Router()
db = Database()
logger = logging.getLogger(__name__)

# Проверка админа (импортируем из admin.py)
def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    ADMIN_IDS = [Config.ADMIN_ID]  # Используем ID из конфига
    return user_id in ADMIN_IDS

class PublishStates(StatesGroup):
    waiting_for_publication = State()

@router.message(Command("publish"), F.chat.type == "private")
async def cmd_publish(message: Message, state: FSMContext):
    """Команда публикации в группу"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора")
        return
    
    text = (
        "📢 <b>Публикация в группу</b>\n\n"
        f"Группа: <code>{Config.PUBLISH_GROUP_ID}</code>\n\n"
        "Отправьте сообщение для публикации:\n"
        "(текст, фото, видео, документ, голосовое)\n\n"
        "Для ответа на конкретное сообщение пришлите его ссылку:\n"
        "<code>https://t.me/c/XXXXXXX/12345</code>\n\n"
        "❌ Для отмены отправьте /cancel"
    )
    
    await message.answer(text, parse_mode="HTML")
    await state.set_state(PublishStates.waiting_for_publication)

@router.message(F.chat.type == "private", PublishStates.waiting_for_publication)
async def process_publication(message: Message, state: FSMContext, command: CommandObject = None):
    """Обработка сообщения для публикации"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    # Проверка на отмену
    if message.text and message.text.strip() == "/cancel":
        await message.answer("🚫 Публикация отменена")
        await state.clear()
        return
    
    # Проверяем, является ли сообщение ссылкой на сообщение в группе
    if message.text and "https://t.me/c/" in message.text:
        # Парсим ссылку на сообщение
        await handle_message_link(message, state)
        return
    
    # Обычная публикация
    try:
        # Публикуем в группу
        published_message = await message.copy_to(Config.PUBLISH_GROUP_ID)
        
        # Подтверждение админу
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Перейти к сообщению",
                    url=f"https://t.me/c/{str(Config.PUBLISH_GROUP_ID)[4:]}/{published_message.message_id}"
                )
            ]
        ])
        
        await message.answer(
            "✅ Сообщение опубликовано в группу!",
            reply_markup=keyboard
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка публикации: {e}")
        await message.answer(f"❌ Ошибка публикации: {e}")
        await state.clear()

async def handle_message_link(message: Message, state: FSMContext):
    """Обработка ссылки на сообщение и ответ на него"""
    text = message.text.strip()
    
    # Парсим ссылку формата: https://t.me/c/1234567890/123
    # или: https://t.me/c/1234567890/123?thread=456
    pattern = r'https://t\.me/c/(\d+)/(\d+)(?:\?thread=(\d+))?'
    match = re.search(pattern, text)
    
    if not match:
        await message.answer("❌ Неверный формат ссылки. Пример:\n"
                           "https://t.me/c/1234567890/123")
        return
    
    chat_id_part = match.group(1)
    message_id = int(match.group(2))
    
    # Формируем полный ID чата (добавляем -100 в начало)
    full_chat_id = int(f"-100{chat_id_part}")
    
    await state.update_data(
        reply_chat_id=full_chat_id,
        reply_message_id=message_id
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ответить на сообщение", callback_data="confirm_reply"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_reply")
        ]
    ])
    
    await message.answer(
        f"📎 <b>Найдено сообщение для ответа:</b>\n\n"
        f"Чат ID: <code>{full_chat_id}</code>\n"
        f"Сообщение ID: <code>{message_id}</code>\n\n"
        f"Теперь отправьте текст для ответа:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "confirm_reply")
async def confirm_reply(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение ответа на сообщение"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав")
        return
    
    await callback.message.edit_text(
        "📝 Отправьте текст для ответа на сообщение:\n"
        "(или отправьте /cancel для отмены)"
    )
    await callback.answer()

@router.callback_query(F.data == "cancel_reply")
async def cancel_reply(callback: types.CallbackQuery, state: FSMContext):
    """Отмена ответа на сообщение"""
    await state.clear()
    await callback.message.edit_text("🚫 Ответ отменен")
    await callback.answer()

@router.message(PublishStates.waiting_for_publication, F.text)
async def process_reply_text(message: Message, state: FSMContext):
    """Обработка текста для ответа на сообщение"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    data = await state.get_data()
    chat_id = data.get("reply_chat_id")
    reply_to_id = data.get("reply_message_id")
    
    if not chat_id or not reply_to_id:
        await message.answer("❌ Ошибка: данные о сообщении не найдены")
        await state.clear()
        return
    
    try:
        # Отправляем ответ на сообщение
        sent_message = await message.bot.send_message(
            chat_id=chat_id,
            text=message.text,
            reply_to_message_id=reply_to_id
        )
        
        # Подтверждение админу
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Перейти к ответу",
                    url=f"https://t.me/c/{str(chat_id)[4:]}/{sent_message.message_id}"
                )
            ]
        ])
        
        await message.answer(
            f"✅ Ответ отправлен!\n\n"
            f"💬 Текст: {message.text[:100]}...\n"
            f"📎 Ответ на сообщение: {reply_to_id}",
            reply_markup=keyboard
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка отправки ответа: {e}")
        await message.answer(f"❌ Ошибка отправки ответа: {e}")
        await state.clear()

@router.message(Command("group_id"), F.chat.type == "private")
async def cmd_group_id(message: Message):
    """Получение ID группы"""
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        f"📋 <b>ID групп:</b>\n\n"
        f"• Группа для проверки подписки: <code>{Config.REQUIRED_GROUP_ID}</code>\n"
        f"• Группа для публикации: <code>{Config.PUBLISH_GROUP_ID}</code>\n\n"
        f"<b>Как получить ссылку на сообщение:</b>\n"
        f"1. В мобильном приложении: нажмите на сообщение → Поделиться → Копировать ссылку\n"
        f"2. В веб-версии: нажмите на дату сообщения → Копировать ссылку",
        parse_mode="HTML"
    )