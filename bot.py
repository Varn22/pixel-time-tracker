from app import application
from telegram import Update
import logging
import os
from dotenv import load_dotenv
import sys
from telegram.ext import ApplicationBuilder
from flask import Flask
import threading
import atexit
from waitress import serve
import time

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создаем Flask приложение для health check
app = Flask(__name__)

@app.route('/')
def health_check():
    return 'OK', 200

def run_flask():
    port = int(os.getenv('PORT', 8000))
    serve(app, host='0.0.0.0', port=port)

def is_bot_running():
    """Проверяет, запущен ли уже бот"""
    lock_file = '/tmp/bot.lock'
    if not os.path.exists(lock_file):
        return False
        
    try:
        with open(lock_file, 'r') as f:
            pid = int(f.read().strip())
        # Проверяем, существует ли процесс
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError):
        # Если процесс не существует, удаляем файл блокировки
        try:
            os.remove(lock_file)
        except:
            pass
        return False

def create_lock():
    """Создает файл блокировки"""
    with open('/tmp/bot.lock', 'w') as f:
        f.write(str(os.getpid()))

def cleanup_lock():
    """Очистка блокировки при выходе"""
    try:
        if os.path.exists('/tmp/bot.lock'):
            os.remove('/tmp/bot.lock')
    except:
        pass

def main():
    try:
        # Проверяем наличие токена бота
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
            sys.exit(1)
            
        # Проверяем формат токена
        if not token.count(':') == 1:
            logger.error("Invalid token format. Token should be in format '123456789:ABCdefGHIjklMNOpqrsTUVwxyz'")
            sys.exit(1)
            
        # Логируем информацию о токене (без самого токена)
        bot_id = token.split(':')[0]
        logger.info(f"Bot ID: {bot_id}")
        logger.info("Token format is valid")

        # Проверяем, не запущен ли уже бот
        if is_bot_running():
            logger.error("Another bot instance is already running")
            sys.exit(1)
            
        # Создаем файл блокировки
        create_lock()
            
        # Регистрируем очистку блокировки при выходе
        atexit.register(cleanup_lock)
            
        logger.info("Starting Telegram bot...")
        
        # Настраиваем таймауты через ApplicationBuilder
        builder = ApplicationBuilder().token(token)
        builder.get_updates_read_timeout(30)
        builder.get_updates_write_timeout(30)
        builder.get_updates_connect_timeout(30)
        builder.get_updates_pool_timeout(30)
        
        # Запускаем Flask в отдельном потоке
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        
        # Запускаем бота
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
    except Exception as e:
        logger.error(f"Error running bot: {str(e)}")
        if "401 Unauthorized" in str(e):
            logger.error("Bot token is invalid or has been revoked. Please check your TELEGRAM_BOT_TOKEN environment variable.")
            logger.error("Make sure you have copied the token correctly from BotFather and it is set in Railway variables.")
        cleanup_lock()
        sys.exit(1)

if __name__ == '__main__':
    main() 