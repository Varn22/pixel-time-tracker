from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import logging
import os
from dotenv import load_dotenv
import sys
from datetime import datetime
import pytz
import atexit
from web import db, User, Category, Activity

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = User.query.filter_by(telegram_id=user.id).first()
    
    if not db_user:
        db_user = User(telegram_id=user.id, username=user.username)
        db.session.add(db_user)
        db.session.commit()
        
        # Создаем категории по умолчанию
        default_categories = [
            Category(name="Работа", user_id=db_user.id),
            Category(name="Учеба", user_id=db_user.id),
            Category(name="Отдых", user_id=db_user.id),
            Category(name="Спорт", user_id=db_user.id),
            Category(name="Другое", user_id=db_user.id)
        ]
        db.session.add_all(default_categories)
        db.session.commit()
    
    await update.message.reply_text(
        f"Привет, {user.first_name}! Я бот для отслеживания времени. "
        "Используйте /help для просмотра доступных команд."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
Доступные команды:
/start - Начать работу с ботом
/help - Показать это сообщение
/start_activity - Начать новую активность
/stop_activity - Остановить текущую активность
/status - Показать текущий статус
/categories - Управление категориями
/statistics - Показать статистику
    """
    await update.message.reply_text(help_text)

async def start_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = User.query.filter_by(telegram_id=user.id).first()
    
    if not db_user:
        await update.message.reply_text("Пожалуйста, сначала используйте команду /start")
        return
    
    # Проверяем, есть ли уже активная активность
    active_activity = Activity.query.filter_by(
        user_id=db_user.id,
        end_time=None
    ).first()
    
    if active_activity:
        await update.message.reply_text(
            f"У вас уже есть активная активность: {active_activity.name} "
            f"в категории {active_activity.category.name}"
        )
        return
    
    # Получаем категории пользователя
    categories = Category.query.filter_by(user_id=db_user.id).all()
    
    if not categories:
        await update.message.reply_text("У вас нет категорий. Создайте хотя бы одну категорию.")
        return
    
    # Создаем клавиатуру с категориями
    keyboard = []
    for category in categories:
        keyboard.append([InlineKeyboardButton(
            category.name,
            callback_data=f"start_activity_{category.id}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выберите категорию для новой активности:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("start_activity_"):
        category_id = int(query.data.split("_")[2])
        category = Category.query.get(category_id)
        
        if not category:
            await query.message.reply_text("Категория не найдена")
            return
        
        # Создаем новую активность
        activity = Activity(
            name=f"Активность в категории {category.name}",
            category_id=category_id,
            user_id=category.user_id,
            start_time=datetime.now(pytz.UTC)
        )
        db.session.add(activity)
        db.session.commit()
        
        await query.message.reply_text(
            f"Начата новая активность в категории {category.name}"
        )
    
    elif query.data.startswith("stop_activity_"):
        activity_id = int(query.data.split("_")[2])
        activity = Activity.query.get(activity_id)
        
        if not activity:
            await query.message.reply_text("Активность не найдена")
            return
        
        activity.end_time = datetime.now(pytz.UTC)
        db.session.commit()
        
        duration = activity.end_time - activity.start_time
        hours = duration.total_seconds() / 3600
        
        await query.message.reply_text(
            f"Активность '{activity.name}' завершена.\n"
            f"Продолжительность: {hours:.2f} часов"
        )

async def stop_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = User.query.filter_by(telegram_id=user.id).first()
    
    if not db_user:
        await update.message.reply_text("Пожалуйста, сначала используйте команду /start")
        return
    
    # Находим активную активность
    active_activity = Activity.query.filter_by(
        user_id=db_user.id,
        end_time=None
    ).first()
    
    if not active_activity:
        await update.message.reply_text("У вас нет активных активностей")
        return
    
    # Создаем клавиатуру для подтверждения
    keyboard = [[
        InlineKeyboardButton(
            "Остановить",
            callback_data=f"stop_activity_{active_activity.id}"
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"У вас активна активность '{active_activity.name}' "
        f"в категории {active_activity.category.name}.\n"
        "Хотите остановить её?",
        reply_markup=reply_markup
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = User.query.filter_by(telegram_id=user.id).first()
    
    if not db_user:
        await update.message.reply_text("Пожалуйста, сначала используйте команду /start")
        return
    
    # Находим активную активность
    active_activity = Activity.query.filter_by(
        user_id=db_user.id,
        end_time=None
    ).first()
    
    if active_activity:
        duration = datetime.now(pytz.UTC) - active_activity.start_time
        hours = duration.total_seconds() / 3600
        
        await update.message.reply_text(
            f"Текущая активность: {active_activity.name}\n"
            f"Категория: {active_activity.category.name}\n"
            f"Начата: {active_activity.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Прошло времени: {hours:.2f} часов"
        )
    else:
        await update.message.reply_text("У вас нет активных активностей")

async def categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = User.query.filter_by(telegram_id=user.id).first()
    
    if not db_user:
        await update.message.reply_text("Пожалуйста, сначала используйте команду /start")
        return
    
    categories = Category.query.filter_by(user_id=db_user.id).all()
    
    if not categories:
        await update.message.reply_text("У вас нет категорий")
        return
    
    message = "Ваши категории:\n\n"
    for category in categories:
        message += f"- {category.name}\n"
    
    await update.message.reply_text(message)

async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = User.query.filter_by(telegram_id=user.id).first()
    
    if not db_user:
        await update.message.reply_text("Пожалуйста, сначала используйте команду /start")
        return
    
    # Получаем статистику по категориям
    categories = Category.query.filter_by(user_id=db_user.id).all()
    
    if not categories:
        await update.message.reply_text("У вас нет категорий")
        return
    
    message = "Статистика по категориям:\n\n"
    for category in categories:
        activities = Activity.query.filter_by(
            category_id=category.id,
            user_id=db_user.id
        ).all()
        
        total_hours = 0
        for activity in activities:
            if activity.end_time:
                duration = activity.end_time - activity.start_time
                total_hours += duration.total_seconds() / 3600
        
        message += f"{category.name}:\n"
        message += f"- Количество активностей: {len(activities)}\n"
        message += f"- Общее время: {total_hours:.2f} часов\n\n"
    
    await update.message.reply_text(message)

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
        
        # Создаем приложение бота
        application = Application.builder().token(token).build()
        
        # Регистрируем обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("start_activity", start_activity))
        application.add_handler(CommandHandler("stop_activity", stop_activity))
        application.add_handler(CommandHandler("status", status))
        application.add_handler(CommandHandler("categories", categories))
        application.add_handler(CommandHandler("statistics", statistics))
        application.add_handler(CallbackQueryHandler(button_handler))
        
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