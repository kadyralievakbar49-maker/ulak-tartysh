import os
import sqlite3
import random
import smtplib
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from uuid import uuid4
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# File extension sets
IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
VIDEO_EXTENSIONS = {'mp4', 'mov', 'webm', 'avi', 'mkv'}
DOCUMENT_EXTENSIONS = {'pdf', 'docx'}

# SMTP configuration (read from environment)
SMTP_HOST = os.getenv('SMTP_HOST', '')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USER or 'noreply@example.com')

def get_db_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def today_iso():
    """Return today's date in ISO format."""
    return date.today().isoformat()

def send_confirmation_email(email, code):
    """Send a confirmation email."""
    subject = 'Код подтверждения регистрации'
    text = f'Ваш код подтверждения: {code}\n\nКод действует 15 минут.'

    if not SMTP_HOST:
        print(f"[EMAIL DEV] Код подтверждения для {email}: {code}")
        return False

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = SMTP_FROM
    message['To'] = email
    message.set_content(text)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        if SMTP_USER and SMTP_PASSWORD:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(message)

    return True

def save_uploaded_file(file, allowed_extensions):
    """Save an uploaded file and return its path."""
    if not file or file.filename == '' or not allowed_file(file.filename, allowed_extensions):
        return ''

    original = secure_filename(file.filename)
    
    # Check that there is an extension
    if '.' not in original:
        return ''
    
    extension = original.rsplit('.', 1)[1].lower()
    filename = f"{uuid4().hex}.{extension}"
    filepath = os.path.join('static/uploads', filename)
    file.save(filepath)
    return f"/{filepath}"

def allowed_file(filename, allowed_extensions=None):
    """Check if the file extension is allowed."""
    extensions = allowed_extensions or (DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS | VIDEO_EXTENSIONS)
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

def form_int_or_none(value):
    """Convert a string to int or return None if not possible."""
    return int(value) if value and str(value).isdigit() else None

