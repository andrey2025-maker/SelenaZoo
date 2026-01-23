from aiogram import Router, types, F
from aiogram.filters import Command, or_f
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ChatType

from database import Database
from config import Config
from utils.messages import locale_manager

router = Router()
db = Database()

# Ключевые слова для вызова настроек
KEYWORDS = [
    "еда", "food", "тотемы","тотем", "stock", "eat", "totem", "totems",
    "настройки", "settings", "уведомления", "notifications",
    "фрукты", "fruits", "fruit", "отключить", "disable", "выкл", "выключить", "off",
    "Еда", "Food", "Тотемы", "Тотем", "Stock", "Eat", "Totem", "Totems",
    "Настройки", "Settings", "Уведомления", "Notifications",
    "Фрукты", "Fruits", "Fruit", "Отключить", "Disable", "Выкл", "Выключить", "Off"
]

# Функция для получения языка пользователя (используется в group_commands.py)
def get_user_language(user_id: int) -> str:
    """Получить язык пользователя из БД"""
    user = db.get_user(user_id)
    if user and user.get("language") == "RUS":
        return "ru"
    return "en"

@router.message(
    or_f(Command("start"), *[F.text.contains(word) for word in KEYWORDS]),
    F.chat.type == ChatType.PRIVATE  # ТОЛЬКО личные сообщения
)
async def handle_settings_request(message: types.Message):
    """Обработка команды /start и ключевых слов ТОЛЬКО в личных сообщениях"""
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Добавляем пользователя в БД
    db.add_user(user_id, username)
    
    # Получаем информацию о пользователе
    user = db.get_user(user_id)
    
    # Определяем язык
    if user and user.get("language"):
        lang = user.get("language")
    else:
        # Определяем язык по сообщению
        text_lower = message.text.lower() if message.text else ""
        if any(word in text_lower for word in ["еда", "тотемы", "настройки", "уведомления", "фрукты", "отключить"]):
            lang = "RUS"
        else:
            lang = "ENG"
        db.update_user_language(user_id, lang)
    
    lang_code = "ru" if lang == "RUS" else "en"
    
    # Проверяем, запрошено ли отключение
    text_lower = message.text.lower() if message.text else ""
    if any(word in text_lower for word in ["отключить", "disable", "выкл", "выключить", "off", "Отключить", "Disable", "Выкл", "Выключить", "Off"]):
        # Отключаем все уведомления
        db.update_user_fruits(user_id, [])
        db.update_totem_settings(user_id, free_totems=False, paid_totems=False)
        
        if lang == "RUS":
            await message.answer("✅ Все уведомления отключены!")
        else:
            await message.answer("✅ All notifications disabled!")
        
        # Показываем настройки
        await show_settings_menu(message, user_id, lang, lang_code)
        return
    
    # Если это команда /start - показываем выбор языка
    if message.text and message.text.startswith('/start'):
        # Создаем клавиатуру для выбора языка
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")
        )
        
        text = (
            f"{locale_manager.get_text('ru', 'start.welcome')}\n"
            f"{locale_manager.get_text('ru', 'start.choose_language')}\n\n"
            f"{locale_manager.get_text('en', 'start.welcome')}\n"
            f"{locale_manager.get_text('en', 'start.choose_language')}"
        )
        
        await message.answer(text, reply_markup=builder.as_markup())
    else:
        # Если это ключевое слово - сразу показываем настройки
        await show_settings_menu(message, user_id, lang, lang_code)


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def ignore_in_groups(message: types.Message):
    """
    Игнорировать команды бота в группах.
    Бот реагирует только в личных сообщениях.
    """
    # Проверяем, является ли сообщение командой или ключевым словом
    if not message.text:
        return
    
    text = message.text.strip()
    
    # Проверяем команды
    if text.startswith('/'):
        # Это команда, но мы игнорируем ее в группах
        return
    
    # Проверяем ключевые слова
    text_lower = text.lower()
    is_keyword = any(word in text_lower for word in [
        "еда", "food", "тотемы", "тотем", "stock", "eat", "totem", "totems",
        "настройки", "settings", "уведомления", "notifications",
        "фрукты", "fruits", "fruit", "отключить", "disable", "выкл", "выключить", "off"
    ])
    
    if is_keyword:
        # Это ключевое слово, но мы игнорируем его в группах
        return


