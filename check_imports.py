import sys

print("Проверка импортов...")

try:
    from aiogram import F
    print("✅ aiogram.F импортирован")
except ImportError as e:
    print(f"❌ Ошибка импорта aiogram.F: {e}")

try:
    from handlers.start import router as start_router
    print("✅ start.py импортирован")
except ImportError as e:
    print(f"❌ Ошибка импорта start.py: {e}")
    import traceback
    traceback.print_exc()

try:
    from handlers.settings import router as settings_router
    print("✅ settings.py импортирован")
except ImportError as e:
    print(f"❌ Ошибка импорта settings.py: {e}")

try:
    from handlers.admin import router as admin_router
    print("✅ admin.py импортирован")
except ImportError as e:
    print(f"❌ Ошибка импорта admin.py: {e}")

try:
    from handlers.channel import router as channel_router
    print("✅ channel.py импортирован")
except ImportError as e:
    print(f"❌ Ошибка импорта channel.py: {e}")

print("\nПроверка завершена!")