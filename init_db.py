import sqlite3
import os
from werkzeug.security import generate_password_hash

# Путь к БД
DATABASE_PATH = os.getenv('DATABASE_PATH', 'database.db')

def get_db_connection():
    """Подключение к базе данных"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация базы данных: создание таблиц и начальных данных"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # === ТАБЛИЦЫ ===
    
    # 1. Matches (Матчи)
    c.execute('''CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, 
        time TEXT, 
        league TEXT,
        team1 TEXT,  
        team2 TEXT, 
        search_tags TEXT, 
        is_next INTEGER DEFAULT 0
    )''')
    
    # 2. News (Новости)
    c.execute('''CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, 
        title TEXT, 
        img_url TEXT, 
        search_tags TEXT
    )''')
    
    # 3. Leagues (Лиги)
    c.execute('''CREATE TABLE IF NOT EXISTS leagues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        category TEXT,
        description TEXT,
        teams_count INTEGER,
        stage TEXT,
        is_active INTEGER DEFAULT 1
    )''')
    
    # 4. Documents (Документы)
    c.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        file_path TEXT,
        file_type TEXT,
        category TEXT,
        upload_date TEXT,
        is_public INTEGER DEFAULT 1
    )''')
    
    # 5. Players (Игроки)
    c.execute('''CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        photo_url TEXT,
        team TEXT,
        position TEXT,
        stats_points INTEGER DEFAULT 0,
        stats_matches INTEGER DEFAULT 0,
        birth_year INTEGER,
        region TEXT,
        is_active INTEGER DEFAULT 1
    )''')
    
    # 6. Referees (Судьи)
    c.execute('''CREATE TABLE IF NOT EXISTS referees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        photo_url TEXT,
        category TEXT,
        experience_years INTEGER,
        region TEXT,
        is_active INTEGER DEFAULT 1
    )''')
    
    # 7. Hippodromes (Ипподромы)
    c.execute('''CREATE TABLE IF NOT EXISTS hippodromes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        location TEXT,
        map_url TEXT,
        capacity INTEGER,
        description TEXT,
        photo_url TEXT
    )''')
    
    # 8. Videos (Видео)
    c.execute('''CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        video_url TEXT,
        thumbnail TEXT,
        match_id INTEGER,
        upload_date TEXT,
        views INTEGER DEFAULT 0,
        category TEXT
    )''')
    
    # 9. Photo Albums (Фото-альбомы)
    c.execute('''CREATE TABLE IF NOT EXISTS photo_albums (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        match_id INTEGER,
        cover_url TEXT,
        upload_date TEXT,
        photo_count INTEGER DEFAULT 0
    )''')
    
    # 10. Photos (Фото)
    c.execute('''CREATE TABLE IF NOT EXISTS photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        album_id INTEGER,
        photo_url TEXT,
        caption TEXT,
        FOREIGN KEY (album_id) REFERENCES photo_albums (id)
    )''')
    
    # 11. Users (Пользователи)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # === НАЧАЛЬНЫЕ ДАННЫЕ ===
    
    # 1. Лиги
    if not c.execute('SELECT 1 FROM leagues LIMIT 1').fetchone():
        leagues_data = [
            ('Жогорку лига', 'Лига', 'Элиталык дивизион', 12, 'Чемпионат', 1),
            ('Биринчи лига', 'Лига', 'Экинчи дивизион', 18, 'Плей-офф', 1),
            ('Экинчи лига', 'Лига', 'Үчүнчү дивизион', 24, 'Группалык этап', 1),
            ('Легендалар лигасы', 'Лига', 'Ветерандар үчүн', 8, 'Достук оюндары', 1),
            ('Жаштар лигасы', 'Лига', '18-23 жаш', 16, 'Чемпионат', 1),
            ('Студенттик лига', 'Лига', 'ЖОЖ командалары', 20, 'Чемпионат', 1),
            ('Сүйүүчүлөр лигасы', 'Лига', 'Аматорлор', 32, 'Турнир', 1),
            ('Мамлекеттик кызмат лигасы', 'Лига', 'Мамлекеттик кызматкерлер', 14, 'Чемпионат', 1),
            ('Нооруз кубогу', 'Кубок', 'Жазгы майрамдык турнир', 16, 'Плей-офф', 1),
            ('Жеңиш Кубогу', 'Кубок', '9-майга арналган', 12, 'Финалдык этап', 1),
            ('Эгемендүүлүк кубогу', 'Кубок', 'Эгемендүүлүк күнүнө', 16, 'Чейрек финал', 1),
        ]
        c.executemany(
            'INSERT INTO leagues (name, category, description, teams_count, stage, is_active) VALUES (?, ?, ?, ?, ?, ?)',
            leagues_data
        )
        print("✅ Лиги добавлены")
    
    # 2. Документы
    if not c.execute('SELECT 1 FROM documents LIMIT 1').fetchone():
        docs_data = [
            ('Улак-тартыш федерациясынын Уставы', 'Негизги документ', '#', 'pdf', 'Устав', '15.05.2026', 1),
            ('Улак-тартыш оюнун эрежелери', 'Расмий эрежелер жана талаптар', '#', 'pdf', 'Правила', '10.04.2026', 1),
            ('Жекеме-жеке эрежелери', 'Жеке чемпионаттын регламенти', '#', 'pdf', 'Правила', '10.04.2026', 1),
            ('Трансфердик эрежелер', 'Оюнчуларды которуу тартиби', '#', 'pdf', 'Трансфер', '01.03.2026', 1),
            ('Нооруз кубогу-2026 жобосу', 'Турнирдин положениеси', '#', 'pdf', 'Положение турнира', '01.03.2026', 1),
        ]
        c.executemany(
            'INSERT INTO documents (title, description, file_path, file_type, category, upload_date, is_public) VALUES (?, ?, ?, ?, ?, ?, ?)',
            docs_data
        )
        print("✅ Документы добавлены")
    
    # 3. Игроки
    if not c.execute('SELECT 1 FROM players LIMIT 1').fetchone():
        players_data = [
            ('Айбек Абдыразаков', 'https://placehold.co/300x400/1e293b/38bdf8?text=AA', 'Достук', 'Чабуулчу', 42, 18, 1995, 'Бишкек', 1),
            ('Руслан Ниязов', 'https://placehold.co/300x400/1e293b/38bdf8?text=RN', 'Ынтымак', 'Капитан', 38, 20, 1992, 'Ош', 1),
            ('Бектур Токтосунов', 'https://placehold.co/300x400/1e293b/38bdf8?text=BT', 'Сары-Өзөн', 'Коргоочу', 31, 17, 1998, 'Нарын', 1),
            ('Нурлан Сыдыков', 'https://placehold.co/300x400/1e293b/38bdf8?text=NS', 'Мурас', 'Улакчы', 29, 15, 2000, 'Талас', 1),
        ]
        c.executemany(
            'INSERT INTO players (name, photo_url, team, position, stats_points, stats_matches, birth_year, region, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            players_data
        )
        print("✅ Игроки добавлены")
    
    # 4. Админ по умолчанию
    admin_email = os.getenv('ADMIN_EMAIL', 'admin@ulaktartysh.kg')
    admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
    
    if not c.execute('SELECT id FROM users WHERE email = ?', (admin_email,)).fetchone():
        c.execute(
            'INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, ?, ?)',
            ('Администратор', admin_email, generate_password_hash(admin_password), 'admin')
        )
        print("✅ Администратор создан")
        print(f"   Email: {admin_email}")
        print(f"   Пароль: {admin_password}")
    
    # Сохраняем изменения
    conn.commit()
    conn.close()
    print("\n✅ База данных успешно инициализирована!")

# Запуск при прямом вызове файла
if __name__ == '__main__':
    init_db()