async def show_settings_menu(message: types.Message, user_id: int, lang: str, lang_code: str):
    """Показ меню настроек с учетом исключений"""
    from handlers.settings import get_settings_keyboard
    
    # Проверяем подписку (не игнорируем исключения для показа пользователю)
    from utils.subscription import check_user_subscription
    is_subscribed = await check_user_subscription(user_id, Config.REQUIRED_GROUP_ID, message.bot)
    
    # Проверяем, есть ли пользователь в исключениях
    is_exception = db.is_exception(user_id)
    
    # Если пользователь в исключениях, считаем его подписанным
    if is_exception:
        is_subscribed = True
    
    db.update_subscription(user_id, is_subscribed)
    
    if not is_subscribed and not is_exception:
        # Показываем сообщение о необходимости подписки
        text = locale_manager.get_text(lang_code, "subscription.require")
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text=locale_manager.get_text(lang_code, "subscription.check_button"),
                callback_data="check_subscription"
            )
        )
        await message.answer(text, reply_markup=builder.as_markup())
    else:
        # Если пользователь в исключениях, показываем особое сообщение
        if is_exception:
            if lang == "RUS":
                special_text = "✅ Вы в списке исключений и можете получать уведомления без подписки на группу."
            else:
                special_text = "✅ You are in the exceptions list and can receive notifications without group subscription."
            
            await message.answer(special_text)
        
        # Показываем настройки
        text = locale_manager.get_text(lang_code, "settings.title")
        keyboard = await get_settings_keyboard(user_id, lang_code)
        await message.answer(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("lang_"))
async def process_language(callback: types.CallbackQuery):
    """Обработка выбора языка"""
    user_id = callback.from_user.id
    lang_code = callback.data.split("_")[1]
    
    # Сохраняем выбор языка
    language = "RUS" if lang_code == "ru" else "ENG"
    db.update_user_language(user_id, language)
    
    # Показываем сообщение о необходимости подписки
    text = locale_manager.get_text(lang_code, "subscription.require")
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=locale_manager.get_text(lang_code, "subscription.check_button"),
            callback_data="check_subscription"
        )
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription(callback: types.CallbackQuery):
    """Проверка подписки пользователя"""
    from utils.subscription import check_user_subscription
    from handlers.settings import get_settings_keyboard
    
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    lang_code = "ru" if user.get("language") == "RUS" else "en"
    
    # Проверяем подписку (не игнорируем исключения для проверки)
    is_subscribed = await check_user_subscription(
        user_id, 
        Config.REQUIRED_GROUP_ID, 
        callback.bot
    )
    
    # Проверяем, есть ли пользователь в исключениях
    is_exception = db.is_exception(user_id)
    
    # Если пользователь в исключениях, считаем его подписанным
    if is_exception:
        is_subscribed = True
    
    db.update_subscription(user_id, is_subscribed)
    
    if is_subscribed:
        # Показываем меню настроек
        text = locale_manager.get_text(lang_code, "subscription.confirmed")
        
        # Если пользователь в исключениях, добавляем особое сообщение
        if is_exception:
            if lang_code == "ru":
                text += "\n\n⚠️ Вы в списке исключений и можете получать уведомления без подписки."
            else:
                text += "\n\n⚠️ You are in exceptions list and can receive notifications without subscription."
        
        keyboard = await get_settings_keyboard(user_id, lang_code)
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        # Просим подписаться
        text = locale_manager.get_text(lang_code, "subscription.not_subscribed")
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text=locale_manager.get_text(lang_code, "subscription.check_button"),
                callback_data="check_subscription"
            )
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    
    await callback.answer()