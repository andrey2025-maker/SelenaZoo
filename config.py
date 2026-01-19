import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Токен бота (единственная переменная из .env)
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # ID канала-источника (встроенные в код)
    # Получить можно через @username_to_id_bot или forwardbot
    SOURCE_CHANNEL_ID = -1003291808303  # ЗАМЕНИТЕ НА ВАШ ID КАНАЛА
    
    # ID группы для обязательной подписки
    REQUIRED_GROUP_ID = -1002927295087  # ЗАМЕНИТЕ НА ВАШ ID ГРУППЫ
    
    # ID администратора (ваш Telegram ID)
    # Получить можно через @userinfobot
    ADMIN_ID = 1835558263  # ЗАМЕНИТЕ НА ВАШ ID
    
    # Настройки базы данных
    DATABASE_PATH = "database.db"
    
    # Английские названия фруктов (без @)
    AVAILABLE_FRUITS_EN = [
        "Pear", "Pineapple", "Gold Mango", "Dragon Fruit", 
        "Bloodstone Cycad", "Colossal Pinecone", "Franken Kiwi",
        "Pumpkin", "Durian", "Candy Corn", "Deepsea Pearl Fruit",
        "Volt Ginkgo", "Cranberry", "Acorn", "Gingerbread", "Candycane"
    ]
    
    # Русские названия фруктов (переводы)
    FRUIT_TRANSLATIONS = {
        # Английское: Русское
        "Pear": "Груша",
        "Pineapple": "Ананас",
        "Gold Mango": "Манго",
        "Dragon Fruit": "Драконий фрукт",
        "Bloodstone Cycad": "Bloodstone Cycad",
        "Colossal Pinecone": "Colossal Pinecone",
        "Franken Kiwi": "Франкен Киви",
        "Pumpkin": "Тыква",
        "Durian": "Дуриан",
        "Candy Corn": "Конфета",
        "Deepsea Pearl Fruit": "Ракушка",
        "Volt Ginkgo": "Volt Ginkgo",  # Исправлено: было "Volt Gingko"
        "Cranberry": "Клюква",
        "Acorn": "Желудь",
        "Gingerbread": "Пряничный человечек",
        "Candycane": "Конфетная трость"
    }
    
    # Эмодзи для фруктов (русская версия)
    FRUIT_EMOJIS_RU = {
        "Груша": "🍐",
        "Ананас": "🍍",
        "Манго": "🥭",
        "Драконий фрукт": "🐲",
        "Bloodstone Cycad": "🩸",
        "Colossal Pinecone": "❇️",
        "Франкен Киви": "🥝",
        "Тыква": "🎃",
        "Дуриан": "❄️",
        "Конфета": "🍬",
        "Ракушка": "🐚",
        "Volt Ginkgo": "⚡️🦕",  # Исправлено: было "Volt Gingko"
        "Клюква": "🍒",
        "Желудь": "🌰",
        "Пряничный человечек": "🍪",
        "Конфетная трость": "🎄🍭"
    }
    
    # Эмодзи для фруктов (английская версия - используем русские эмодзи)
    FRUIT_EMOJIS_EN = {
        "Pear": "🍐",
        "Pineapple": "🍍",
        "Gold Mango": "🥭",
        "Dragon Fruit": "🐲",
        "Bloodstone Cycad": "🩸",
        "Colossal Pinecone": "❇️",
        "Franken Kiwi": "🥝",
        "Pumpkin": "🎃",
        "Durian": "❄️",
        "Candy Corn": "🍬",
        "Deepsea Pearl Fruit": "🐚",
        "Volt Ginkgo": "⚡️🦕",  # Исправлено: было "Volt Ginkgo"
        "Cranberry": "🍒",
        "Acorn": "🌰",
        "Gingerbread": "🍪",
        "Candycane": "🎄🍭"
    }
    
    # Фрукты, которые нужно выделять жирным (True/False)
    BOLD_FRUITS = {
        "Pear": False,
        "Pineapple": False,
        "Gold Mango": False,
        "Dragon Fruit": False,
        "Bloodstone Cycad": False,
        "Colossal Pinecone": False,
        "Franken Kiwi": True,
        "Pumpkin": True,
        "Durian": True,
        "Candy Corn": True,
        "Deepsea Pearl Fruit": True,
        "Volt Ginkgo": True,
        "Cranberry": True,
        "Acorn": True,
        "Gingerbread": True,
        "Candycane": True
    }
    
    # Словарь для замены @-версий фруктов
    REPLACE_WORDS = {
        "@Pear": "Pear",
        "@Pineapple": "Pineapple",
        "@Gold Mango": "Gold Mango",
        "@DragonFruit": "Dragon Fruit",
        "@BloodstoneCycad": "Bloodstone Cycad",
        "@ColossalPinecone": "Colossal Pinecone",
        "@FrankenKiwi": "Franken Kiwi",
        "@Pumpkin": "Pumpkin",
        "@Durian": "Durian",
        "@CandyCorn": "Candy Corn",
        "@DeepseaPearlFruit": "Deepsea Pearl Fruit",
        "@VoltGinkgo": "Volt Ginkgo",
        "@Cranberry": "Cranberry",
        "@Acorn": "Acorn",
        "@Gingerbread": "Gingerbread",
        "@Candycane": "Candycane"
    }
    
    # Интервал проверки подписок (в секундах)
    SUBSCRIPTION_CHECK_INTERVAL = 86400  # 24 часа