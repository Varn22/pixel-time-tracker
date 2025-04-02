from app import application
from telegram import Update
import logging
import os
from dotenv import load_dotenv
import sys
import signal
import asyncio
from telegram.ext import ApplicationBuilder

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

async def main():
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
            
        # Регистрируем обработчики сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
            
        logger.info("Starting Telegram bot...")
        
        # Настраиваем таймауты через ApplicationBuilder
        builder = ApplicationBuilder().token(token)
        builder.get_updates_read_timeout(30)
        builder.get_updates_write_timeout(30)
        builder.get_updates_connect_timeout(30)
        builder.get_updates_pool_timeout(30)
        
        # Запускаем бота с обработкой ошибок
        await application.initialize()
        await application.start()
        await application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
    except asyncio.TimeoutError:
        logger.error("Connection to Telegram API timed out. Please check your internet connection.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error running bot: {str(e)}")
        if "401 Unauthorized" in str(e):
            logger.error("Bot token is invalid or has been revoked. Please check your TELEGRAM_BOT_TOKEN environment variable.")
            logger.error("Make sure you have copied the token correctly from BotFather and it is set in Railway variables.")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main()) 