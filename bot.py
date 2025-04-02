from app import application
from telegram import Update
import logging
import os
from dotenv import load_dotenv
import sys
import signal

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info(f"Received signal {signum}")
    application.stop()
    sys.exit(0)

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
            
        # Регистрируем обработчики сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
            
        logger.info("Starting Telegram bot...")
        # Запускаем бота с обработкой ошибок
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            read_timeout=30,
            write_timeout=30,
            connect_timeout=30,
            pool_timeout=30
        )
    except Exception as e:
        logger.error(f"Error running bot: {str(e)}")
        if "401 Unauthorized" in str(e):
            logger.error("Bot token is invalid or has been revoked. Please check your TELEGRAM_BOT_TOKEN environment variable.")
        sys.exit(1)

if __name__ == '__main__':
    main() 