def site_content():
    """Return static site content for templates."""
    official_documents = [
        {'title': 'Улак тартыш эрежеси', 'category': 'Правила', 'file': 'docs/ulak-tartysh-rules.pdf'},
        {'title': 'ULAK TARTYSH', 'category': 'Международный документ', 'file': 'docs/ulak-tartysh.pdf'},
        {'title': 'Положение Улак тартыш, редакция №1', 'category': 'Положение', 'file': 'docs/ulak-tartysh-regulation-1.pdf'},
        {'title': 'Заявка команд №1', 'category': 'Заявки', 'file': 'docs/team-application-1.pdf'},
        {'title': 'Заявка команд №1, копия', 'category': 'Заявки', 'file': 'docs/team-application-1-copy.pdf'},
        {'title': 'Состав команды №8', 'category': 'Команды', 'file': 'docs/team-roster-8.pdf'},
        {'title': 'Выписка Минюст Федерации Улак тартыш', 'category': 'Уставные документы', 'file': 'docs/minjust-extract.pdf'},
        {'title': 'Протокол №1 о создании федерации', 'category': 'Уставные документы', 'file': 'docs/federation-protocol-4.pdf'},
        {'title': 'Протокол №1 о создании федерации, копия', 'category': 'Уставные документы', 'file': 'docs/federation-protocol-4-copy.pdf'},
        {'title': 'Сканированный документ №2', 'category': 'Документы', 'file': 'docs/scanned-2026-04-07.pdf'},
        {'title': 'Документ 89', 'category': 'Документы', 'file': 'docs/document-89.pdf'},
    ]

    hippodromes_public = [
        {'name': 'Бишкек ипподрому', 'location': 'Бишкек', 'address': 'ул. Масалиева, спортивная зона', 'capacity': '12 000', 'surface': 'Кумдуу талаа', 'map_url': 'https://maps.google.com/?q=Bishkek+hippodrome', 'description': 'Расмий беттештер, финалдык оюндар жана федерациялык турнирлер үчүн негизги аянтча.'},
        {'name': 'Ош ипподрому', 'location': 'Ош', 'address': 'Ош шаары, ипподром аймагы', 'capacity': '8 500', 'surface': 'Табигый талаа', 'map_url': 'https://maps.google.com/?q=Osh+hippodrome', 'description': 'Түштүк аймактагы чемпионаттар жана жаштар лигалары үчүн колдонулат.'},
        {'name': 'Чолпон-Ата ат майданы', 'location': 'Ысык-Көл', 'address': 'Чолпон-Ата, спорт комплекси', 'capacity': '10 000', 'surface': 'Кең талаа', 'map_url': 'https://maps.google.com/?q=Cholpon-Ata+hippodrome', 'description': 'Ири майрамдык оюндарга, эл аралык жолугушууларга жана көргөзмө матчтарга ылайыкталган.'},
    ]

    referees_public = [
        {'name': 'Нурбек Осмонов', 'category': 'Башкы калыс', 'experience': 12, 'region': 'Бишкек', 'assignment': 'Жогорку лига'},
        {'name': 'Тилек Матраимов', 'category': 'Улуттук категория', 'experience': 9, 'region': 'Ош', 'assignment': 'Биринчи лига'},
        {'name': 'Айжан Сыдыкова', 'category': 'Катчы-калыс', 'experience': 7, 'region': 'Чүй', 'assignment': 'Кубок оюндары'},
        {'name': 'Бакыт Эргешов', 'category': 'Аймактык калыс', 'experience': 6, 'region': 'Нарын', 'assignment': 'Жаштар лигасы'},
    ]

    teams_public = [
        {'name': 'Ынтымак', 'region': 'Ош', 'league': 'Жогорку лига', 'players': 18, 'wins': 12, 'points': 36},
        {'name': 'Достук', 'region': 'Талас', 'league': 'Жогорку лига', 'players': 20, 'wins': 10, 'points': 31},
        {'name': 'Сары-Өзөн', 'region': 'Чүй', 'league': 'Биринчи лига', 'players': 16, 'wins': 8, 'points': 25},
        {'name': 'Намыс', 'region': 'Нарын', 'league': 'Биринчи лига', 'players': 17, 'wins': 7, 'points': 22},
    ]

    leadership = [
        {'name': 'Адилет Токтобаев', 'role': 'Президент федерации'},
        {'name': 'Мирбек Сатыбалдиев', 'role': 'Спортивный директор'},
        {'name': 'Айсулуу Касымова', 'role': 'Координатор соревнований'},
    ]

    partners_public = [
        {'name': 'Кыргыз спорт союзу', 'type': 'Стратегиялык өнөктөш'},
        {'name': 'Бишкек мэриясы', 'type': 'Инфраструктура'},
        {'name': 'Улуттук телеканал', 'type': 'Медиа өнөктөш'},
        {'name': 'Жаштар спорту фонду', 'type': 'Социалдык өнөктөш'},
    ]

    accreditation_steps = [
        'Анкетаны толтуруу жана байланыш маалыматтарын көрсөтүү.',
        'Команда, медиа же уюштуруучу статуusun тастыктаган документти тиркөө.',
        'Федерациянын жооптуу кызматкеринен ырастоо алуу.',
        'Оюн күнү бейдж же уруксат кагазын алып кирүү.',
    ]

    return {
        'official_documents': official_documents,
        'hippodromes_public': hippodromes_public,
        'referees_public': referees_public,
        'teams_public': teams_public,
        'leadership': leadership,
        'partners_public': partners_public,
        'accreditation_steps': accreditation_steps,
    }

