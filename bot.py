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

# Глобальная переменная для хранения задачи
bot_task = None

async def shutdown(signal, loop):
    """Корректное завершение бота"""
    logger.info(f"Received exit signal {signal.name}...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    
    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    
    loop.stop()

def handle_signal(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    loop = asyncio.get_event_loop()
    loop.create_task(shutdown(signal.Signals(signum), loop))

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
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: handle_signal(s, None))
            
        logger.info("Starting Telegram bot...")
        
        # Настраиваем таймауты через ApplicationBuilder
        builder = ApplicationBuilder().token(token)
        builder.get_updates_read_timeout(30)
        builder.get_updates_write_timeout(30)
        builder.get_updates_connect_timeout(30)
        builder.get_updates_pool_timeout(30)
        
        # Запускаем бота
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
    finally:
        # Корректное завершение
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1) 