from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from telegram import Bot, Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
import asyncio
import uuid
import json
import pandas as pd
from io import BytesIO

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///pixel_time_tracker.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
WEBAPP_URL = os.getenv('WEBAPP_URL', 'http://localhost:5000')
db = SQLAlchemy(app)

# Модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.String(50), unique=True)
    username = db.Column(db.String(100))
    photo_url = db.Column(db.String(200))
    level = db.Column(db.Integer, default=1)
    xp = db.Column(db.Integer, default=0)
    theme = db.Column(db.String(10), default='light')
    notifications = db.Column(db.Boolean, default=True)
    daily_goal = db.Column(db.Integer, default=120)  # Цель в минутах
    break_reminder = db.Column(db.Integer, default=60)  # Напоминание о перерыве каждые X минут
    activities = db.relationship('Activity', backref='user', lazy=True)
    categories = db.relationship('Category', backref='user', lazy=True)
    reminders = db.relationship('Reminder', backref='user', lazy=True)

    def calculate_level(self):
        new_level = 1 + (self.xp // 100)
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
            bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
            await bot.send_message(
                chat_id=self.telegram_id,
                text=f'🎉 Поздравляем! Вы достигли уровня {self.level}!'
            )

# Модель категорий
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(7), default='#4a90e2')  # HEX цвет
    icon = db.Column(db.String(50), default='📌')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    activities = db.relationship('Activity', backref='category', lazy=True)

# Модель напоминаний
class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    activity_name = db.Column(db.String(100))
    time = db.Column(db.Time)  # Время напоминания
    days = db.Column(db.String(20))  # Дни недели (1,2,3,4,5,6,7)
    is_active = db.Column(db.Boolean, default=True)

# Модель для хранения треков времени
class TimeTrack(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    activity = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)  # в секундах
    category = db.Column(db.String(50))
    tags = db.Column(db.String(200))

# Модель достижений
class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(50), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Achievement {self.name}>'

# Модель активностей
class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)  # в минутах
    notes = db.Column(db.Text)
    productivity = db.Column(db.Integer)  # Оценка продуктивности (1-5)
    breaks = db.relationship('Break', backref='activity', lazy=True)

# Модель перерывов
class Break(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'))
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)  # в минутах
    type = db.Column(db.String(20))  # short, long, lunch

# Инициализация бота Telegram
bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
application = ApplicationBuilder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/user', methods=['GET'])
def get_user():
    telegram_id = request.headers.get('X-Telegram-Id')
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({
        'id': user.id,
        'username': user.username,
        'photo_url': user.photo_url,
        'level': user.level,
        'xp': user.xp,
        'theme': user.theme,
        'notifications': user.notifications
    })

@app.route('/api/user', methods=['POST'])
def create_user():
    data = request.json
    user = User(
        telegram_id=data['telegram_id'],
        username=data.get('username'),
        photo_url=data.get('photo_url')
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'User created successfully'})

@app.route('/api/activity', methods=['POST'])
def start_activity():
    data = request.json
    user_id = request.headers.get('X-User-Id')
    
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401
    
    user = User.query.filter_by(telegram_id=user_id).first()
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    # Проверяем, нет ли уже активной задачи
    active_activity = Activity.query.filter_by(
        user_id=user.id,
        end_time=None
    ).first()
    
    if active_activity:
        return jsonify({'error': 'Уже есть активная задача'}), 400
    
    activity = Activity(
        user_id=user.id,
        name=data['name'],
        category=data.get('category', 'other')
    )
    
    db.session.add(activity)
    db.session.commit()
    
    return jsonify({
        'id': activity.id,
        'name': activity.name,
        'category': activity.category,
        'start_time': activity.start_time.isoformat()
    })

@app.route('/api/activity/stop', methods=['POST'])
def stop_activity():
    user_id = request.headers.get('X-User-Id')
    
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401
    
    user = User.query.filter_by(telegram_id=user_id).first()
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    activity = Activity.query.filter_by(
        user_id=user.id,
        end_time=None
    ).first()
    
    if not activity:
        return jsonify({'error': 'Нет активной задачи'}), 404
    
    activity.end_time = datetime.utcnow()
    activity.duration = int((activity.end_time - activity.start_time).total_seconds() / 60)
    
    db.session.commit()
    
    return jsonify({
        'id': activity.id,
        'name': activity.name,
        'category': activity.category,
        'duration': activity.duration,
        'start_time': activity.start_time.isoformat(),
        'end_time': activity.end_time.isoformat()
    })

