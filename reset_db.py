from app import app, db

def reset_database():
    with app.app_context():
        # Удаляем все таблицы
        db.drop_all()
        # Создаем таблицы заново
        db.create_all()
        print("База данных успешно сброшена!")

if __name__ == '__main__':
    reset_database() 