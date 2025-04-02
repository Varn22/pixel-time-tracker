from app import application
import logging
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    try:
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
        raise 