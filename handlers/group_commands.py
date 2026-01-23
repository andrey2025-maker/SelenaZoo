"""
group_commands.py - Команды для работы в группах и ЛС
"""

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
import re
import logging
from datetime import datetime
from database import Database

router = Router()
db = Database()
logger = logging.getLogger(__name__)

# ========== ФУНКЦИЯ ФОРМАТИРОВАНИЯ ЧИСЕЛ ==========
def format_number(number: int) -> str:
    """Форматирует число с пробелами каждые 3 разряда"""
    return f"{number:,}".replace(",", " ")

# ========== ТЕКСТЫ НА РУССКОМ И АНГЛИЙСКОМ ==========
TEXTS = {
    "ru": {
        "calculator_title": "🧮 <b>Калькулятор мутаций</b>",
        "number": "<b>Число:</b>",
        "choose_mutation": "<b>Выберите мутацию:</b>",
        "another_calc": "🔢 Еще расчет",
        "results_for": "🧮 <b>Результаты для</b>",
        "mutation": "<b>Мутация:</b>",
        "new_calc_title": "🔢 <b>Новый расчет мутаций</b>",
        "new_calc_text": "Отправьте число с восклицательным знаком:",
        "or_number": "Или просто число:",
        "enter_new_number": "Введите новое число",
        "help_title": "🧮 <b>Калькулятор мутаций Build a Zoo</b>",
        "how_to_use": "<b>📱 Как использовать:</b>",
        "how_to_steps": [
            "1. Напишите <code>!число</code> (например: !36455)",
            "2. Или просто <code>число</code> (в личных сообщениях)",
            "3. Выберите мутацию из кнопок",
            "4. Получите расчет для всех 4 уровней"
        ],
        "examples": "<b>📊 Примеры:</b>",
        "example_commands": ["• <code>!1000</code>", "• <code>!50000</code>", "• <code>!123456</code>"],
        "available_mutations": "🎯 <b>Доступные мутации:</b>",
        "mutations": {
            "⚪️": "Обычная (+100%/+200%/+300%/+400%)",
            "🟡": "Золотая (+50%/+75%/+100%/+125%)",
            "💎": "Алмазная (+40%/+60%/+80%/+100%)",
            "⚡️": "Электрическая (+25%/+37.5%/+50%/+62.5%)",
            "🔥": "Огненная (+20%/+30%/+40%/+50%)",
            "🦖": "Юрская (+16.67%/+25%/+33.33%/+41.67%)",
            "❄️": "Снежная (+16.67%/+25%/+33.33%/+41.67%)",
            "🎃": "Хэллуин (+15.38%/+23.08%/+30.78%/+38.46%)",
            "🦃": "Благодарения (+14.81%/+22.22%/+29.63%/+37.04%)",
            "🎄": "Рождество (+13.33%/+20%/+26.67%/+33.33%)"
        },
        "levels": "<b>📈 Уровни:</b>",
        "levels_text": "💨 Буря → 🌀 Аврора → 🌋 Вулкан → 🪯 Админ",
        "pong": "🏓 PONG!",
        "time": "🕐 Время:",
        "chat": "💬 Чат:",
        "sender": "👤 Отправитель:",
        "calculator_works": "✅ Калькулятор мутаций работает!"
    },
    "en": {
        "calculator_title": "🧮 <b>Mutation Calculator</b>",
        "number": "<b>Number:</b>",
        "choose_mutation": "<b>Choose mutation:</b>",
        "another_calc": "🔢 Another calculation",
        "results_for": "🧮 <b>Results for</b>",
        "mutation": "<b>Mutation:</b>",
        "new_calc_title": "🔢 <b>New mutation calculation</b>",
        "new_calc_text": "Send a number with an exclamation mark:",
        "or_number": "Or just a number:",
        "enter_new_number": "Enter new number",
        "help_title": "🧮 <b>Build a Zoo Mutation Calculator</b>",
        "how_to_use": "<b>📱 How to use:</b>",
        "how_to_steps": [
            "1. Write <code>!number</code> (for example: !36455)",
            "2. Or just <code>number</code> (in private messages)",
            "3. Choose mutation from buttons",
            "4. Get calculation for all 4 levels"
        ],
        "examples": "<b>📊 Examples:</b>",
        "example_commands": ["• <code>!1000</code>", "• <code>!50000</code>", "• <code>!123456</code>"],
        "available_mutations": "🎯 <b>Available mutations:</b>",
        "mutations": {
            "⚪️": "Normal (+100%/+200%/+300%/+400%)",
            "🟡": "Golden (+50%/+75%/+100%/+125%)",
            "💎": "Diamond (+40%/+60%/+80%/+100%)",
            "⚡️": "Electric (+25%/+37.5%/+50%/+62.5%)",
            "🔥": "Fire (+20%/+30%/+40%/+50%)",
            "🦖": "Jurassic (+16.67%/+25%/+33.33%/+41.67%)",
            "❄️": "Snow (+16.67%/+25%/+33.33%/+41.67%)",
            "🎃": "Halloween (+15.38%/+23.08%/+30.78%/+38.46%)",
            "🦃": "Thanksgiving (+14.81%/+22.22%/+29.63%/+37.04%)",
            "🎄": "Christmas (+13.33%/+20%/+26.67%/+33.33%)"
        },
        "levels": "<b>📈 Levels:</b>",
        "levels_text": "💨 Storm → 🌀 Aurora → 🌋 Volcano → 🪯 Admin",
        "pong": "🏓 PONG!",
        "time": "🕐 Time:",
        "chat": "💬 Chat:",
        "sender": "👤 Sender:",
        "calculator_works": "✅ Mutation calculator works!"
    }
}

