from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
import os
from telegram import Bot, Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import threading

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///pixel_tracker.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Инициализация бота
bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.Integer, unique=True)
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
        db.create_all()
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

# Обработчики команд Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Создаем или получаем пользователя
    db_user = User.query.filter_by(telegram_id=user.id).first()
    if not db_user:
        db_user = User(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        db.session.add(db_user)
        db.session.commit()
    
    # Создаем кнопку для веб-приложения
    webapp_button = KeyboardButton(
        text="Открыть трекер ⏱",
        web_app=WebAppInfo(url=os.getenv('WEBAPP_URL'))
    )
    keyboard = ReplyKeyboardMarkup([[webapp_button]], resize_keyboard=True)
    
    welcome_text = (
        f"Привет, {user.first_name}! 👋\n\n"
        "Я помогу тебе отслеживать время и быть продуктивнее. "
        "Используй кнопку ниже, чтобы открыть трекер времени."
    )
    
    await update.message.reply_text(welcome_text, reply_markup=keyboard)

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

# Регистрация обработчиков команд
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("stats", stats_command))
application.add_handler(CommandHandler("settings", settings_command))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/user', methods=['GET'])
def get_user():
    telegram_id = request.args.get('telegram_id')
    if not telegram_id:
        return jsonify({'error': 'Telegram ID is required'}), 400
    
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'created_at': user.created_at.isoformat()
    })

@app.route('/api/stats/categories', methods=['GET'])
def get_categories():
    telegram_id = request.args.get('telegram_id')
    if not telegram_id:
        return jsonify({'error': 'Telegram ID is required'}), 400
    
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    categories = Category.query.filter_by(user_id=user.id).all()
    return jsonify([{
        'id': cat.id,
        'name': cat.name,
        'created_at': cat.created_at.isoformat()
    } for cat in categories])

@app.route('/api/stats/daily', methods=['GET'])
def get_daily_stats():
    telegram_id = request.args.get('telegram_id')
    if not telegram_id:
        return jsonify({'error': 'Telegram ID is required'}), 400
    
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    today = datetime.now(pytz.UTC).date()
    activities = Activity.query.filter(
        Activity.user_id == user.id,
        db.func.date(Activity.start_time) == today
    ).all()
    
    stats = {
        'total_time': 0,
        'categories': {}
    }
    
    for activity in activities:
        if activity.end_time:
            duration = (activity.end_time - activity.start_time).total_seconds() / 60  # в минутах
            stats['total_time'] += duration
            category_name = activity.category.name
            if category_name not in stats['categories']:
                stats['categories'][category_name] = 0
            stats['categories'][category_name] += duration
    
    return jsonify(stats)

@app.route('/api/activity/start', methods=['POST'])
def start_activity():
    data = request.get_json()
    telegram_id = data.get('telegram_id')
    category_id = data.get('category_id')
    
    if not telegram_id or not category_id:
        return jsonify({'error': 'Telegram ID and category ID are required'}), 400
    
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    category = Category.query.get(category_id)
    if not category or category.user_id != user.id:
        return jsonify({'error': 'Category not found'}), 404
    
    activity = Activity(
        user_id=user.id,
        category_id=category_id,
        start_time=datetime.now(pytz.UTC)
    )
    db.session.add(activity)
    db.session.commit()
    
    return jsonify({
        'id': activity.id,
        'start_time': activity.start_time.isoformat()
    })

@app.route('/api/activity/finish', methods=['POST'])
def finish_activity():
    data = request.get_json()
    telegram_id = data.get('telegram_id')
    activity_id = data.get('activity_id')
    
    if not telegram_id or not activity_id:
        return jsonify({'error': 'Telegram ID and activity ID are required'}), 400
    
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    activity = Activity.query.get(activity_id)
    if not activity or activity.user_id != user.id:
        return jsonify({'error': 'Activity not found'}), 404
    
    activity.end_time = datetime.now(pytz.UTC)
    db.session.commit()
    
    return jsonify({
        'id': activity.id,
        'end_time': activity.end_time.isoformat()
    })

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