@app.route('/api/categories', methods=['GET'])
def get_categories():
    telegram_id = request.headers.get('X-Telegram-Id')
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    categories = Category.query.filter_by(user_id=user.id).all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'color': c.color,
        'icon': c.icon
    } for c in categories])

@app.route('/api/categories', methods=['POST'])
def create_category():
    telegram_id = request.headers.get('X-Telegram-Id')
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.json
    category = Category(
        name=data['name'],
        color=data.get('color', '#4a90e2'),
        icon=data.get('icon', '📌'),
        user_id=user.id
    )
    db.session.add(category)
    db.session.commit()
    return jsonify({'message': 'Category created successfully'})

@app.route('/api/reminders', methods=['GET'])
def get_reminders():
    telegram_id = request.headers.get('X-Telegram-Id')
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    reminders = Reminder.query.filter_by(user_id=user.id, is_active=True).all()
    return jsonify([{
        'id': r.id,
        'activity_name': r.activity_name,
        'time': r.time.strftime('%H:%M'),
        'days': r.days.split(',')
    } for r in reminders])

@app.route('/api/reminders', methods=['POST'])
def create_reminder():
    telegram_id = request.headers.get('X-Telegram-Id')
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.json
    reminder = Reminder(
        user_id=user.id,
        activity_name=data['activity_name'],
        time=datetime.strptime(data['time'], '%H:%M').time(),
        days=','.join(data['days']),
        is_active=True
    )
    db.session.add(reminder)
    db.session.commit()
    return jsonify({'message': 'Reminder created successfully'})

@app.route('/api/export', methods=['GET'])
def export_data():
    telegram_id = request.headers.get('X-Telegram-Id')
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Получаем все активности пользователя
    activities = Activity.query.filter_by(user_id=user.id).all()
    
    # Создаем DataFrame
    data = []
    for activity in activities:
        data.append({
            'Дата': activity.start_time.strftime('%Y-%m-%d'),
            'Время начала': activity.start_time.strftime('%H:%M'),
            'Время окончания': activity.end_time.strftime('%H:%M') if activity.end_time else None,
            'Активность': activity.name,
            'Категория': activity.category if activity.category else None,
            'Длительность (мин)': activity.duration,
            'Заметки': activity.notes,
            'Продуктивность': activity.productivity
        })
    
    df = pd.DataFrame(data)
    
    # Создаем Excel файл
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Активности', index=False)
        
        # Форматирование
        workbook = writer.book
        worksheet = writer.sheets['Активности']
        
        # Заголовки
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4a90e2',
            'font_color': 'white',
            'border': 1
        })
        
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            worksheet.set_column(col_num, col_num, 15)
    
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'pixel_time_tracker_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )

@app.route('/api/break', methods=['POST'])
def start_break():
    telegram_id = request.headers.get('X-Telegram-Id')
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.json
    activity = Activity.query.get_or_404(data['activity_id'])
    
    if activity.user_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    break_record = Break(
        activity_id=activity.id,
        type=data.get('type', 'short')
    )
    db.session.add(break_record)
    db.session.commit()
    
    return jsonify({'message': 'Break started successfully'})