# ========== МУТАЦИИ И ИХ ПРОЦЕНТЫ (остается без изменений) ==========
MUTATIONS = {
    "⚪️": {
        "name_ru": "Обычная",
        "name_en": "Normal",
        "percentages": [100, 200, 300, 400],
        "names_ru": ["Буря", "Аврора", "Вулкан", "Админ"],
        "names_en": ["Storm", "Aurora", "Volcano", "Admin"]
    },
    "🟡": {
        "name_ru": "Золотая",
        "name_en": "Golden", 
        "percentages": [50, 75, 100, 125],
        "names_ru": ["Буря", "Аврора", "Вулкан", "Админ"],
        "names_en": ["Storm", "Aurora", "Volcano", "Admin"]
    },
    "💎": {
        "name_ru": "Алмазная",
        "name_en": "Diamond",
        "percentages": [40, 60, 80, 100],
        "names_ru": ["Буря", "Аврора", "Вулкан", "Админ"],
        "names_en": ["Storm", "Aurora", "Volcano", "Admin"]
    },
    "⚡️": {
        "name_ru": "Электрическая",
        "name_en": "Electric",
        "percentages": [25, 37.5, 50, 62.5],
        "names_ru": ["Буря", "Аврора", "Вулкан", "Админ"],
        "names_en": ["Storm", "Aurora", "Volcano", "Admin"]
    },
    "🔥": {
        "name_ru": "Огненная",
        "name_en": "Fire",
        "percentages": [20, 30, 40, 50],
        "names_ru": ["Буря", "Аврора", "Вулкан", "Админ"],
        "names_en": ["Storm", "Aurora", "Volcano", "Admin"]
    },
    "🦖": {
        "name_ru": "Юрская",
        "name_en": "Jurassic",
        "percentages": [16.67, 25, 33.33, 41.67],
        "names_ru": ["Буря", "Аврора", "Вулкан", "Админ"],
        "names_en": ["Storm", "Aurora", "Volcano", "Admin"]
    },
    "❄️": {
        "name_ru": "Снежная",
        "name_en": "Snow",
        "percentages": [16.67, 25, 33.33, 41.67],
        "names_ru": ["Буря", "Аврора", "Вулкан", "Админ"],
        "names_en": ["Storm", "Aurora", "Volcano", "Admin"]
    },
    "🎃": {
        "name_ru": "Хэллуин",
        "name_en": "Halloween",
        "percentages": [15.38, 23.08, 30.78, 38.46],
        "names_ru": ["Буря", "Аврора", "Вулкан", "Админ"],
        "names_en": ["Storm", "Aurora", "Volcano", "Admin"]
    },
    "🦃": {
        "name_ru": "Благодарения",
        "name_en": "Thanksgiving",
        "percentages": [14.81, 22.22, 29.63, 37.04],
        "names_ru": ["Буря", "Аврора", "Вулкан", "Админ"],
        "names_en": ["Storm", "Aurora", "Volcano", "Admin"]
    },
    "🎄": {
        "name_ru": "Рождество",
        "name_en": "Christmas",
        "percentages": [13.33, 20, 26.67, 33.33],
        "names_ru": ["Буря", "Аврора", "Вулкан", "Админ"],
        "names_en": ["Storm", "Aurora", "Volcano", "Admin"]
    }
}

