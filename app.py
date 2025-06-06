from flask import Flask, request, jsonify, render_template, session, redirect, url_for, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
import os
from telegram import Bot, Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import asyncio
import threading
import json
import logging
from functools import wraps

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__, 
    static_folder='static',
    static_url_path='/static',
    template_folder='templates'
)

# Конфигурация базы данных
database_url = os.getenv('DATABASE_URL')
if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    if '?' not in database_url:
        database_url += '?sslmode=require'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///pixel_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_size': 5,
    'max_overflow': 10
}

if database_url:
    app.config['SQLALCHEMY_ENGINE_OPTIONS']['connect_args'] = {
        'sslmode': 'require'
    }

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Декоратор для работы с контекстом приложения
def with_app_context(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        with app.app_context():
            return await f(*args, **kwargs)
    return decorated_function

# Обработчики команд Telegram
@with_app_context
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
    """Обработчик команды /help"""
    help_text = (
        "🔍 *Доступные команды:*\n\n"
        "/start - Начать работу с ботом\n"
        "/stats - Показать статистику\n"
        "/profile - Информация о профиле\n"
        "/settings - Настройки уведомлений\n\n"
        "📱 Используйте кнопку 'Открыть трекер' для доступа к основному интерфейсу."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stats"""
    user = User.query.filter_by(telegram_id=update.effective_user.id).first()
    if not user:
        await update.message.reply_text("Пользователь не найден. Используйте /start для начала работы.")
        return
    
    # Получаем статистику за сегодня
    today = datetime.now(pytz.UTC).date()
    today_activities = Activity.query.filter(
        Activity.user_id == user.id,
        db.func.date(Activity.start_time) == today
    ).all()
    
    total_today = sum(activity.duration or 0 for activity in today_activities) // 60
    
    stats_text = (
        f"📊 *Статистика за сегодня:*\n\n"
        f"⏱ Общее время: {total_today} минут\n"
        f"📝 Количество активностей: {len(today_activities)}\n"
        f"🎯 Цель на день: {user.daily_goal} минут\n"
        f"✨ Текущий уровень: {user.level}\n"
        f"⭐️ Опыт: {user.xp} XP"
    )
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /settings"""
    user = User.query.filter_by(telegram_id=update.effective_user.id).first()
    if not user:
        await update.message.reply_text("Пользователь не найден. Используйте /start для начала работы.")
        return
    
    settings_text = (
        f"⚙️ *Текущие настройки:*\n\n"
        f"🔔 Уведомления: {'включены' if user.notifications else 'выключены'}\n"
        f"🎯 Цель на день: {user.daily_goal} минут\n"
        f"⏰ Напоминание о перерыве: каждые {user.break_reminder} минут\n"
        f"🎨 Тема: {user.theme}\n\n"
        "Для изменения настроек используйте веб-интерфейс."
    )
    
    await update.message.reply_text(settings_text, parse_mode='Markdown')

# Инициализация бота
def init_bot():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
        
    application = Application.builder().token(token).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("settings", settings_command))
    
    return application

# Создаем экземпляр бота
application = init_bot()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True)
    username = db.Column(db.String(80))
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    level = db.Column(db.Integer, default=1)
    xp = db.Column(db.Integer, default=0)
    theme = db.Column(db.String(20), default='light')
    notifications = db.Column(db.Boolean, default=True)
    daily_goal = db.Column(db.Integer, default=120)  # Цель в минутах
    break_reminder = db.Column(db.Integer, default=60)  # Напоминание о перерыве каждые X минут
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    activities = db.relationship('Activity', backref='user', lazy=True)
    categories = db.relationship('Category', backref='user', lazy=True)
    achievements = db.relationship('Achievement', backref='user', lazy=True)

    def calculate_level(self):
        new_level = 1 + (self.xp // 1000)
        if new_level > self.level:
            self.level = new_level
            return True
        return False

    def add_xp(self, amount):
        self.xp += amount
        if self.calculate_level():
            asyncio.run(self.notify_level_up())
        db.session.commit()

    async def notify_level_up(self):
        if self.notifications:
            await bot.send_message(
                chat_id=self.telegram_id,
                text=f'🎉 Поздравляем! Вы достигли уровня {self.level}!'
            )

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    activities = db.relationship('Activity', backref='category', lazy=True)

class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)  # в секундах
    notes = db.Column(db.Text)
    productivity = db.Column(db.Integer)  # Оценка продуктивности (1-5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Achievement(db.Model):
    __tablename__ = 'achievements'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(50), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)