@app.route('/api/break/<int:break_id>', methods=['PUT'])
def end_break(break_id):
    telegram_id = request.headers.get('X-Telegram-Id')
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    break_record = Break.query.get_or_404(break_id)
    if break_record.activity.user_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    break_record.end_time = datetime.utcnow()
    break_record.duration = int((break_record.end_time - break_record.start_time).total_seconds() / 60)
    db.session.commit()
    
    return jsonify({
        'message': 'Break ended successfully',
        'duration': break_record.duration
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    telegram_id = request.headers.get('X-Telegram-Id')
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Статистика за последние 7 дней
    week_ago = datetime.utcnow() - timedelta(days=7)
    activities = Activity.query.filter(
        Activity.user_id == user.id,
        Activity.end_time >= week_ago
    ).all()

    total_duration = sum(activity.duration for activity in activities)
    daily_stats = {}
    category_stats = {}
    productivity_stats = {i: 0 for i in range(1, 6)}

    for activity in activities:
        # Статистика по дням
        date = activity.end_time.date().isoformat()
        daily_stats[date] = daily_stats.get(date, 0) + activity.duration

        # Статистика по категориям
        if activity.category:
            category_stats[activity.category] = category_stats.get(activity.category, 0) + activity.duration

        # Статистика по продуктивности
        if activity.productivity:
            productivity_stats[activity.productivity] += 1

    # Проверяем достижение ежедневной цели
    today = datetime.utcnow().date()
    today_activities = Activity.query.filter(
        Activity.user_id == user.id,
        db.func.date(Activity.end_time) == today
    ).all()
    today_duration = sum(activity.duration for activity in today_activities)
    goal_achieved = today_duration >= user.daily_goal

    return jsonify({
        'total_duration': total_duration,
        'daily_stats': daily_stats,
        'category_stats': category_stats,
        'productivity_stats': productivity_stats,
        'activities_count': len(activities),
        'today_duration': today_duration,
        'daily_goal': user.daily_goal,
        'goal_achieved': goal_achieved
    })

@app.route('/api/settings', methods=['PUT'])
def update_settings():
    telegram_id = request.headers.get('X-Telegram-Id')
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.json
    if 'theme' in data:
        user.theme = data['theme']
    if 'notifications' in data:
        user.notifications = data['notifications']
    
    db.session.commit()
    return jsonify({'message': 'Settings updated successfully'})

# Обработчики команд Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Создаем или получаем пользователя
    db_user = User.query.filter_by(telegram_id=str(user.id)).first()
    if not db_user:
        db_user = User(
            telegram_id=str(user.id),
            username=user.username,
            photo_url=user.get_profile_photos().photos[0][0].file_id if user.get_profile_photos().photos else None
        )
        db.session.add(db_user)
        db.session.commit()
    
    # Создаем кнопку для веб-приложения
    webapp_button = KeyboardButton(
        text="Открыть трекер ⏱",
        web_app=WebAppInfo(url=WEBAPP_URL)
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
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stats"""
    user = User.query.filter_by(telegram_id=str(update.effective_user.id)).first()
    if not user:
        await update.message.reply_text("Пользователь не найден. Используйте /start для начала работы.")
        return
    
    # Получаем статистику за сегодня
    today = datetime.utcnow().date()
    today_activities = Activity.query.filter(
        Activity.user_id == user.id,
        db.func.date(Activity.end_time) == today
    ).all()
    
    total_today = sum(activity.duration for activity in today_activities if activity.duration)
    
    stats_text = (
        f"📊 *Статистика за сегодня:*\n\n"
        f"⏱ Общее время: {total_today} минут\n"
        f"📝 Количество активностей: {len(today_activities)}\n"
        f"🎯 Цель на день: {user.daily_goal} минут\n"
        f"✨ Текущий уровень: {user.level}\n"
        f"⭐️ Опыт: {user.xp} XP"
    )
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /settings"""
    user = User.query.filter_by(telegram_id=str(update.effective_user.id)).first()
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
    
    await update.message.reply_text(settings_text, parse_mode=ParseMode.MARKDOWN)

def init_bot():
    """Инициализация бота"""
    application = ApplicationBuilder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("settings", settings_command))
    
    return application

# Веб-хук для Telegram
@app.route(f"/webhook/{os.getenv('TELEGRAM_BOT_TOKEN')}", methods=['POST'])
async def webhook():
    """Обработчик веб-хуков от Telegram"""
    if request.method == "POST":
        update = Update.de_json(request.get_json(), bot)
        
        # Обработка данных из веб-приложения
        if update.message and update.message.web_app_data:
            try:
                data = json.loads(update.message.web_app_data.data)
                user = User.query.filter_by(telegram_id=str(update.effective_user.id)).first()
                
                if 'action' in data:
                    if data['action'] == 'start_activity':
                        activity = Activity(
                            user_id=user.id,
                            name=data['name'],
                            category=data.get('category', 'other')
                        )
                        db.session.add(activity)
                        db.session.commit()
                        
                        await update.message.reply_text(
                            f"✅ Активность '{data['name']}' начата!",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    
                    elif data['action'] == 'stop_activity':
                        activity = Activity.query.filter_by(
                            user_id=user.id,
                            end_time=None
                        ).first()
                        
                        if activity:
                            activity.end_time = datetime.utcnow()
                            activity.duration = int((activity.end_time - activity.start_time).total_seconds() / 60)
                            db.session.commit()
                            
                            await update.message.reply_text(
                                f"✅ Активность '{activity.name}' завершена!\n"
                                f"⏱ Длительность: {activity.duration} минут",
                                parse_mode=ParseMode.MARKDOWN
                            )
            
            except Exception as e:
                print(f"Error processing web app data: {e}")
                await update.message.reply_text("❌ Произошла ошибка при обработке данных")
        
        # Применяем обновление
        application = init_bot()
        await application.process_update(update)
    
    return jsonify({'status': 'ok'})

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    achievements = Achievement.query.filter_by(user_id=user.id).all()
    
    # Получаем статистику
    total_time = TimeTrack.query.filter_by(user_id=user.id).with_entities(
        db.func.sum(TimeTrack.duration).label('total')
    ).scalar() or 0
    
    total_activities = TimeTrack.query.filter_by(user_id=user.id).count()
    unique_activities = TimeTrack.query.filter_by(user_id=user.id).with_entities(
        TimeTrack.activity
    ).distinct().count()
    
    return render_template('profile.html',
                         user=user,
                         achievements=achievements,
                         total_time=total_time,
                         total_activities=total_activities,
                         unique_activities=unique_activities)

@app.route('/stats')
def stats():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    achievements = Achievement.query.filter_by(user_id=user.id).all()
    
    # Получаем данные для графиков
    today = datetime.now()
    last_7_days = [(today - timedelta(days=i)).date() for i in range(6, -1, -1)]
    
    activity_data = {}
    activity_minutes = []
    activity_dates = []
    
    for date in last_7_days:
        tracks = TimeTrack.query.filter(
            TimeTrack.user_id == user.id,
            db.func.date(TimeTrack.start_time) == date
        ).all()
        
        total_minutes = sum(track.duration or 0 for track in tracks) // 60
        activity_data[date.day] = total_minutes
        activity_minutes.append(total_minutes)
        activity_dates.append(date.strftime('%d.%m'))
    
    # Получаем топ активностей
    top_activities = db.session.query(
        TimeTrack.activity,
        db.func.sum(TimeTrack.duration).label('total_duration')
    ).filter(
        TimeTrack.user_id == user.id
    ).group_by(
        TimeTrack.activity
    ).order_by(
        db.desc('total_duration')
    ).limit(5).all()
    
    top_activities_labels = [activity for activity, _ in top_activities]
    top_activities_data = [duration // 60 for _, duration in top_activities]
    
    # Рассчитываем прогресс уровня
    current_xp = user.xp
    next_level_xp = (user.level * 1000)
    xp_percentage = (current_xp % 1000) / 10
    
    return render_template('stats.html',
                         user=user,
                         achievements=achievements,
                         activity_dates=activity_dates,
                         activity_minutes=activity_minutes,
                         calendar_data=activity_data,
                         top_activities_labels=top_activities_labels,
                         top_activities_data=top_activities_data,
                         level=user.level,
                         current_xp=current_xp,
                         next_level_xp=next_level_xp,
                         xp_percentage=xp_percentage)

@app.route('/api/stats/daily', methods=['GET'])
def get_daily_stats():
    user_id = request.headers.get('X-User-Id')
    
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401
    
    user = User.query.filter_by(telegram_id=user_id).first()
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    # Получаем статистику за последние 24 часа по часам
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)
    
    activities = Activity.query.filter(
        Activity.user_id == user.id,
        Activity.start_time >= yesterday,
        Activity.end_time.isnot(None)
    ).all()
    
    # Создаем словарь для хранения длительности по часам
    hours_stats = {str(i).zfill(2): 0 for i in range(24)}
    
    for activity in activities:
        hour = activity.start_time.hour
        hours_stats[str(hour).zfill(2)] += activity.duration or 0
    
    return jsonify({
        'hours': list(hours_stats.keys()),
        'durations': list(hours_stats.values())
    })

@app.route('/api/stats/categories', methods=['GET'])
def get_category_stats():
    user_id = request.headers.get('X-User-Id')
    
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401
    
    user = User.query.filter_by(telegram_id=user_id).first()
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    # Получаем статистику по категориям за последние 7 дней
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    activities = Activity.query.filter(
        Activity.user_id == user.id,
        Activity.start_time >= week_ago,
        Activity.end_time.isnot(None)
    ).all()
    
    category_stats = {}
    for activity in activities:
        category = activity.category or 'other'
        if category not in category_stats:
            category_stats[category] = 0
        category_stats[category] += activity.duration or 0
    
    return jsonify(category_stats)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Настраиваем веб-хук для бота
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        webhook_url = f"{WEBAPP_URL}/webhook/{bot_token}"
        
        async def setup_webhook():
            await bot.set_webhook(webhook_url)
            print(f"Webhook set to {webhook_url}")
        
        # Запускаем настройку веб-хука
        asyncio.run(setup_webhook())
    
    app.run(debug=True) 