from flask import Flask, request, jsonify, render_template, session, redirect, url_for, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
import os
import json
import logging
from waitress import serve

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

# Модели данных
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
    daily_goal = db.Column(db.Integer, default=120)
    break_reminder = db.Column(db.Integer, default=60)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    activities = db.relationship('Activity', backref='user', lazy=True)
    categories = db.relationship('Category', backref='user', lazy=True)
    achievements = db.relationship('Achievement', backref='user', lazy=True)

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
    duration = db.Column(db.Integer)
    notes = db.Column(db.Text)
    productivity = db.Column(db.Integer)
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
            db_url = os.getenv('DATABASE_URL', '')
            if db_url:
                masked_url = db_url.replace(db_url.split('@')[0].split(':')[2], '****')
                logger.info(f"Attempting to connect to database: {masked_url}")
            else:
                logger.error("DATABASE_URL not found in environment variables")
                return
            
            db.engine.connect()
            logger.info("Database connection successful")
            
            db.create_all()
            logger.info("Database tables created successfully")
            
            try:
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

# API endpoints
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
            
            try:
                default_categories = ['Работа', 'Учеба', 'Отдых', 'Спорт', 'Другое']
                for category_name in default_categories:
                    category = Category(name=category_name, user_id=db_user.id)
                    db.session.add(category)
                db.session.commit()
                logger.info(f"Default categories created for user {telegram_id}.")
            except Exception as cat_e:
                db.session.rollback()
                logger.error(f"Error creating default categories for user {telegram_id}: {str(cat_e)}")

        response_data = {
            'id': db_user.id,
            'telegram_id': db_user.telegram_id,
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

# Добавьте остальные API endpoints здесь...

def run():
    init_db()
    port = int(os.getenv('PORT', 8000))
    serve(app, host='0.0.0.0', port=port)

if __name__ == '__main__':
    run() 