# ========== ЭМОДЗИ ДЛЯ РЕЗУЛЬТАТОВ (остается без изменений) ==========
RESULT_EMOJIS = {
    "Буря": "💨", "Storm": "💨",
    "Аврора": "🌀", "Aurora": "🌀",
    "Вулкан": "🌋", "Volcano": "🌋",
    "Админ": "🪯", "Admin": "🪯"
}

# ========== ПОЛУЧЕНИЕ ЯЗЫКА ПОЛЬЗОВАТЕЛЯ ==========
def get_user_language(user_id: int) -> str:
    """Получить язык пользователя из БД"""
    user = db.get_user(user_id)
    if user and user.get("language") == "RUS":
        return "ru"
    return "en"

# ========== СОЗДАНИЕ КЛАВИАТУРЫ С ЯЗЫКОМ ==========
def get_mutation_keyboard(number: int, lang: str = "ru", in_private: bool = False) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора мутации с учетом языка"""
    keyboard = []
    row = []
    
    for i, (emoji, data) in enumerate(MUTATIONS.items(), 1):
        mutation_name = data[f"name_{lang}"] if lang == "ru" else data[f"name_en"]
        row.append(
            InlineKeyboardButton(
                text=f"{emoji} {mutation_name}",
                callback_data=f"mut_{emoji}_{number}_{lang}"
            )
        )
        
        # 2 кнопки в ряду
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    # Добавляем кнопку для быстрых расчетов в ЛС
    if in_private:
        keyboard.append([
            InlineKeyboardButton(
                text=TEXTS[lang]["another_calc"], 
                callback_data=f"calc_another_{lang}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ========== РАСЧЕТ МУТАЦИЙ С ЯЗЫКОМ ==========
def calculate_mutations(number: int, emoji: str = "⚪️", lang: str = "ru") -> str:
    """Расчет всех мутаций для числа с учетом языка"""
    if emoji not in MUTATIONS:
        emoji = "⚪️"
    
    mutation = MUTATIONS[emoji]
    formatted_number = format_number(number)
    
    # Получаем тексты на нужном языке
    texts = TEXTS[lang]
    
    # Формируем результат
    result_text = f"{texts['results_for']} {formatted_number}\n\n"
    mutation_name = mutation[f"name_{lang}"] if lang == "ru" else mutation[f"name_en"]
    result_text += f"{texts['mutation']} {emoji} {mutation_name}\n\n"
    
    for i, percentage in enumerate(mutation["percentages"]):
        result = number + (number * percentage / 100)
        
        # Получаем название уровня на нужном языке
        level_name = mutation[f"names_{lang}"][i] if lang == "ru" else mutation[f"names_en"][i]
        emoji_result = RESULT_EMOJIS.get(level_name, "⭐")
        formatted_result = format_number(int(result))
        
        result_text += f"{emoji_result}<b>{level_name}:</b> {formatted_result} (+{percentage}%)\n"
    
    return result_text

# ========== ОБРАБОТКА КОМАНД С ! В ГРУППАХ И ЛС ==========

@router.message(F.text.regexp(r'^!\d+$'))
async def handle_exclamation_command(message: Message):
    """Обработка команд с ! в группах и личных сообщениях"""
    text = message.text.strip()
    logger.info(f"🔧 Обработка команды с !: '{text}' в чате {message.chat.type}")
    
    # Проверяем формат !число
    match = re.match(r'^!(\d+)$', text)
    if not match:
        return
    
    number = int(match.group(1))
    
    # Получаем язык пользователя (только для ЛС, в группах используем русский)
    if message.chat.type == "private":
        lang = get_user_language(message.from_user.id)
    else:
        lang = "ru"  # В группах всегда русский
    
    logger.info(f"✅ Формат правильный! Число: {number}, Язык: {lang}")
    
    # Определяем, в ЛС мы или в группе
    in_private = message.chat.type == "private"
    
    # Создаем клавиатуру
    keyboard = get_mutation_keyboard(number, lang, in_private)
    texts = TEXTS[lang]
    
    # Отправляем сообщение с клавиатурой
    try:
        if in_private:
            # В личных сообщениях - отправляем новое сообщение
            sent_message = await message.answer(
                f"{texts['calculator_title']}\n\n"
                f"{texts['number']} {format_number(number)}\n"
                f"{texts['choose_mutation']}",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            # В группах - отвечаем на сообщение
            sent_message = await message.reply(
                f"{texts['calculator_title']}\n\n"
                f"{texts['number']} {format_number(number)}\n"
                f"{texts['choose_mutation']}",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        
        logger.info(f"✅ Ответ успешно отправлен! ID сообщения: {sent_message.message_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {type(e).__name__}: {str(e)}")
        
        # Резервный вариант - простой ответ
        try:
            result_text = calculate_mutations(number, lang=lang)
            if in_private:
                await message.answer(result_text, parse_mode=ParseMode.HTML)
            else:
                await message.reply(result_text, parse_mode=ParseMode.HTML)
            logger.info("✅ Простой ответ отправлен")
        except Exception as e2:
            logger.error(f"❌ Ошибка отправки простого ответа: {e2}")

# ========== УДАЛИМ ОБРАБОТКУ ПРОСТЫХ ЧИСЕЛ В ЛС ==========
# Удаляем старый обработчик @router.message(F.chat.type == "private", F.text.regexp(r'^\d+$'))

# ========== ОБРАБОТКА ВЫБОРА МУТАЦИИ (С ЯЗЫКОМ) ==========

@router.callback_query(F.data.startswith("mut_"))
async def handle_mutation_selection(callback: types.CallbackQuery):
    """Обработка выбора мутации из инлайн-клавиатуры с языком"""
    logger.info(f"🔘 Нажата кнопка: {callback.data}")
    
    # Парсим данные: mut_⚪️_36455_ru
    parts = callback.data.split("_")
    if len(parts) != 4:
        logger.error(f"❌ Неправильный формат callback: {callback.data}")
        await callback.answer("❌ Ошибка данных")
        return
    
    emoji = parts[1]
    number = int(parts[2])
    lang = parts[3]
    
    if emoji not in MUTATIONS:
        logger.error(f"❌ Мутация не найдена: {emoji}")
        await callback.answer("❌ Мутация не найдена")
        return
    
    mutation = MUTATIONS[emoji]
    mutation_name = mutation[f"name_{lang}"] if lang == "ru" else mutation[f"name_en"]
    logger.info(f"✅ Выбрана мутация: {mutation_name} для числа {number}, язык: {lang}")
    
    # Формируем результат с форматированием
    result_text = calculate_mutations(number, emoji, lang)
    
    # Отправляем результат
    try:
        await callback.message.edit_text(
            result_text,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"✅ Результат обновлен для мутации {mutation_name}")
        answer_text = "✅ Расчет завершен" if lang == "ru" else "✅ Calculation completed"
        await callback.answer(answer_text)
    except Exception as e:
        logger.error(f"❌ Ошибка обновления сообщения: {type(e).__name__}: {str(e)}")
        # Попробуем отправить новое сообщение
        try:
            await callback.message.answer(result_text, parse_mode=ParseMode.HTML)
            answer_text = "✅ Результат отправлен в новом сообщении" if lang == "ru" else "✅ Result sent in new message"
            await callback.answer(answer_text)
        except Exception as e2:
            logger.error(f"❌ Не удалось отправить результат: {e2}")
            error_text = "❌ Ошибка отправки" if lang == "ru" else "❌ Sending error"
            await callback.answer(error_text)

# ========== КНОПКА "ЕЩЕ РАСЧЕТ" ДЛЯ ЛС (С ЯЗЫКОМ) ==========

@router.callback_query(F.data.startswith("calc_another_"))
async def handle_calc_another(callback: types.CallbackQuery):
    """Обработка кнопки 'Еще расчет' в ЛС с языком"""
    logger.info(f"🔘 Нажата кнопка 'Еще расчет': {callback.data}")
    
    # Получаем язык из callback_data: calc_another_ru
    parts = callback.data.split("_")
    if len(parts) != 3:
        lang = "ru"
    else:
        lang = parts[2]
    
    texts = TEXTS[lang]
    
    await callback.message.answer(
        f"{texts['new_calc_title']}\n\n"
        f"{texts['new_calc_text']}\n"
        f"<code>!12345</code>\n\n",
        parse_mode=ParseMode.HTML
    )
    
    answer_text = texts["enter_new_number"]
    await callback.answer(answer_text)

# ========== КОМАНДА ПОМОЩИ (С ЯЗЫКОМ) ==========

@router.message(Command("help_group", "help_mutations"))
async def help_mutations_command(message: Message):
    """Команда помощи для мутаций с языком"""
    logger.info(f"📖 Запрос помощи от {message.from_user.id}")
    
    # Получаем язык пользователя
    lang = get_user_language(message.from_user.id)
    texts = TEXTS[lang]
    
    help_text = f"{texts['help_title']}\n\n"
    
    help_text += f"{texts['how_to_use']}\n"
    for step in texts['how_to_steps']:
        help_text += f"{step}\n"
    
    help_text += f"\n{texts['examples']}\n"
    for example in texts['example_commands']:
        help_text += f"{example}\n"
    
    help_text += f"\n{texts['available_mutations']}\n"
    for emoji, description in texts['mutations'].items():
        help_text += f"{emoji} {description}\n"
    
    help_text += f"\n{texts['levels']}\n{texts['levels_text']}"
    
    await message.answer(help_text, parse_mode=ParseMode.HTML)

# ========== ПРОСТАЯ КОМАНДА ДЛЯ ТЕСТА (С ЯЗЫКОМ) ==========

@router.message(Command("ping", "test"))
async def ping_command(message: Message):
    """Проверка работы бота с языком"""
    logger.info(f"🏓 Ping команда от {message.from_user.id}")
    
    # Получаем язык пользователя
    lang = get_user_language(message.from_user.id)
    texts = TEXTS[lang]
    
    current_time = datetime.now().strftime("%H:%M:%S")
    chat_title = message.chat.title or "Личные сообщения" if lang == "ru" else "Private messages"
    
    response = (
        f"{texts['pong']}\n"
        f"{texts['time']} {current_time}\n"
        f"{texts['chat']} {chat_title}\n"
        f"{texts['sender']} {message.from_user.full_name}\n"
        f"{texts['calculator_works']}"
    )
    
    if message.chat.type == "private":
        await message.answer(response)
    else:
        await message.reply(response)