from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

from database import Database
from config import Config
from utils.messages import locale_manager

router = Router()
db = Database()

async def get_settings_keyboard(user_id: int, lang_code: str) -> InlineKeyboardMarkup:
    """Создание клавиатуры настроек с кнопкой отключения"""
    user = db.get_user(user_id)
    user_fruits = db.get_user_fruits(user_id)
    
    builder = InlineKeyboardBuilder()
    
    # Кнопка настройки еды
    food_text = locale_manager.get_text(lang_code, "settings.food_button")
    builder.row(InlineKeyboardButton(text=food_text, callback_data="settings_food"))
    
    # Кнопки тотемов
    if user:
        free_status = "✅" if user.get("free_totems", 1) else "❌"
        paid_status = "✅" if user.get("paid_totems", 1) else "❌"
    else:
        free_status = "✅"
        paid_status = "✅"

    # Статусы тотемов
    free_text = f"🗿Free {free_status}"
    paid_text = f"💎🗿 Paid {paid_status}"
    
    builder.row(
        InlineKeyboardButton(text=free_text, callback_data="toggle_free_totems"),
        InlineKeyboardButton(text=paid_text, callback_data="toggle_paid_totems")
    )
    
    # Кнопка отключения всех уведомлений
    if lang_code == "ru":
        disable_text = "🚫 Отключить все"
    else:
        disable_text = "🚫 Disable all"
    
    builder.row(InlineKeyboardButton(text=disable_text, callback_data="disable_all"))
    
    return builder.as_markup()

@router.callback_query(lambda c: c.data == "disable_all")
async def disable_all_notifications(callback: types.CallbackQuery):
    """Отключение всех уведомлений"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    lang_code = "ru" if user and user.get("language") == "RUS" else "en"
    
    # Отключаем все фрукты
    db.update_user_fruits(user_id, [])
    
    # Отключаем все тотемы
    db.update_totem_settings(user_id, free_totems=False, paid_totems=False)
    
    # Показываем сообщение об успехе
    if lang_code == "ru":
        text = "✅ Все уведомления отключены!\n\nВы не будете получать уведомления о фруктах и тотемах."
    else:
        text = "✅ All notifications disabled!\n\nYou will not receive notifications about fruits and totems."
    
    # Обновляем клавиатуру
    keyboard = await get_settings_keyboard(user_id, lang_code)
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise e
    
    await callback.answer()

@router.callback_query(lambda c: c.data == "settings_food")
async def food_settings(callback: types.CallbackQuery):
    """Настройка уведомлений о еде"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    lang_code = "ru" if user and user.get("language") == "RUS" else "en"
    user_fruits = db.get_user_fruits(user_id)
    
    builder = InlineKeyboardBuilder()
    
    # Определяем, выбран ли режим "все"
    is_all_selected = "all" in user_fruits
    
    # Кнопки для каждого фрукта
    for fruit in Config.AVAILABLE_FRUITS_EN:
        fruit_display = locale_manager.get_fruit_display(fruit, user.get("language") if user else "RUS")
        
        # Определяем статус галочки
        if is_all_selected:
            # В режиме "все" все фрукты отмечены
            status = "✅"
        else:
            # В обычном режиме проверяем каждый фрукт
            status = "✅" if fruit in user_fruits else "❌"
            
        button_text = f"{fruit_display} {status}"
        builder.row(InlineKeyboardButton(text=button_text, callback_data=f"fruit_{fruit}"))
    
    # Кнопка "Получать всё"
    select_all_text = locale_manager.get_text(lang_code, "settings.select_all")
    all_status = "✅" if is_all_selected else "❌"
    builder.row(InlineKeyboardButton(text=f"{select_all_text} {all_status}", callback_data="fruit_all"))
    
    # Кнопка отключения всех фруктов
    if lang_code == "ru":
        disable_fruits_text = "🚫 Отключить фрукты"
    else:
        disable_fruits_text = "🚫 Disable fruits"
    
    builder.row(InlineKeyboardButton(text=disable_fruits_text, callback_data="disable_fruits"))
    
    # Кнопка сохранения и возврата
    save_text = locale_manager.get_text(lang_code, "settings.save_button")
    back_text = locale_manager.get_text(lang_code, "settings.back_button")
    builder.row(
        InlineKeyboardButton(text=save_text, callback_data="save_fruits"),
        InlineKeyboardButton(text=back_text, callback_data="back_to_settings")
    )
    
    text = locale_manager.get_text(lang_code, "settings.food_selection")
    
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise e
    
    await callback.answer()

