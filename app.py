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
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///timetracker.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', str(uuid.uuid4()))
db = SQLAlchemy(app)

# Модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.String(50), unique=True, nullable=False)
    username = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.now)
    time_tracks = db.relationship('TimeTrack', backref='user', lazy=True)
    total_time = db.Column(db.Integer, default=0)
    achievements = db.relationship('Achievement', backref='user', lazy=True)

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
    description = db.Column(db.String(200))
    earned_at = db.Column(db.DateTime, default=datetime.now)
    icon = db.Column(db.String(50))

# Инициализация бота Telegram
bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))

@app.route('/')
def index():
    init_data = request.args.get('initData')
    if init_data:
        try:
            data = json.loads(init_data)
            user = data.get('user', {})
            telegram_id = str(user.get('id'))
            username = user.get('username', 'Пользователь')
            
            # Автоматическая регистрация пользователя
            db_user = User.query.filter_by(telegram_id=telegram_id).first()
            if not db_user:
                db_user = User(telegram_id=telegram_id, username=username)
                db.session.add(db_user)
                db.session.commit()
                
                # Создаем начальные достижения
                achievements = [
                    Achievement(user_id=db_user.id, name='Первый трек', description='Создайте свой первый трек времени', icon='🎯'),
                    Achievement(user_id=db_user.id, name='Мастер времени', description='Отслеживайте время 7 дней подряд', icon='⏰'),
                    Achievement(user_id=db_user.id, name='Профессионал', description='Накопите 100 часов трекинга', icon='🏆')
                ]
                db.session.bulk_save_objects(achievements)
                db.session.commit()
            
            session['user_id'] = db_user.id
            session['username'] = db_user.username
            return render_template('index.html', user=db_user)
        except Exception as e:
            print(f"Error processing initData: {e}")
    
    return render_template('index.html')

@app.route('/api/track', methods=['POST'])
def track_time():
    data = request.json
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401
        
    activity = data.get('activity')
    category = data.get('category')
    tags = data.get('tags')
    
    if not activity:
        return jsonify({'error': 'Missing activity'}), 400
    
    track = TimeTrack(
        user_id=user_id,
        activity=activity,
        category=category,
        tags=tags,
        start_time=datetime.now()
    )
    db.session.add(track)
    db.session.commit()
    
    return jsonify({'message': 'Time tracking started'})

@app.route('/api/stop', methods=['POST'])
def stop_tracking():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401
    
    track = TimeTrack.query.filter_by(
        user_id=user_id,
        end_time=None
    ).first()
    
    if track:
        track.end_time = datetime.now()
        track.duration = int((track.end_time - track.start_time).total_seconds())
        
        # Обновляем общее время пользователя
        user = User.query.get(user_id)
        user.total_time += track.duration
        
        # Проверяем достижения
        check_achievements(user)
        
        db.session.commit()
        
        # Отправка уведомления в Telegram
        asyncio.run(bot.send_message(
            chat_id=user.telegram_id,
            text=f'Трек времени завершен!\nАктивность: {track.activity}\nДлительность: {track.duration} секунд'
        ))
        
        return jsonify({'message': 'Time tracking stopped'})
    
    return jsonify({'error': 'No active tracking found'}), 404

@app.route('/api/stats')
def get_stats():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401
        
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    tracks = TimeTrack.query.filter_by(user_id=user_id).all()
    stats = {
        'total_tracks': len(tracks),
        'total_duration': user.total_time,
        'activities': {},
        'categories': {},
        'daily_stats': get_daily_stats(user_id)
    }
    
    for track in tracks:
        if track.activity not in stats['activities']:
            stats['activities'][track.activity] = 0
        stats['activities'][track.activity] += track.duration or 0
        
        if track.category:
            if track.category not in stats['categories']:
                stats['categories'][track.category] = 0
            stats['categories'][track.category] += track.duration or 0
    
    return jsonify(stats)

def get_daily_stats(user_id):
    today = datetime.now().date()
    tracks = TimeTrack.query.filter(
        TimeTrack.user_id == user_id,
        TimeTrack.start_time >= today
    ).all()
    
    return {
        'total_duration': sum(track.duration or 0 for track in tracks),
        'track_count': len(tracks)
    }

def check_achievements(user):
    # Проверяем достижение "Мастер времени"
    if user.total_time >= 360000:  # 100 часов
        achievement = Achievement.query.filter_by(
            user_id=user.id,
            name='Профессионал'
        ).first()
        if not achievement.earned_at:
            achievement.earned_at = datetime.now()
            db.session.commit()
            
            # Отправляем уведомление о достижении
            asyncio.run(bot.send_message(
                chat_id=user.telegram_id,
                text=f'🎉 Поздравляем! Вы получили достижение "{achievement.name}"!\n{achievement.description}'
            ))

@app.route('/webhook', methods=['POST'])
async def webhook():
    data = request.get_json()
    update = Update.de_json(data, bot)
    
    if update.message and update.message.web_app_data:
        web_app_data = update.message.web_app_data.data
        # Обработка данных из веб-приложения
        try:
            data = json.loads(web_app_data)
            user_id = update.message.from_user.id
            activity = data.get('activity')
            duration = data.get('duration')
            
            if activity and duration:
                # Сохраняем активность в базу данных
                new_activity = Activity(
                    user_id=user_id,
                    activity=activity,
                    duration=duration,
                    date=datetime.utcnow()
                )
                db.session.add(new_activity)
                db.session.commit()
                
                # Отправляем подтверждение пользователю
                await bot.send_message(
                    chat_id=user_id,
                    text=f"✅ Активность '{activity}' на {duration} минут успешно сохранена!"
                )
        except Exception as e:
            await bot.send_message(
                chat_id=update.message.from_user.id,
                text="❌ Произошла ошибка при сохранении активности. Попробуйте еще раз."
            )
    
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 