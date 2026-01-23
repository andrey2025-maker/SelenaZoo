import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from config import Config

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = Config.DATABASE_PATH):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Создание подключения к БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Инициализация таблиц базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей - ДОБАВЛЕНО ПОЛЕ USERNAME
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    language TEXT DEFAULT 'RUS',
                    is_subscribed INTEGER DEFAULT 0,
                    free_totems INTEGER DEFAULT 1,
                    paid_totems INTEGER DEFAULT 1,
                    last_check TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица выбранных фруктов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_fruits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    fruit_name TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                    UNIQUE(user_id, fruit_name)
                )
            ''')
            
            # Таблица исключений подписок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscription_exceptions (
                    user_id INTEGER PRIMARY KEY,
                    admin_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            ''')
            
            # Создаем индексы для ускорения запросов
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_subscribed ON users(is_subscribed)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_fruits_user ON user_fruits(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_fruits_fruit ON user_fruits(fruit_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_exceptions_user ON subscription_exceptions(user_id)')
            
            conn.commit()
        logger.info("Database initialized with indexes")
    
    def add_user(self, user_id: int, username: str = None, language: str = "RUS"):
        """Добавление нового пользователя с username"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Проверяем, существует ли пользователь
                cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
                existing_user = cursor.fetchone()
                
                if existing_user:
                    # Обновляем username если пользователь уже существует
                    if username:
                        cursor.execute('''
                            UPDATE users SET username = ? WHERE user_id = ?
                        ''', (username, user_id))
                else:
                    # Добавляем нового пользователя
                    cursor.execute('''
                        INSERT INTO users (user_id, username, language) 
                        VALUES (?, ?, ?)
                    ''', (user_id, username, language))
                
                conn.commit()
                logger.info(f"User {user_id} added/updated with username: {username}")
                return True
            except Exception as e:
                logger.error(f"Error adding user {user_id}: {e}")
                return False
    
    def update_user_language(self, user_id: int, language: str):
        """Обновление языка пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET language = ? WHERE user_id = ?
            ''', (language, user_id))
            conn.commit()
    
    def update_subscription(self, user_id: int, is_subscribed: bool):
        """Обновление статуса подписки"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET is_subscribed = ?, last_check = ?
                WHERE user_id = ?
            ''', (1 if is_subscribed else 0, datetime.now(), user_id))
            conn.commit()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получение информации о пользователе"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM users WHERE user_id = ?
            ''', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_user_fruits(self, user_id: int) -> List[str]:
        """Получение списка выбранных фруктов пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT fruit_name FROM user_fruits WHERE user_id = ?
            ''', (user_id,))
            return [row[0] for row in cursor.fetchall()]
    
    def update_user_fruits(self, user_id: int, fruits: List[str]):
        """Обновление списка фруктов пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Удаляем старые записи
            cursor.execute('DELETE FROM user_fruits WHERE user_id = ?', (user_id,))
            # Добавляем новые
            for fruit in fruits:
                cursor.execute('''
                    INSERT INTO user_fruits (user_id, fruit_name) VALUES (?, ?)
                ''', (user_id, fruit))
            conn.commit()
    
    def update_totem_settings(self, user_id: int, free_totems: bool = None, paid_totems: bool = None):
        """Обновление настроек тотемов"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            
            if free_totems is not None:
                updates.append("free_totems = ?")
                params.append(1 if free_totems else 0)
            
            if paid_totems is not None:
                updates.append("paid_totems = ?")
                params.append(1 if paid_totems else 0)
            
            if updates:
                params.append(user_id)
                query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
                cursor.execute(query, params)
                conn.commit()
    
    def get_all_users(self) -> List[Dict]:
        """Получение списка всех пользователей"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_active_subscribers(self) -> List[Dict]:
        """Получение пользователей с активной подпиской"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.*, 
                       GROUP_CONCAT(uf.fruit_name) as fruits
                FROM users u
                LEFT JOIN user_fruits uf ON u.user_id = uf.user_id
                WHERE u.is_subscribed = 1
                GROUP BY u.user_id
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_users_for_fruit(self, fruit_name: str) -> List[int]:
        """Получение пользователей, подписанных на конкретный фрукт"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT u.user_id 
                FROM users u
                JOIN user_fruits uf ON u.user_id = uf.user_id
                WHERE u.is_subscribed = 1 
                AND (uf.fruit_name = ? OR uf.fruit_name = 'all')
            ''', (fruit_name,))
            return [row[0] for row in cursor.fetchall()]
    
    def get_users_for_totem(self, is_free: bool) -> List[int]:
        """Получение пользователей, подписанных на тотемы"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            column = "free_totems" if is_free else "paid_totems"
            cursor.execute(f'''
                SELECT user_id FROM users 
                WHERE is_subscribed = 1 AND {column} = 1
            ''')
            return [row[0] for row in cursor.fetchall()]
    
    def get_statistics(self) -> Dict:
        """Получение статистики"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_subscribed = 1")
            active_subscribers = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT fruit_name, COUNT(*) as count 
                FROM user_fruits 
                GROUP BY fruit_name 
                ORDER BY count DESC
            ''')
            fruit_stats = cursor.fetchall()
            
            cursor.execute('''
                SELECT 
                    SUM(free_totems) as free_totems_count,
                    SUM(paid_totems) as paid_totems_count
                FROM users 
                WHERE is_subscribed = 1
            ''')
            totem_stats = cursor.fetchone()
            
            # Форматируем статистику фруктов с переводами
            formatted_fruit_stats = {}
            for fruit, count in fruit_stats:
                if fruit == "all":
                    formatted_fruit_stats["Все фрукты"] = count
                else:
                    russian_name = Config.FRUIT_TRANSLATIONS.get(fruit, fruit)
                    formatted_fruit_stats[russian_name] = count
            
            return {
                "total_users": total_users,
                "active_subscribers": active_subscribers,
                "fruit_stats": formatted_fruit_stats,
                "free_totems": totem_stats[0] or 0,
                "paid_totems": totem_stats[1] or 0
            }
    
    def update_username(self, user_id: int, username: str):
        """Обновление username пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET username = ? WHERE user_id = ?
            ''', (username, user_id))
            conn.commit()
            logger.info(f"Username updated for user {user_id}: {username}")
    
    # ========== МЕТОДЫ ДЛЯ ИСКЛЮЧЕНИЙ ==========
    
    def is_exception(self, user_id: int) -> bool:
        """Проверка, есть ли пользователь в исключениях"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM subscription_exceptions WHERE user_id = ?', (user_id,))
            return cursor.fetchone() is not None
    
    def add_exception(self, user_id: int, admin_id: int) -> bool:
        """Добавление пользователя в исключения"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO subscription_exceptions (user_id, admin_id) 
                    VALUES (?, ?)
                ''', (user_id, admin_id))
                conn.commit()
                logger.info(f"User {user_id} added to exceptions by admin {admin_id}")
                return True
            except Exception as e:
                logger.error(f"Error adding exception for user {user_id}: {e}")
                return False
    
    def remove_exception(self, user_id: int) -> bool:
        """Удаление пользователя из исключений"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM subscription_exceptions WHERE user_id = ?', (user_id,))
            conn.commit()
            success = cursor.rowcount > 0
            if success:
                logger.info(f"User {user_id} removed from exceptions")
            return success
    
    def get_exceptions(self) -> List[Dict]:
        """Получение списка исключений"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT se.*, u.username, u.language
                FROM subscription_exceptions se
                LEFT JOIN users u ON se.user_id = u.user_id
                ORDER BY se.created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_user_with_exception_status(self, user_id: int) -> Dict:
        """Получение информации о пользователе со статусом исключения"""
        user = self.get_user(user_id)
        if user:
            user['is_exception'] = self.is_exception(user_id)
        return user