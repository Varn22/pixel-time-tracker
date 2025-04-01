from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import WebAppData
import asyncio
import uuid
import json

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///pixel_time_tracker.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
db = SQLAlchemy(app)

# Модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.Integer, unique=True)
    username = db.Column(db.String(80))
    photo_url = db.Column(db.String(200))
    level = db.Column(db.Integer, default=1)
    xp = db.Column(db.Integer, default=0)
    theme = db.Column(db.String(10), default='light')
    notifications = db.Column(db.Boolean, default=True)
    activities = db.relationship('Activity', backref='user', lazy=True)

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
    name = db.Column(db.String(100))
    category = db.Column(db.String(50))
    tags = db.Column(db.String(200))
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)  # в минутах
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

# Инициализация бота Telegram
bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))

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
    telegram_id = request.headers.get('X-Telegram-Id')
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.json
    activity = Activity(
        name=data['name'],
        category=data.get('category'),
        tags=data.get('tags'),
        user_id=user.id
    )
    db.session.add(activity)
    db.session.commit()
    return jsonify({'message': 'Activity started successfully'})

@app.route('/api/activity/<int:activity_id>', methods=['PUT'])
def stop_activity(activity_id):
    telegram_id = request.headers.get('X-Telegram-Id')
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    activity = Activity.query.get_or_404(activity_id)
    if activity.user_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    activity.end_time = datetime.utcnow()
    activity.duration = int((activity.end_time - activity.start_time).total_seconds() / 60)
    user.add_xp(activity.duration)  # 1 XP за каждую минуту
    db.session.commit()

    return jsonify({
        'message': 'Activity stopped successfully',
        'duration': activity.duration,
        'xp_earned': activity.duration
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

    for activity in activities:
        # Статистика по дням
        date = activity.end_time.date().isoformat()
        daily_stats[date] = daily_stats.get(date, 0) + activity.duration

        # Статистика по категориям
        if activity.category:
            category_stats[activity.category] = category_stats.get(activity.category, 0) + activity.duration

    return jsonify({
        'total_duration': total_duration,
        'daily_stats': daily_stats,
        'category_stats': category_stats,
        'activities_count': len(activities)
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

@app.route('/webhook', methods=['POST'])
async def webhook():
    data = request.get_json()
    update = Update.de_json(data, bot)
    
    if update.message and update.message.web_app_data:
        web_app_data = update.message.web_app_data.data
        try:
            data = json.loads(web_app_data)
            user_id = update.message.from_user.id
            activity = data.get('activity')
            duration = data.get('duration')
            
            if activity and duration:
                # Находим или создаем пользователя
                user = User.query.filter_by(telegram_id=str(user_id)).first()
                if not user:
                    user = User(telegram_id=str(user_id), username=update.message.from_user.username)
                    db.session.add(user)
                    db.session.commit()
                
                # Создаем новый трек времени
                track = TimeTrack(
                    user_id=user.id,
                    activity=activity,
                    start_time=datetime.utcnow(),
                    duration=duration * 60  # конвертируем минуты в секунды
                )
                db.session.add(track)
                db.session.commit()
                
                # Отправляем подтверждение пользователю
                await bot.send_message(
                    chat_id=user_id,
                    text=f"✅ Активность '{activity}' на {duration} минут успешно сохранена!"
                )
        except Exception as e:
            print(f"Error in webhook: {e}")
            await bot.send_message(
                chat_id=update.message.from_user.id,
                text="❌ Произошла ошибка при сохранении активности. Попробуйте еще раз."
            )
    
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 