def init_db():
    """Initialize the database: create tables and initial data."""
    conn = get_db_connection()
    
    conn.execute('''CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, time TEXT, league TEXT,
        team1 TEXT, team2 TEXT, search_tags TEXT, is_next INTEGER DEFAULT 0
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, title TEXT, img_url TEXT, search_tags TEXT
    )''')

    news_columns = {row[1] for row in conn.execute('PRAGMA table_info(news)').fetchall()}
    if 'body' not in news_columns:
        conn.execute('ALTER TABLE news ADD COLUMN body TEXT')

    conn.execute('''CREATE TABLE IF NOT EXISTS leagues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, category TEXT, description TEXT,
        teams_count INTEGER, stage TEXT, is_active INTEGER DEFAULT 1
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, description TEXT, file_path TEXT,
        file_type TEXT, category TEXT, upload_date TEXT, is_public INTEGER DEFAULT 1
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, photo_url TEXT, team TEXT, position TEXT,
        stats_points INTEGER DEFAULT 0, stats_matches INTEGER DEFAULT 0,
        birth_year INTEGER, region TEXT, is_active INTEGER DEFAULT 1
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS horses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        photo_url TEXT,
        breed TEXT,
        age INTEGER,
        color TEXT,
        speed INTEGER DEFAULT 0,
        stamina INTEGER DEFAULT 0,
        points INTEGER DEFAULT 0,
        price INTEGER,
        description TEXT,
        is_for_sale INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS referees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, photo_url TEXT, category TEXT,
        experience_years INTEGER, region TEXT, is_active INTEGER DEFAULT 1
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS hippodromes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, location TEXT, map_url TEXT,
        capacity INTEGER, description TEXT, photo_url TEXT
    )''')

    hippodrome_columns = {row[1] for row in conn.execute('PRAGMA table_info(hippodromes)').fetchall()}
    if 'address' not in hippodrome_columns:
        conn.execute('ALTER TABLE hippodromes ADD COLUMN address TEXT')
    if 'surface' not in hippodrome_columns:
        conn.execute('ALTER TABLE hippodromes ADD COLUMN surface TEXT')

    conn.execute('''CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, video_url TEXT, thumbnail TEXT,
        match_id INTEGER, upload_date TEXT, views INTEGER DEFAULT 0, category TEXT
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS photo_albums (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, match_id INTEGER, cover_url TEXT,
        upload_date TEXT, photo_count INTEGER DEFAULT 0
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        album_id INTEGER, photo_url TEXT, caption TEXT,
        FOREIGN KEY (album_id) REFERENCES photo_albums (id)
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        is_verified INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )''')

    user_columns = {row[1] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
    if 'is_verified' not in user_columns:
        conn.execute('ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0')

    conn.execute('''CREATE TABLE IF NOT EXISTS email_confirmations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        code TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS ticket_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_name TEXT,
        count INTEGER DEFAULT 1,
        phone TEXT NOT NULL,
        email TEXT,
        status TEXT DEFAULT 'new',
        created_at TEXT NOT NULL
    )''')

    if not conn.execute('SELECT 1 FROM leagues LIMIT 1').fetchone():
        leagues_data = [
            ('Жогорку лига', 'Лига', 'Элиталык дивизион', 12, 'Чемпионат', 1),
            ('Биринчи лига', 'Лига', 'Экинчи дивизион', 18, 'Плей-офф', 1),
            ('Нооруз кубогу', 'Кубок', 'Жазгы майрамдык турнир', 16, 'Плей-офф', 1),
        ]
        conn.executemany('''INSERT INTO leagues (name, category, description, teams_count, stage, is_active) VALUES (?, ?, ?, ?, ?, ?)''', leagues_data)

    if not conn.execute('SELECT 1 FROM players LIMIT 1').fetchone():
        players_data = [
            ('Айбек Абдыразаков', 'https://placehold.co/300x400/1e293b/38bdf8?text=AA', 'Достук', 'Чабуулчу', 42, 18, 1995, 'Бишкек', 1),
            ('Руслан Ниязов', 'https://placehold.co/300x400/1e293b/38bdf8?text=RN', 'Ынтымак', 'Капитан', 38, 20, 1992, 'Ош', 1),
        ]
        conn.executemany('''INSERT INTO players (name, photo_url, team, position, stats_points, stats_matches, birth_year, region, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', players_data)

    if not conn.execute('SELECT 1 FROM horses LIMIT 1').fetchone():
        horses_data = [
            ('Аккула', '', 'Кыргыз жылкысы', 7, 'Ак боз', 92, 88, 145, 850000, 'Финалдык оюндарда туруктуу көрсөткүч берген күлүк.', 1, 1),
            ('Карагер', '', 'Тоолук аргымак', 6, 'Кара тору', 86, 94, 132, 720000, 'Чыдамкайлыгы күчтүү, узак оюндарга ылайыктуу.', 1, 1),
            ('Шамал', '', 'Аргымак', 5, 'Күрөң', 95, 82, 118, 650000, 'Ылдам чабуулдарда өзүн жакшы көрсөтөт.', 0, 1),
        ]
        conn.executemany('''INSERT INTO horses (name, photo_url, breed, age, color, speed, stamina, points, price, description, is_for_sale, is_active)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', horses_data)

    conn.commit()
    conn.close()