def init_db():
    with app.app_context():
        try:
            # Логируем URL базы данных (без пароля)
            db_url = os.getenv('DATABASE_URL', '')
            if db_url:
                masked_url = db_url.replace(db_url.split('@')[0].split(':')[2], '****')
                logger.info(f"Attempting to connect to database: {masked_url}")
            else:
                logger.error("DATABASE_URL not found in environment variables")
                return
            
            # Проверяем подключение к базе данных
            db.engine.connect()
            logger.info("Database connection successful")
            
            # Создаем таблицы
            db.create_all()
            logger.info("Database tables created successfully")
            
            try:
                # Создаем категории по умолчанию для каждого пользователя
                users = User.query.all()
                default_categories = ['Работа', 'Учеба', 'Отдых', 'Спорт', 'Другое']
                for user in users:
                    existing_categories = [cat.name for cat in user.categories]
                    for category_name in default_categories:
                        if category_name not in existing_categories:
                            category = Category(name=category_name, user_id=user.id)
                            db.session.add(category)
                db.session.commit()
                logger.info("Default categories created")
            except Exception as e:
                logger.error(f"Error creating default categories: {str(e)}")
                db.session.rollback()
                
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/user', methods=['GET'])
def get_user():
    try:
        user_data = request.args.get('user')
        if not user_data:
            logger.warning("No user data received in /api/user")
            return jsonify({'error': 'No user data'}), 400
            
        try:
            user = json.loads(user_data)
            logger.info(f"Received user data: {user}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON data received in /api/user")
            return jsonify({'error': 'Invalid JSON data'}), 400
            
        telegram_id = user.get('id')
        
        if not telegram_id:
            logger.warning("No Telegram ID found in user data")
            return jsonify({'error': 'No Telegram ID'}), 400
        
        db_user = User.query.filter_by(telegram_id=telegram_id).first()
        if not db_user:
            logger.info(f"User with telegram_id {telegram_id} not found. Creating new user.")
            db_user = User(
                telegram_id=telegram_id,
                username=user.get('username'),
                first_name=user.get('first_name'),
                last_name=user.get('last_name')
            )
            db.session.add(db_user)
            db.session.commit()
            logger.info(f"User {telegram_id} created successfully.")
            
            # Создаем категории по умолчанию для нового пользователя
            try:
                default_categories = ['Работа', 'Учеба', 'Отдых', 'Спорт', 'Другое']
                for category_name in default_categories:
                    category = Category(name=category_name, user_id=db_user.id)
                    db.session.add(category)
                db.session.commit()
                logger.info(f"Default categories created for user {telegram_id}.")
            except Exception as cat_e:
                db.session.rollback() # Откатываем добавление категорий в случае ошибки
                logger.error(f"Error creating default categories for user {telegram_id}: {str(cat_e)}")

        else:
             logger.info(f"User {telegram_id} found.")

        # --- ОБНОВЛЯЕМ ВОЗВРАЩАЕМЫЕ ДАННЫЕ ---
        response_data = {
            'id': db_user.id, # Возвращаем внутренний ID базы данных
            'telegram_id': db_user.telegram_id, # Также возвращаем telegram_id
            'username': db_user.username,
            'first_name': db_user.first_name,
            'last_name': db_user.last_name,
            'level': db_user.level,
            'xp': db_user.xp,
            'theme': db_user.theme,
            'notifications': db_user.notifications,
            'daily_goal': db_user.daily_goal,
            'break_reminder': db_user.break_reminder
        }
        logger.info(f"Returning user data for {telegram_id}: {response_data}")
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Unexpected error in get_user: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/api/stats/daily', methods=['GET'])
def get_daily_stats():
    try:
        user_data = request.args.get('user')
        if not user_data:
            return jsonify({'error': 'No user data'}), 400
            
        try:
            user = json.loads(user_data)
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid JSON data'}), 400
            
        telegram_id = user.get('id')
        if not telegram_id:
            return jsonify({'error': 'No Telegram ID'}), 400
            
        db_user = User.query.filter_by(telegram_id=telegram_id).first()
        if not db_user:
            return jsonify({'error': 'User not found'}), 404
            
        today = datetime.now(pytz.UTC).date()
        activities = Activity.query.filter(
            Activity.user_id == db_user.id,
            db.func.date(Activity.start_time) == today
        ).all()
        
        total_time = sum((activity.end_time - activity.start_time).total_seconds() / 60 
                        for activity in activities if activity.end_time) if activities else 0
        total_tasks = len(activities)
        productivity = sum(activity.productivity for activity in activities) / total_tasks if total_tasks > 0 else 0
        
        return jsonify({
            'total_time': total_time,
            'total_tasks': total_tasks,
            'productivity': round(productivity, 1)
        })
    except Exception as e:
        logger.error(f"Error in get_daily_stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/categories', methods=['GET'])
def get_category_stats():
    try:
        user_data = request.args.get('user')
        if not user_data:
            return jsonify({'error': 'No user data'}), 400
            
        try:
            user = json.loads(user_data)
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid JSON data'}), 400
            
        telegram_id = user.get('id')
        if not telegram_id:
            return jsonify({'error': 'No Telegram ID'}), 400
            
        db_user = User.query.filter_by(telegram_id=telegram_id).first()
        if not db_user:
            return jsonify({'error': 'User not found'}), 404
            
        categories = Category.query.filter_by(user_id=db_user.id).all()
        stats = []
        
        for category in categories:
            activities = Activity.query.filter_by(
                user_id=db_user.id,
                category_id=category.id
            ).all()
            
            total_time = sum(activity.duration for activity in activities)
            total_tasks = len(activities)
            
            stats.append({
                'id': category.id,
                'name': category.name,
                'total_time': total_time,
                'total_tasks': total_tasks
            })
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error in get_category_stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/activity/start', methods=['POST'])
def start_activity():
    try:
        data = request.get_json()
        user_data = data.get('user')
        if not user_data:
            return jsonify({'error': 'No user data'}), 400
            
        user = json.loads(user_data)
        telegram_id = user.get('id')
        category_id = data.get('category_id')
        
        if not telegram_id or not category_id:
            return jsonify({'error': 'Telegram ID and category ID are required'}), 400
        
        db_user = User.query.filter_by(telegram_id=telegram_id).first()
        if not db_user:
            return jsonify({'error': 'User not found'}), 404
        
        category = Category.query.get(category_id)
        if not category or category.user_id != db_user.id:
            return jsonify({'error': 'Category not found'}), 404
        
        activity = Activity(
            user_id=db_user.id,
            category_id=category_id,
            name=data.get('name', 'Новая активность'),
            start_time=datetime.now(pytz.UTC)
        )
        db.session.add(activity)
        db.session.commit()
        
        return jsonify({
            'id': activity.id,
            'start_time': activity.start_time.isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/activity/finish', methods=['POST'])
def finish_activity():
    try:
        data = request.get_json()
        user_data = data.get('user')
        if not user_data:
            return jsonify({'error': 'No user data'}), 400
            
        user = json.loads(user_data)
        telegram_id = user.get('id')
        activity_id = data.get('activity_id')
        
        if not telegram_id or not activity_id:
            return jsonify({'error': 'Telegram ID and activity ID are required'}), 400
        
        db_user = User.query.filter_by(telegram_id=telegram_id).first()
        if not db_user:
            return jsonify({'error': 'User not found'}), 404
        
        activity = Activity.query.get(activity_id)
        if not activity or activity.user_id != db_user.id:
            return jsonify({'error': 'Activity not found'}), 404
        
        activity.end_time = datetime.now(pytz.UTC)
        activity.duration = (activity.end_time - activity.start_time).total_seconds()
        activity.notes = data.get('notes')
        activity.productivity = data.get('productivity')
        
        # Добавляем XP за завершенную активность
        xp = int(activity.duration / 60)  # 1 XP за каждую минуту
        db_user.add_xp(xp)
        
        db.session.commit()
        
        return jsonify({
            'id': activity.id,
            'end_time': activity.end_time.isoformat(),
            'duration': activity.duration,
            'xp_earned': xp
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/theme', methods=['POST'])
def update_theme():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        user_data = data.get('user')
        if not user_data:
            return jsonify({'error': 'No user data'}), 400
            
        try:
            user = json.loads(user_data) if isinstance(user_data, str) else user_data
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid JSON data'}), 400
            
        telegram_id = user.get('id')
        
        if not telegram_id:
            return jsonify({'error': 'No Telegram ID'}), 400
            
        theme = data.get('theme')
        if not theme:
            return jsonify({'error': 'No theme specified'}), 400
        
        db_user = User.query.filter_by(telegram_id=telegram_id).first()
        if not db_user:
            return jsonify({'error': 'User not found'}), 404
            
        db_user.theme = theme
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error in update_theme: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/notifications', methods=['POST'])
def update_notifications():
    try:
        data = request.get_json()
        user_data = data.get('user')
        if not user_data:
            return jsonify({'error': 'No user data'}), 400
            
        user = json.loads(user_data)
        telegram_id = user.get('id')
        
        if not telegram_id:
            return jsonify({'error': 'No Telegram ID'}), 400
            
        notifications = data.get('notifications')
        if notifications is None:
            return jsonify({'error': 'No notifications setting specified'}), 400
        
        db_user = User.query.filter_by(telegram_id=telegram_id).first()
        if not db_user:
            return jsonify({'error': 'User not found'}), 404
            
        db_user.notifications = notifications
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error in update_notifications: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/daily_goal', methods=['POST'])
def update_daily_goal():
    try:
        data = request.get_json()
        user_data = data.get('user')
        if not user_data:
            return jsonify({'error': 'No user data'}), 400
            
        user = json.loads(user_data)
        telegram_id = user.get('id')
        
        if not telegram_id:
            return jsonify({'error': 'No Telegram ID'}), 400
            
        daily_goal = data.get('daily_goal')
        if daily_goal is None:
            return jsonify({'error': 'No daily goal specified'}), 400
        
        db_user = User.query.filter_by(telegram_id=telegram_id).first()
        if not db_user:
            return jsonify({'error': 'User not found'}), 404
            
        db_user.daily_goal = daily_goal
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error in update_daily_goal: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/break_reminder', methods=['POST'])
def update_break_reminder():
    try:
        data = request.get_json()
        user_data = data.get('user')
        if not user_data:
            return jsonify({'error': 'No user data'}), 400
            
        user = json.loads(user_data)
        telegram_id = user.get('id')
        
        if not telegram_id:
            return jsonify({'error': 'No Telegram ID'}), 400
            
        break_reminder = data.get('break_reminder')
        if break_reminder is None:
            return jsonify({'error': 'No break reminder specified'}), 400
        
        db_user = User.query.filter_by(telegram_id=telegram_id).first()
        if not db_user:
            return jsonify({'error': 'User not found'}), 404
            
        db_user.break_reminder = break_reminder
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error in update_break_reminder: {str(e)}")
        return jsonify({'error': str(e)}), 500

@with_app_context
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

def run_flask():
    """Запуск Flask приложения"""
    app.run(debug=True, use_reloader=False)

def run_bot():
    """Запуск Telegram бота"""
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    init_db()
    
    # Запускаем Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    # Запускаем бота в основном потоке
    run_bot()
else:
    init_db()  # Инициализируем базу данных при запуске через gunicorn 