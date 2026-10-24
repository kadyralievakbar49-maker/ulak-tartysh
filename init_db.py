import sqlite3
import os
from werkzeug.security import generate_password_hash

# Путь к БД
DATABASE_PATH = os.getenv('DATABASE_PATH', 'database.db')
DOCUMENT_SEED = [
    ('Положение игры «Улак Тартыш» Редакция №1', 'rules', '2026-04-23', '', 'Официальные правила игры Улак Тартыш, утверждённые Федерацией. Определяет порядок проведения соревнований, права и обязанности участников, судей и организаторов.', 'Положение_Улак_Тартыш_Редакция_№1.pdf'),
    ('Заявка команды на участие', 'applications', '2026-01-15', '', 'Бланк заявки команды для участия в турнирах. Включает состав команды, подписи тренера, капитана и врача.', '№1. заявка команд (2).pdf'),
    ('Состав команды (Форма №8)', 'forms', '2026-01-15', '', 'Форма состава команды с игроками и лошадьми. Указывается ФИО, год рождения, кличка лошади.', '№8 Состав команды-2.pdf'),
    ('Выписка Минюст Федерации', 'legal', '2026-04-16', '328117-3301-ОО', 'Выписка из Министерства Юстиции КР о регистрации ОО «Федерация Улак Тартыш». Рег. номер 328117-3301-ОО.', '№3_Выписка_Мин_Юст_Фед_Улак_Тартыш.pdf'),
    ('Доверенность', 'legal', '2026-04-07', '', 'Доверенность на представление интересов Федерации в государственных органах КР.', '№2. Scanned 7 Apr 2026 at 09_05_49.pdf'),
    ('Протокол №1 о создании Федерации', 'legal', '2026-04-16', '', 'Протокол учредительного собрания о создании Общественного объединения «Федерация Улак Тартыш».', '№_4_Протокол_№1_о_Создании_ОО_Федерация_Улак_Тартыш.pdf'),
    ('ULAK TARTYSH (международный стандарт)', 'rules', '2026-04-23', '', 'Международный стандарт игры Улак-Тартыш (Кок-Бору). Основные правила и регламент международных соревнований.', 'ULAK TARTYSH.pdf'),
    ('Улак Тартыш эрежеси', 'rules', '2026-04-23', '', 'Правила игры на кыргызском языке.', 'УлакТартыш эрежесиd.pdf'),
]

def ensure_column(cursor, table, column, definition):
    columns = {row[1] for row in cursor.execute(f'PRAGMA table_info({table})').fetchall()}
    if column not in columns:
        cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')