@router.callback_query(lambda c: c.data == "disable_fruits")
async def disable_fruits(callback: types.CallbackQuery):
    """Отключение всех фруктов"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    lang_code = "ru" if user and user.get("language") == "RUS" else "en"
    
    # Отключаем все фрукты
    db.update_user_fruits(user_id, [])
    
    # Обновляем клавиатуру
    await food_settings(callback)
    
    if lang_code == "ru":
        await callback.answer("✅ Все фрукты отключены")
    else:
        await callback.answer("✅ All fruits disabled")

# ... остальной код settings.py остается без изменений ...

@router.callback_query(lambda c: c.data == "save_fruits")
async def save_fruits(callback: types.CallbackQuery):
    """Сохранение выбранных фруктов"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    lang_code = "ru" if user and user.get("language") == "RUS" else "en"
    user_fruits = db.get_user_fruits(user_id)
    
    if not user_fruits:
        text = locale_manager.get_text(lang_code, "settings.no_fruits_selected")
    else:
        if "all" in user_fruits:
            # Режим "все"
            if lang_code == "ru":
                text = "✅ Настройки сохранены!\nВы будете получать уведомления о ВСЕХ фруктах."
            else:
                text = "✅ Settings saved!\nYou will receive notifications about ALL fruits."
        else:
            # Индивидуальный выбор
            fruit_list = "\n".join([
                f"- {locale_manager.get_fruit_display(fruit, user.get('language') if user else 'RUS')}"
                for fruit in user_fruits
            ])
            
            if lang_code == "ru":
                text = f"✅ Настройки сохранены!\nВы будете получать:\n{fruit_list}"
            else:
                text = f"✅ Settings saved!\nYou will receive:\n{fruit_list}"
    
    keyboard = await get_settings_keyboard(user_id, lang_code)
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise e
    
    await callback.answer()

@router.callback_query(lambda c: c.data == "back_to_settings")
async def back_to_settings(callback: types.CallbackQuery):
    """Возврат к основным настройкам"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    lang_code = "ru" if user and user.get("language") == "RUS" else "en"
    
    text = locale_manager.get_text(lang_code, "settings.title")
    keyboard = await get_settings_keyboard(user_id, lang_code)
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise e
    
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("toggle_"))
async def toggle_totem(callback: types.CallbackQuery):
    """Переключение настроек тотемов"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    totem_type = callback.data.split("_")[1]  # free или paid
    
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
    
    # Получаем текущее значение
    current_value = user.get(f"{totem_type}_totems", 1)
    
    # Инвертируем значение
    new_value = not bool(current_value)
    
    # Обновляем в БД
    if totem_type == "free":
        db.update_totem_settings(user_id, free_totems=new_value)
    else:
        db.update_totem_settings(user_id, paid_totems=new_value)
    
    # Обновляем клавиатуру
    lang_code = "ru" if user.get("language") == "RUS" else "en"
    text = locale_manager.get_text(lang_code, "settings.title")
    keyboard = await get_settings_keyboard(user_id, lang_code)
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise e
    
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("fruit_"))
async def toggle_fruit(callback: types.CallbackQuery):
    """Переключение выбора фрукта"""
    user_id = callback.from_user.id
    fruit_name = callback.data.split("_", 1)[1]
    user_fruits = db.get_user_fruits(user_id)
    
    if fruit_name == "all":
        if "all" in user_fruits:
            # Если уже выбрано "все", очищаем выбор
            db.update_user_fruits(user_id, [])
        else:
            # Выбираем все фрукты
            db.update_user_fruits(user_id, ["all"])
    else:
        if "all" in user_fruits:
            # Если был выбран "все", переключаемся на индивидуальный выбор
            # Убираем "all" и добавляем все фрукты КРОМЕ текущего
            all_fruits = Config.AVAILABLE_FRUITS_EN.copy()
            if fruit_name in all_fruits:
                all_fruits.remove(fruit_name)
            db.update_user_fruits(user_id, all_fruits)
        else:
            # Обычный выбор/снятие выбора
            if fruit_name in user_fruits:
                # Убираем фрукт из выбранных
                user_fruits.remove(fruit_name)
            else:
                # Добавляем фрукт
                user_fruits.append(fruit_name)
            
            # Проверяем, выбраны ли ВСЕ фрукты
            all_selected = all(fruit in user_fruits for fruit in Config.AVAILABLE_FRUITS_EN)
            if all_selected:
                # Если выбраны все, переключаемся на режим "все"
                db.update_user_fruits(user_id, ["all"])
            else:
                db.update_user_fruits(user_id, user_fruits)
    
    # Обновляем клавиатуру
    await food_settings(callback)