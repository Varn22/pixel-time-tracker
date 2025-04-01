# Pixel Time Tracker

Pixel Time Tracker - это современное приложение для отслеживания времени в Telegram, которое поможет вам быть более продуктивным и организованным.

## Возможности

- ⏱ Отслеживание времени по категориям
- 📊 Подробная статистика и аналитика
- 🎯 Система уровней и достижений
- 🔔 Умные уведомления
- 🌙 Поддержка темной темы
- 📱 Адаптивный веб-интерфейс
- 🔄 Синхронизация с Telegram

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/pixel-time-tracker.git
cd pixel-time-tracker
```

2. Создайте виртуальное окружение и активируйте его:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл `.env` и добавьте необходимые переменные окружения:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
WEBAPP_URL=http://localhost:5000
SECRET_KEY=your_secret_key_here
```

5. Инициализируйте базу данных:
```bash
python reset_db.py
```

6. Запустите приложение (в двух разных терминалах):

Терминал 1 (веб-приложение):
```bash
python web.py
```

Терминал 2 (Telegram бот):
```bash
python bot.py
```

## Использование

1. Найдите бота в Telegram: @your_bot_username
2. Отправьте команду `/start`
3. Используйте кнопку "Открыть трекер" для доступа к веб-интерфейсу
4. Начните отслеживать свое время!

## Команды бота

- `/start` - Начать работу с ботом
- `/help` - Показать справку
- `/stats` - Показать статистику
- `/profile` - Информация о профиле
- `/settings` - Настройки уведомлений

## Разработка

### Структура проекта

```
pixel-time-tracker/
├── app.py              # Основной файл приложения
├── web.py             # Запуск веб-приложения
├── bot.py             # Запуск Telegram бота
├── reset_db.py         # Скрипт для сброса базы данных
├── requirements.txt    # Зависимости проекта
├── .env               # Переменные окружения
├── static/            # Статические файлы
│   ├── css/          # Стили
│   └── js/           # JavaScript
└── templates/         # HTML шаблоны
```

### Технологии

- Python 3.8+
- Flask
- SQLAlchemy
- python-telegram-bot
- HTML5/CSS3
- JavaScript

## Лицензия

MIT License 