def ensure_email_confirmations_schema(cursor):
    required_columns = {'id', 'user_id', 'email', 'token_hash', 'expires_at', 'created_at', 'used_at'}
    existing_columns = {row[1] for row in cursor.execute('PRAGMA table_info(email_confirmations)').fetchall()}
    if existing_columns and not required_columns.issubset(existing_columns):
        cursor.execute('DROP TABLE email_confirmations')
    cursor.execute('''CREATE TABLE IF NOT EXISTS email_confirmations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        email TEXT NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        used_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')

def document_size(filename):
    path = os.path.join('static', 'documents', filename)
    return os.path.getsize(path) if os.path.exists(path) else 0

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

    c.execute('''CREATE TABLE IF NOT EXISTS match_archive (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team1_name TEXT NOT NULL,
        team2_name TEXT NOT NULL,
        team1_score INTEGER DEFAULT 0,
        team2_score INTEGER DEFAULT 0,
        match_date TEXT NOT NULL,
        match_time TEXT,
        location TEXT,
        league TEXT,
        season TEXT,
        tournament_name TEXT,
        description TEXT,
        video_url TEXT,
        photo_gallery TEXT,
        winner_team TEXT,
        is_playoff INTEGER DEFAULT 0,
        stage TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_match_archive_date ON match_archive(match_date DESC, created_at DESC)')
    
    # 2. News (Новости)
    c.execute('''CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, 
        title TEXT, 
        img_url TEXT, 
        search_tags TEXT,
        body TEXT,
        is_published INTEGER DEFAULT 1,
        meta_title TEXT DEFAULT '',
        meta_description TEXT DEFAULT ''
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
        title TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'regulations',
        description TEXT,
        file_url TEXT NOT NULL DEFAULT '',
        file_name TEXT,
        file_size INTEGER DEFAULT 0,
        official_date TEXT,
        reg_number TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        file_path TEXT,
        file_type TEXT,
        upload_date TEXT,
        is_public INTEGER DEFAULT 1
    )''')
    ensure_column(c, 'documents', 'file_url', "TEXT DEFAULT ''")
    ensure_column(c, 'documents', 'file_name', "TEXT DEFAULT ''")
    ensure_column(c, 'documents', 'file_size', 'INTEGER DEFAULT 0')
    ensure_column(c, 'documents', 'official_date', "TEXT DEFAULT ''")
    ensure_column(c, 'documents', 'reg_number', "TEXT DEFAULT ''")
    ensure_column(c, 'documents', 'is_active', 'INTEGER DEFAULT 1')
    ensure_column(c, 'documents', 'created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    ensure_column(c, 'documents', 'file_path', "TEXT DEFAULT ''")
    ensure_column(c, 'documents', 'file_type', "TEXT DEFAULT 'pdf'")
    ensure_column(c, 'documents', 'upload_date', "TEXT DEFAULT ''")
    ensure_column(c, 'documents', 'is_public', 'INTEGER DEFAULT 1')

    c.execute('''CREATE TABLE IF NOT EXISTS rules_sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        order_num INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS regulations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        file_path TEXT,
        regulation_date TEXT,
        order_num INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player TEXT NOT NULL,
        from_team TEXT NOT NULL,
        to_team TEXT NOT NULL,
        transfer_date TEXT NOT NULL,
        status TEXT DEFAULT 'На рассмотрении'
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

    c.execute('''CREATE TABLE IF NOT EXISTS horses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        photo_url TEXT,
        photo_urls TEXT DEFAULT '',
        breed TEXT,
        age INTEGER,
        color TEXT,
        speed INTEGER DEFAULT 0,
        stamina INTEGER DEFAULT 0,
        points INTEGER DEFAULT 0,
        price INTEGER,
        description TEXT,
        phone TEXT DEFAULT '',
        is_for_sale INTEGER DEFAULT 0,
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
        archive_match_id INTEGER,
        team_id INTEGER,
        tournament_name TEXT DEFAULT '',
        upload_date TEXT,
        views INTEGER DEFAULT 0,
        category TEXT,
        description TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1
    )''')
    
    # 9. Photo Albums (Фото-альбомы)
    c.execute('''CREATE TABLE IF NOT EXISTS photo_albums (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        match_id INTEGER,
        archive_match_id INTEGER,
        team_id INTEGER,
        tournament_name TEXT DEFAULT '',
        cover_url TEXT,
        upload_date TEXT,
        photo_count INTEGER DEFAULT 0,
        description TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1,
        meta_title TEXT DEFAULT '',
        meta_description TEXT DEFAULT ''
    )''')
    
    # 10. Photos (Фото)
    c.execute('''CREATE TABLE IF NOT EXISTS photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        album_id INTEGER,
        photo_url TEXT,
        caption TEXT,
        order_num INTEGER DEFAULT 0,
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
        is_verified INTEGER DEFAULT 1,
        email_verified_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    ensure_column(c, 'users', 'role', "TEXT DEFAULT 'user'")
    ensure_column(c, 'users', 'is_active', 'INTEGER DEFAULT 1')
    ensure_column(c, 'users', 'is_verified', 'INTEGER DEFAULT 1')
    ensure_column(c, 'users', 'email_verified_at', 'TEXT')
    c.execute("UPDATE users SET is_verified = 1 WHERE is_verified IS NULL")

    ensure_email_confirmations_schema(c)
    
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
        docs_data = []
        for title, category, official_date, reg_number, description, filename in DOCUMENT_SEED:
            docs_data.append((
                title,
                category,
                description,
                f'/documents/{filename}',
                filename,
                document_size(filename),
                official_date,
                reg_number,
                1,
                f'static/documents/{filename}',
                'pdf',
                official_date,
                1,
            ))
        c.executemany(
            '''INSERT INTO documents
               (title, category, description, file_url, file_name, file_size, official_date,
                reg_number, is_active, file_path, file_type, upload_date, is_public)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
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
