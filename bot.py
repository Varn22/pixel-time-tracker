from app import application

if __name__ == '__main__':
    print("Запуск Telegram бота...")
    application.run_polling(drop_pending_updates=True) 