from app import app, init_db

if __name__ == '__main__':
    print("Инициализация базы данных...")
    init_db()
    print("Запуск веб-приложения...")
    app.run(debug=True) 