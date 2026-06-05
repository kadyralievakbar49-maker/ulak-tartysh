from flask import Flask, Blueprint, render_template, request, jsonify, redirect, url_for, session, send_from_directory
import sqlite3
import os
import logging
import re
from markupsafe import Markup, escape
from datetime import date, datetime
from uuid import uuid4
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
from PIL import Image, ImageOps

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)  # ✅ ИСПРАВЛЕНО
pages_bp = Blueprint('pages', __name__)
app.secret_key = os.getenv('SECRET_KEY', 'super_secret_key_for_sessions')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

# Initialize CSRF protection
csrf = CSRFProtect(app)

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
VIDEO_EXTENSIONS = {'mp4', 'mov', 'webm', 'avi', 'mkv'}
DOCUMENT_EXTENSIONS = {'pdf', 'docx'}
HORSE_PHOTO_PLACEHOLDER = 'https://placehold.co/800x600/1a2744/f5b041?text=Horse'
DEFAULT_HOMEPAGE_SETTINGS = {
    'section_name': 'hero',
    'title': 'Улак тартыш оюндарын жаңы деңгээлде көрүңүз',
    'subtitle': 'Расмий портал',
    'description': 'Матчтардын календары, лигалар, оюнчулар, жаңылыктар жана медиа бир жерде.',
    'button1_text': 'Оюндарды көрүү',
    'button1_link': '#matches',
    'button2_text': 'Жаңылыктар',
    'button2_link': '#news',
    'background_image': '/static/img/slider/slide1.jpg',
    'overlay_color': 'linear-gradient(135deg, rgba(26, 39, 68, 0.58) 0%, rgba(26, 39, 68, 0.36) 55%, rgba(26, 39, 68, 0.21) 100%)',
    'is_active': 1,
}
DEFAULT_HOMEPAGE_STATS = [
    ('Оюн', 0, 1, 1),
    ('Жаңылык', 3, 2, 1),
    ('Оюнчу', 2, 3, 1),
]

def site_content():
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
        'Команда, медиа же уюштуруучу статусун тастыктаган документти тиркөө.',
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

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def today_iso():
    return date.today().isoformat()

def save_uploaded_file(file, allowed_extensions):
    if not file or file.filename == '' or not allowed_file(file.filename, allowed_extensions):
        return ''

    original = secure_filename(file.filename)
    if '.' not in original:
        return ''

    extension = original.rsplit('.', 1)[1].lower()
    try:
        if extension in IMAGE_EXTENSIONS:
            image = Image.open(file.stream)
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
            if image.mode in ('RGBA', 'LA', 'P'):
                if image.mode == 'P':
                    image = image.convert('RGBA')
                canvas = Image.new('RGB', image.size, (255, 255, 255))
                alpha = image.getchannel('A') if image.mode in ('RGBA', 'LA') else None
                canvas.paste(image, mask=alpha)
                image = canvas
            else:
                image = image.convert('RGB')

            base_name = uuid4().hex
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}.jpg")
            image.save(filepath, 'JPEG', quality=85, optimize=True)

            thumbnail = ImageOps.fit(image, (400, 300), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_thumb.jpg")
            thumbnail.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
            return f"/{filepath}"

        filename = f"{uuid4().hex}.{extension}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return f"/{filepath}"
    except Exception:
        logger.exception("Could not save uploaded file: %s", original)
        return ''

def form_int_or_none(value):
    return int(value) if value and str(value).isdigit() else None

def row_to_dict(row):
    return dict(row) if row else {}

def get_homepage_settings(conn=None):
    owns_connection = conn is None
    if owns_connection:
        conn = get_db_connection()
    settings = conn.execute(
        "SELECT * FROM homepage_settings WHERE section_name = 'hero' AND is_active = 1 LIMIT 1"
    ).fetchone()
    if owns_connection:
        conn.close()
    return settings

def get_homepage_stats(conn=None):
    owns_connection = conn is None
    if owns_connection:
        conn = get_db_connection()
    stats = conn.execute(
        'SELECT * FROM homepage_stats WHERE is_active = 1 ORDER BY order_num, id'
    ).fetchall()
    if owns_connection:
        conn.close()
    return stats

def build_homepage_context():
    conn = get_db_connection()
    page = max(form_int_or_none(request.args.get('page')) or 1, 1)
    per_page = 10
    offset = (page - 1) * per_page
    matches = conn.execute('SELECT * FROM matches ORDER BY date, time').fetchall()
    total_news = conn.execute('SELECT COUNT(*) FROM news').fetchone()[0]
    news = conn.execute('SELECT * FROM news ORDER BY date DESC, id DESC LIMIT ? OFFSET ?', (per_page, offset)).fetchall()
    next_match = conn.execute('SELECT * FROM matches WHERE is_next = 1 LIMIT 1').fetchone()
    if not next_match and matches:
        next_match = matches[0]

    context = {
        'matches': matches,
        'news': news,
        'next_match': next_match,
        'leagues': conn.execute('SELECT * FROM leagues WHERE is_active = 1 ORDER BY category, name').fetchall(),
        'players': conn.execute('SELECT * FROM players WHERE is_active = 1 ORDER BY stats_points DESC LIMIT 4').fetchall(),
        'documents': conn.execute('SELECT * FROM documents WHERE is_public = 1 ORDER BY upload_date DESC').fetchall(),
        'videos': conn.execute('SELECT * FROM videos ORDER BY upload_date DESC LIMIT 4').fetchall(),
        'albums': conn.execute('SELECT * FROM photo_albums ORDER BY upload_date DESC LIMIT 4').fetchall(),
        'homepage_settings': get_homepage_settings(conn),
        'homepage_stats': get_homepage_stats(conn),
        'page': page,
        'per_page': per_page,
        'total_news': total_news,
    }
    conn.close()
    return context

def highlight_text(text, query):
    text = text or ''
    query = (query or '').strip()
    safe_text = escape(text)
    if not query:
        return safe_text

    pattern = re.compile(re.escape(query), re.IGNORECASE)
    highlighted = pattern.sub(lambda match: f'<mark>{escape(match.group(0))}</mark>', str(safe_text))
    return Markup(highlighted)

def search_site(query):
    query = (query or '').strip()
    empty = {'news': [], 'matches': [], 'players': [], 'teams': [], 'horses': []}
    if not query:
        return empty

    term = f"%{query}%"
    conn = get_db_connection()
    results = {
        'news': [row_to_dict(row) for row in conn.execute(
            '''SELECT id, title, body, date, img_url FROM news
               WHERE title LIKE ? OR COALESCE(body, '') LIKE ?
               ORDER BY date DESC, id DESC LIMIT 5''',
            (term, term)).fetchall()],
        'matches': [row_to_dict(row) for row in conn.execute(
            '''SELECT id, date, time, league, team1, team2 FROM matches
               WHERE team1 LIKE ? OR team2 LIKE ? OR league LIKE ?
               ORDER BY date, time LIMIT 5''',
            (term, term, term)).fetchall()],
        'players': [row_to_dict(row) for row in conn.execute(
            '''SELECT id, name, team, position, photo_url, stats_points FROM players
               WHERE is_active = 1 AND (name LIKE ? OR COALESCE(team, '') LIKE ?)
               ORDER BY stats_points DESC, name LIMIT 5''',
            (term, term)).fetchall()],
        'teams': [row_to_dict(row) for row in conn.execute(
            '''SELECT id, name, region, league, photo_url, points FROM teams
               WHERE is_active = 1 AND (name LIKE ? OR COALESCE(region, '') LIKE ?)
               ORDER BY points DESC, name LIMIT 5''',
            (term, term)).fetchall()],
        'horses': [row_to_dict(row) for row in conn.execute(
            '''SELECT id, name, breed, color, photo_url, points FROM horses
               WHERE is_active = 1 AND (name LIKE ? OR COALESCE(breed, '') LIKE ?)
               ORDER BY points DESC, name LIMIT 5''',
            (term, term)).fetchall()],
    }
    conn.close()
    return results

def contact_card_href(card):
    card_type = (card['type'] or '').strip().lower()
    value = (card['value'] or '').strip()
    compact_value = re.sub(r'[\s()+-]', '', value)
    if card_type == 'phone':
        return f"tel:+{compact_value.lstrip('+')}"
    if card_type == 'whatsapp':
        return f"https://wa.me/{compact_value.lstrip('+')}"
    if card_type == 'telegram':
        username = value.replace('https://t.me/', '').replace('http://t.me/', '').lstrip('@')
        return f"https://t.me/{username}"
    if card_type == 'email':
        return f"mailto:{value}"
    if card_type == 'website':
        return value if value.startswith(('http://', 'https://')) else f"https://{value}"
    return value or '#'

def get_active_contact_cards():
    conn = get_db_connection()
    cards = [row_to_dict(row) for row in conn.execute('''SELECT * FROM contact_cards
                                                          WHERE is_active = 1
                                                          ORDER BY order_num, id''').fetchall()]
    conn.close()
    for card in cards:
        card['href'] = contact_card_href(card)
    return cards

def register_user_from_payload(payload):
    payload = payload or {}
    fullname = payload.get('fullname', '').strip()
    email = payload.get('email', '').strip().lower()
    password = payload.get('password', '')
    confirm_password = payload.get('confirm_password', '')

    if not fullname or not email or not password:
        return jsonify({"status": "error", "message": "Заполните все поля регистрации."}), 400
    if len(password) < 6:
        return jsonify({"status": "error", "message": "Пароль должен быть минимум 6 символов."}), 400
    if password != confirm_password:
        return jsonify({"status": "error", "message": "Пароли не совпадают."}), 400

    now = datetime.utcnow()
    password_hash = generate_password_hash(password)
    conn = get_db_connection()
    existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()

    if existing:
        conn.execute('''UPDATE users SET full_name = ?, password_hash = ?
                        WHERE email = ?''', (fullname, password_hash, email))
        user_id = existing['id']
    else:
        conn.execute('''INSERT INTO users (full_name, email, password_hash, created_at)
                        VALUES (?, ?, ?, ?)''',
                     (fullname, email, password_hash, now.isoformat()))
        user_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    conn.commit()
    conn.close()

    session['user_id'] = user_id
    session['user_name'] = fullname
    return jsonify({"status": "success", "message": "Регистрация завершена.", "reload": True})

@app.context_processor
def inject_contact_cards():
    try:
        return {'footer_contact_cards': get_active_contact_cards()}
    except sqlite3.Error:
        return {'footer_contact_cards': []}

def init_db():
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

    player_columns = {row[1] for row in conn.execute('PRAGMA table_info(players)').fetchall()}
    if 'team_id' not in player_columns:
        conn.execute('ALTER TABLE players ADD COLUMN team_id INTEGER')

    conn.execute('''CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        region TEXT,
        league TEXT,
        photo_url TEXT,
        wins INTEGER DEFAULT 0,
        points INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
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
        created_at TEXT NOT NULL
    )''')
    user_columns = {row[1] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
    if 'photo_url' not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN photo_url TEXT DEFAULT ''")
    if 'phone' not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''")

    conn.execute('''CREATE TABLE IF NOT EXISTS ticket_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_name TEXT,
        count INTEGER DEFAULT 1,
        phone TEXT NOT NULL,
        email TEXT,
        status TEXT DEFAULT 'new',
        created_at TEXT NOT NULL
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS homepage_settings (
        id INTEGER PRIMARY KEY,
        section_name TEXT UNIQUE,
        title TEXT,
        subtitle TEXT,
        description TEXT,
        button1_text TEXT,
        button1_link TEXT,
        button2_text TEXT,
        button2_link TEXT,
        background_image TEXT,
        overlay_color TEXT,
        is_active INTEGER DEFAULT 1,
        updated_at TIMESTAMP
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS homepage_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT NOT NULL,
        value INTEGER DEFAULT 0,
        order_num INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        updated_at TIMESTAMP
    )''')

    if not conn.execute("SELECT 1 FROM homepage_settings WHERE section_name = 'hero' LIMIT 1").fetchone():
        conn.execute('''INSERT INTO homepage_settings (
                            section_name, title, subtitle, description,
                            button1_text, button1_link, button2_text, button2_link,
                            background_image, overlay_color, is_active, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (
                         DEFAULT_HOMEPAGE_SETTINGS['section_name'],
                         DEFAULT_HOMEPAGE_SETTINGS['title'],
                         DEFAULT_HOMEPAGE_SETTINGS['subtitle'],
                         DEFAULT_HOMEPAGE_SETTINGS['description'],
                         DEFAULT_HOMEPAGE_SETTINGS['button1_text'],
                         DEFAULT_HOMEPAGE_SETTINGS['button1_link'],
                         DEFAULT_HOMEPAGE_SETTINGS['button2_text'],
                         DEFAULT_HOMEPAGE_SETTINGS['button2_link'],
                         DEFAULT_HOMEPAGE_SETTINGS['background_image'],
                         DEFAULT_HOMEPAGE_SETTINGS['overlay_color'],
                         DEFAULT_HOMEPAGE_SETTINGS['is_active'],
                         datetime.now().isoformat(timespec='seconds'),
                     ))

    if not conn.execute('SELECT 1 FROM homepage_stats LIMIT 1').fetchone():
        conn.executemany('''INSERT INTO homepage_stats (label, value, order_num, is_active, updated_at)
                            VALUES (?, ?, ?, ?, ?)''',
                         [(label, value, order_num, is_active, datetime.now().isoformat(timespec='seconds'))
                          for label, value, order_num, is_active in DEFAULT_HOMEPAGE_STATS])

    conn.execute('''CREATE TABLE IF NOT EXISTS contact_cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        type TEXT NOT NULL,
        value TEXT NOT NULL,
        icon TEXT DEFAULT '☎️',
        color TEXT DEFAULT '#16a34a',
        order_num INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )''')

    if not conn.execute('SELECT 1 FROM contact_cards LIMIT 1').fetchone():
        contact_cards = [
            ('Телефон', 'phone', '+996995544444', '☎️', '#16a34a', 1, 1),
            ('WhatsApp', 'whatsapp', '+996995544444', '💬', '#22c55e', 2, 1),
            ('Telegram', 'telegram', 'ulak_tartysh_official', '✈️', '#229ed9', 3, 1),
            ('Email', 'email', 'ulaktartys@gmail.com', '✉️', '#d32f2f', 4, 1),
        ]
        conn.executemany('''INSERT INTO contact_cards (title, type, value, icon, color, order_num, is_active)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''', contact_cards)

    if not conn.execute('SELECT 1 FROM leagues LIMIT 1').fetchone():
        leagues_data = [
            ('Жогорку лига', 'Лига', 'Элиталык дивизион', 12, 'Чемпионат', 1),
            ('Биринчи лига', 'Лига', 'Экинчи дивизион', 18, 'Плей-офф', 1),
            ('Нооруз кубогу', 'Кубок', 'Жазгы майрамдык турнир', 16, 'Плей-офф', 1),
        ]
        conn.executemany('''INSERT INTO leagues (name, category, description, teams_count, stage, is_active) VALUES (?, ?, ?, ?, ?, ?)''', leagues_data)

    if not conn.execute('SELECT 1 FROM teams LIMIT 1').fetchone():
        teams_data = [
            ('Ынтымак', 'Ош', 'Жогорку лига', 'https://placehold.co/300x300/1a2744/d4a843?text=Ы', 12, 36, 1),
            ('Достук', 'Талас', 'Жогорку лига', 'https://placehold.co/300x300/1a2744/d4a843?text=Д', 10, 31, 1),
            ('Сары-Өзөн', 'Чүй', 'Биринчи лига', 'https://placehold.co/300x300/1a2744/d4a843?text=С', 8, 25, 1),
            ('Намыс', 'Нарын', 'Биринчи лига', 'https://placehold.co/300x300/1a2744/d4a843?text=Н', 7, 22, 1),
        ]
        conn.executemany('''INSERT INTO teams (name, region, league, photo_url, wins, points, is_active)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''', teams_data)

    if not conn.execute('SELECT 1 FROM players LIMIT 1').fetchone():
        players_data = [
            ('Айбек Абдыразаков', 'https://placehold.co/300x400/1e293b/38bdf8?text=AA', 'Достук', 'Чабуулчу', 42, 18, 1995, 'Бишкек', 1),
            ('Руслан Ниязов', 'https://placehold.co/300x400/1e293b/38bdf8?text=RN', 'Ынтымак', 'Капитан', 38, 20, 1992, 'Ош', 1),
        ]
        conn.executemany('''INSERT INTO players (name, photo_url, team, position, stats_points, stats_matches, birth_year, region, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', players_data)

    conn.execute('''UPDATE players
                    SET team_id = (SELECT teams.id FROM teams WHERE teams.name = players.team)
                    WHERE team_id IS NULL AND team IS NOT NULL''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_players_team ON players(team)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_players_team_id ON players(team_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_news_date ON news(date DESC)')

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

@app.route('/')
def home():
    return render_template('index.html', **build_homepage_context())

@app.route('/about')
def about_page():
    return render_template('about.html', **site_content())

@app.route('/rules')
def rules_page():
    return render_template('rules.html')

@app.route('/documents')
def documents_page():
    content = site_content()
    conn = get_db_connection()
    db_documents = conn.execute('SELECT * FROM documents WHERE is_public = 1 ORDER BY upload_date DESC').fetchall()
    conn.close()
    return render_template('documents.html', **content, db_documents=db_documents)

@app.route('/news')
def news_page():
    return redirect(url_for('home') + '#news')

@app.route('/news/<int:news_id>')
def news_detail_page(news_id):
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM news WHERE id = ?', (news_id,)).fetchone()
    conn.close()
    if not item:
        return render_template('errors/404.html'), 404
    return render_template('news_detail.html', item=item)


@app.route('/hippodromes')
def hippodromes_page():
    content = site_content()
    conn = get_db_connection()
    hippodromes = conn.execute('SELECT * FROM hippodromes ORDER BY location, name').fetchall()
    conn.close()
    return render_template('hippodromes.html', **content, hippodromes=hippodromes)

@app.route('/referees')
def referees_page():
    content = site_content()
    conn = get_db_connection()
    referees = conn.execute('SELECT * FROM referees WHERE is_active = 1 ORDER BY name').fetchall()
    conn.close()
    return render_template('referees.html', **content, referees=referees)

@app.route('/teams')
def teams_page():
    conn = get_db_connection()
    teams = conn.execute('''SELECT t.*, COUNT(p.id) AS player_count
                            FROM teams t
                            LEFT JOIN players p ON p.team_id = t.id OR (p.team_id IS NULL AND p.team = t.name)
                            WHERE t.is_active = 1
                            GROUP BY t.id
                            ORDER BY t.league, t.points DESC, t.name''').fetchall()
    conn.close()
    return render_template('teams.html', teams=teams, **site_content())

@app.route('/team/<int:team_id>')
def team_detail_page(team_id):
    conn = get_db_connection()
    team = conn.execute('SELECT * FROM teams WHERE id = ? AND is_active = 1', (team_id,)).fetchone()
    if not team:
        conn.close()
        return render_template('errors/404.html'), 404
    players = conn.execute('''SELECT * FROM players
                              WHERE is_active = 1 AND (team_id = ? OR (team_id IS NULL AND team = ?))
                              ORDER BY stats_points DESC, name''',
                           (team_id, team['name'])).fetchall()
    conn.close()
    return render_template('team_detail.html', team=team, players=players)

@app.route('/horses')
def horses_page():
    conn = get_db_connection()
    horses = conn.execute('SELECT * FROM horses WHERE is_active = 1 ORDER BY points DESC, name').fetchall()
    conn.close()
    return render_template('horses.html', horses=horses)

@app.route('/horses/<int:horse_id>')
def horse_detail_page(horse_id):
    conn = get_db_connection()
    horse = conn.execute('SELECT * FROM horses WHERE id = ? AND is_active = 1', (horse_id,)).fetchone()
    conn.close()
    if not horse:
        return render_template('errors/404.html'), 404
    return render_template('horse_detail.html', horse=horse)

@app.route('/contacts')
def contacts_page():
    return render_template('contacts.html', contact_cards=get_active_contact_cards(), **site_content())

@app.route('/api/search')
def api_search():
    query = request.args.get('q', '').strip()
    return jsonify({'query': query, 'results': search_site(query)})

@app.route('/search')
def search_page():
    query = request.args.get('q', '').strip()
    results = search_site(query)
    total = sum(len(items) for items in results.values())
    return render_template('search.html', query=query, results=results, total=total, highlight=highlight_text)

@app.route('/profile')
def profile_page():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('home'))

    conn = get_db_connection()
    user = conn.execute('SELECT id, full_name, email, photo_url, phone, created_at FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        session.pop('user_id', None)
        session.pop('user_name', None)
        return redirect(url_for('home'))

    tickets = conn.execute('''SELECT * FROM ticket_requests
                              WHERE email = ?
                              ORDER BY created_at DESC''', (user['email'],)).fetchall()
    conn.close()
    return render_template('profile.html', user=user, tickets=tickets)

@app.route('/api/profile/update', methods=['POST'])
def api_profile_update():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Кирүү талап кылынат.'}), 401

    data = request.get_json() or {}
    full_name = data.get('full_name', '').strip()
    phone = data.get('phone', '').strip()
    if not full_name:
        return jsonify({'status': 'error', 'message': 'Аты-жөнү бош болбошу керек.'}), 400

    conn = get_db_connection()
    conn.execute('UPDATE users SET full_name = ?, phone = ? WHERE id = ?', (full_name, phone, user_id))
    conn.commit()
    conn.close()
    session['user_name'] = full_name
    return jsonify({'status': 'success', 'message': 'Профиль жаңыртылды.', 'full_name': full_name, 'phone': phone})

@app.route('/api/profile/change-password', methods=['POST'])
def api_profile_change_password():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Кирүү талап кылынат.'}), 401

    data = request.get_json() or {}
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    if len(new_password) < 6:
        return jsonify({'status': 'error', 'message': 'Жаңы сыр сөз кеминде 6 символ болушу керек.'}), 400

    conn = get_db_connection()
    user = conn.execute('SELECT password_hash FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user or not check_password_hash(user['password_hash'], old_password):
        conn.close()
        return jsonify({'status': 'error', 'message': 'Эски сыр сөз туура эмес.'}), 400

    conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (generate_password_hash(new_password), user_id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Сыр сөз өзгөртүлдү.'})

@app.route('/sw.js')
def service_worker():
    return send_from_directory(app.static_folder, 'sw.js', mimetype='application/javascript')

def league_payload(league_name):
    conn = get_db_connection()
    standings = conn.execute('''SELECT t.*, COUNT(p.id) AS player_count
                                FROM teams t
                                LEFT JOIN players p ON p.team_id = t.id OR (p.team_id IS NULL AND p.team = t.name)
                                WHERE t.is_active = 1 AND t.league = ?
                                GROUP BY t.id
                                ORDER BY t.points DESC, t.wins DESC, t.name''', (league_name,)).fetchall()
    matches = conn.execute('''SELECT * FROM matches
                              WHERE league = ?
                              ORDER BY date, time''', (league_name,)).fetchall()
    conn.close()
    return standings, matches

@pages_bp.route('/regulations')
def regulations_page():
    regulations = [
        {'title': 'Регламент сезона 2026', 'date': '2026-03-01', 'description': 'Порядок проведения официальных матчей и турнирных этапов.', 'file': 'docs/ulak-tartysh-regulation-1.pdf'},
        {'title': 'Положение о заявках команд', 'date': '2026-02-15', 'description': 'Требования к составам, срокам подачи и подтверждению заявок.', 'file': 'docs/team-application-1.pdf'},
        {'title': 'Положение о судействе', 'date': '2026-01-20', 'description': 'Регламент назначения судей и оформления протоколов матчей.', 'file': 'docs/federation-protocol-4.pdf'},
    ]
    return render_template('regulations.html', regulations=regulations)

@pages_bp.route('/transfers')
def transfers_page():
    transfers = [
        {'player': 'Айбек Абдыразаков', 'from_team': 'Достук', 'to_team': 'Ынтымак', 'date': '2026-05-12', 'status': 'Подтверждён'},
        {'player': 'Руслан Ниязов', 'from_team': 'Ынтымак', 'to_team': 'Достук', 'date': '2026-04-28', 'status': 'На рассмотрении'},
        {'player': 'Тилек Сагынбаев', 'from_team': 'Намыс', 'to_team': 'Сары-Өзөн', 'date': '2026-04-10', 'status': 'Подтверждён'},
    ]
    return render_template('transfers.html', transfers=transfers)

@pages_bp.route('/league/higher')
def league_higher_page():
    standings, matches = league_payload('Жогорку лига')
    return render_template('league_higher.html', league_name='Жогорку лига', standings=standings, matches=matches)

@pages_bp.route('/league/first')
def league_first_page():
    standings, matches = league_payload('Биринчи лига')
    return render_template('league_first.html', league_name='Биринчи лига', standings=standings, matches=matches)

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json() or request.form.to_dict()
    payload = data.get('payload') if isinstance(data, dict) and data.get('payload') else data
    return register_user_from_payload(payload)

@app.route('/api/submit', methods=['POST'])
def handle_submissions():
    data = request.get_json() or request.form.to_dict()
    print(f"[БЭКЕНД] Получены данные: {data}")

    if data.get('form_type') == 'register':
        return register_user_from_payload(data.get('payload') or {})

    if data.get('form_type') == 'login':
        payload = data.get('payload') or {}
        email = payload.get('email', '').strip().lower()
        password = payload.get('password', '')

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if not user or not check_password_hash(user['password_hash'], password):
            return jsonify({"status": "error", "message": "Неверный email или пароль."}), 401

        session['user_id'] = user['id']
        session['user_name'] = user['full_name']
        return jsonify({"status": "success", "message": f"Добро пожаловать, {user['full_name']}!", "reload": True})

    if data.get('form_type') == 'tickets':
        payload = data.get('payload') or {}
        phone = payload.get('phone', '').strip()
        if not phone:
            return jsonify({"status": "error", "message": "Укажите телефон для бронирования."}), 400

        conn = get_db_connection()
        email = payload.get('email', '').strip()
        if not email and session.get('user_id'):
            user = conn.execute('SELECT email FROM users WHERE id = ?', (session['user_id'],)).fetchone()
            email = user['email'] if user else ''
        conn.execute('''INSERT INTO ticket_requests (match_name, count, phone, email, status, created_at)
                        VALUES (?, ?, ?, ?, 'new', ?)''',
                     (payload.get('match', '').strip(),
                      form_int_or_none(payload.get('count')) or 1,
                      phone,
                      email,
                      datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Заявка на билет сохранена. Мы свяжемся с вами."})

    return jsonify({"status": "success", "message": "Маалымат ийгиликтүү жөнөтүлдү!"})

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        expected_password = (ADMIN_PASSWORD or '').strip()
        if password == expected_password:
            session['logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            return render_template('admin/login.html', error="Туура эмес сыр сөз!")
    
    if not session.get('logged_in'):
        return render_template('admin/login.html')

    conn = get_db_connection()
    data = {
        'matches': conn.execute('SELECT * FROM matches ORDER BY date, time').fetchall(),
        'news': conn.execute('SELECT * FROM news').fetchall(),
        'leagues': conn.execute('SELECT * FROM leagues').fetchall(),
        'documents': conn.execute('SELECT * FROM documents').fetchall(),
        'players': conn.execute('SELECT * FROM players').fetchall(),
        'horses': conn.execute('SELECT * FROM horses ORDER BY points DESC, name').fetchall(),
        'referees': conn.execute('SELECT * FROM referees').fetchall(),
        'hippodromes': conn.execute('SELECT * FROM hippodromes').fetchall(),
        'videos': conn.execute('SELECT * FROM videos').fetchall(),
        'albums': conn.execute('SELECT a.*, COUNT(p.id) as photo_count FROM photo_albums a LEFT JOIN photos p ON a.id = p.album_id GROUP BY a.id').fetchall(),
        'users': conn.execute('SELECT id, full_name, email, created_at FROM users ORDER BY created_at DESC').fetchall(),
        'ticket_requests': conn.execute('SELECT * FROM ticket_requests ORDER BY created_at DESC').fetchall(),
        'contact_cards': conn.execute('SELECT * FROM contact_cards ORDER BY order_num, id').fetchall(),
        'homepage_settings': get_homepage_settings(conn),
        'homepage_stats': conn.execute('SELECT * FROM homepage_stats ORDER BY order_num, id').fetchall(),
    }
    conn.close()
    return render_template('admin/dashboard.html', **data)

@app.route('/admin/homepage', methods=['GET', 'POST'])
def admin_homepage():
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))

    if request.method == 'GET':
        return redirect(url_for('admin_panel') + '#homepage')

    try:
        title = request.form.get('title', '').strip()
        subtitle = request.form.get('subtitle', '').strip()
        description = request.form.get('description', '').strip()
        if not title or not description:
            return redirect(url_for('admin_panel') + '#homepage')

        conn = get_db_connection()
        current = get_homepage_settings(conn)
        uploaded_background = save_uploaded_file(request.files.get('background_image'), IMAGE_EXTENSIONS)
        background_image = uploaded_background or (current['background_image'] if current else DEFAULT_HOMEPAGE_SETTINGS['background_image'])

        conn.execute('''UPDATE homepage_settings
                        SET title = ?, subtitle = ?, description = ?,
                            button1_text = ?, button1_link = ?,
                            button2_text = ?, button2_link = ?,
                            background_image = ?, overlay_color = ?,
                            is_active = 1, updated_at = ?
                        WHERE section_name = 'hero' ''',
                     (
                         title,
                         subtitle or DEFAULT_HOMEPAGE_SETTINGS['subtitle'],
                         description,
                         request.form.get('button1_text', '').strip() or DEFAULT_HOMEPAGE_SETTINGS['button1_text'],
                         request.form.get('button1_link', '').strip() or DEFAULT_HOMEPAGE_SETTINGS['button1_link'],
                         request.form.get('button2_text', '').strip() or DEFAULT_HOMEPAGE_SETTINGS['button2_text'],
                         request.form.get('button2_link', '').strip() or DEFAULT_HOMEPAGE_SETTINGS['button2_link'],
                         background_image,
                         request.form.get('overlay_color', '').strip() or DEFAULT_HOMEPAGE_SETTINGS['overlay_color'],
                         datetime.now().isoformat(timespec='seconds'),
                     ))

        stat_ids = request.form.getlist('stat_id')
        stat_labels = request.form.getlist('stat_label')
        stat_values = request.form.getlist('stat_value')
        for index, stat_id in enumerate(stat_ids):
            label = stat_labels[index].strip() if index < len(stat_labels) else ''
            value = form_int_or_none(stat_values[index] if index < len(stat_values) else '') or 0
            if stat_id.isdigit() and label:
                conn.execute('''UPDATE homepage_stats
                                SET label = ?, value = ?, order_num = ?, is_active = 1, updated_at = ?
                                WHERE id = ?''',
                             (label, value, index + 1, datetime.now().isoformat(timespec='seconds'), int(stat_id)))

        conn.commit()
        conn.close()
    except Exception:
        logger.exception("Could not update homepage settings")
    return redirect(url_for('admin_panel') + '#homepage')

@app.route('/admin/homepage/preview')
def admin_homepage_preview():
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    context = build_homepage_context()
    context['is_admin_preview'] = True
    return render_template('index.html', **context)

@app.route('/admin/homepage/reset', methods=['POST'])
def reset_homepage():
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    try:
        conn = get_db_connection()
        conn.execute('''UPDATE homepage_settings
                        SET title = ?, subtitle = ?, description = ?,
                            button1_text = ?, button1_link = ?,
                            button2_text = ?, button2_link = ?,
                            background_image = ?, overlay_color = ?,
                            is_active = 1, updated_at = ?
                        WHERE section_name = 'hero' ''',
                     (
                         DEFAULT_HOMEPAGE_SETTINGS['title'],
                         DEFAULT_HOMEPAGE_SETTINGS['subtitle'],
                         DEFAULT_HOMEPAGE_SETTINGS['description'],
                         DEFAULT_HOMEPAGE_SETTINGS['button1_text'],
                         DEFAULT_HOMEPAGE_SETTINGS['button1_link'],
                         DEFAULT_HOMEPAGE_SETTINGS['button2_text'],
                         DEFAULT_HOMEPAGE_SETTINGS['button2_link'],
                         DEFAULT_HOMEPAGE_SETTINGS['background_image'],
                         DEFAULT_HOMEPAGE_SETTINGS['overlay_color'],
                         datetime.now().isoformat(timespec='seconds'),
                     ))
        conn.execute('DELETE FROM homepage_stats')
        conn.executemany('''INSERT INTO homepage_stats (label, value, order_num, is_active, updated_at)
                            VALUES (?, ?, ?, ?, ?)''',
                         [(label, value, order_num, is_active, datetime.now().isoformat(timespec='seconds'))
                          for label, value, order_num, is_active in DEFAULT_HOMEPAGE_STATS])
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("Could not reset homepage settings")
    return redirect(url_for('admin_panel') + '#homepage')

@app.route('/admin/add-match', methods=['POST'])
def add_match():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    team1 = request.form.get('team1', '').strip()
    team2 = request.form.get('team2', '').strip()
    league = request.form.get('league', '').strip()
    date = request.form.get('date', '').strip()
    time = request.form.get('time', '').strip()
    if not all([team1, team2, league, date, time]):
        return redirect(url_for('admin_panel'))

    search_tags = f"{team1} {team2} {league}".lower()
    is_next = 1 if request.form.get('is_next') else 0
    conn = get_db_connection()
    if is_next:
        conn.execute('UPDATE matches SET is_next = 0')
    conn.execute('''INSERT INTO matches (date, time, league, team1, team2, search_tags, is_next)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (date, time, league, team1, team2, search_tags, is_next))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/add-news', methods=['POST'])
def add_news():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    title = request.form.get('title', '').strip()
    date = request.form.get('date', '').strip()
    img_url = save_uploaded_file(request.files.get('image'), IMAGE_EXTENSIONS) or request.form.get('img_url', '').strip()
    body = request.form.get('body', '').strip()
    if not title or not date:
        return redirect(url_for('admin_panel'))

    search_tags = title.lower()
    conn = get_db_connection()
    conn.execute('INSERT INTO news (date, title, img_url, search_tags, body) VALUES (?, ?, ?, ?, ?)',
                 (date, title, img_url, search_tags, body))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel') + '#news')

@app.route('/admin/update-news/<int:news_id>', methods=['POST'])
def update_news(news_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    title = request.form.get('title', '').strip()
    date_value = request.form.get('date', '').strip()
    if not title or not date_value:
        return redirect(url_for('admin_panel') + '#news')

    img_url = save_uploaded_file(request.files.get('image'), IMAGE_EXTENSIONS) or request.form.get('img_url', '').strip()
    body = request.form.get('body', '').strip()
    conn = get_db_connection()
    current = conn.execute('SELECT img_url FROM news WHERE id = ?', (news_id,)).fetchone()
    final_img_url = img_url or (current['img_url'] if current else '')
    conn.execute('''UPDATE news SET date = ?, title = ?, img_url = ?, search_tags = ?, body = ?
                    WHERE id = ?''',
                 (date_value, title, final_img_url, title.lower(), body, news_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel') + '#news')

@app.route('/admin/update-match/<int:match_id>', methods=['POST'])
def update_match(match_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    team1 = request.form.get('team1', '').strip()
    team2 = request.form.get('team2', '').strip()
    league = request.form.get('league', '').strip()
    date_value = request.form.get('date', '').strip()
    time_value = request.form.get('time', '').strip()
    if not all([team1, team2, league, date_value, time_value]):
        return redirect(url_for('admin_panel') + '#matches')

    is_next = 1 if request.form.get('is_next') else 0
    conn = get_db_connection()
    if is_next:
        conn.execute('UPDATE matches SET is_next = 0')
    conn.execute('''UPDATE matches SET date = ?, time = ?, league = ?, team1 = ?, team2 = ?, search_tags = ?, is_next = ?
                    WHERE id = ?''',
                 (date_value, time_value, league, team1, team2, f"{team1} {team2} {league}".lower(), is_next, match_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel') + '#matches')

@app.route('/admin/add-league', methods=['POST'])
def add_league():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    conn.execute('''INSERT INTO leagues (name, category, description, teams_count, stage, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                 (request.form.get('name'), request.form.get('category'),
                  request.form.get('description'), request.form.get('teams_count'),
                  request.form.get('stage'), 1))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/toggle-league/<int:league_id>')  # ✅ ИСПРАВЛЕНО
def toggle_league(league_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    conn.execute('UPDATE leagues SET is_active = NOT is_active WHERE id = ?', (league_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/upload-document', methods=['POST'])
def upload_document():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    if 'file' not in request.files:
        return redirect(url_for('admin_panel'))
    
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename, DOCUMENT_EXTENSIONS):
        return redirect(url_for('admin_panel'))
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    conn = get_db_connection()
    conn.execute('''INSERT INTO documents (title, description, file_path, file_type, category, upload_date, is_public) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (request.form.get('title'), request.form.get('description'),
                  filepath, filename.rsplit('.', 1)[1].lower(),
                  request.form.get('category'), request.form.get('upload_date') or today_iso(), 1))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/add-player', methods=['POST'])
def add_player():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    photo_url = save_uploaded_file(request.files.get('photo'), IMAGE_EXTENSIONS) or request.form.get('photo_url') or 'https://placehold.co/300x400'
    team_name = request.form.get('team', '').strip()
    conn = get_db_connection()
    team = conn.execute('SELECT id FROM teams WHERE name = ?', (team_name,)).fetchone()
    conn.execute('''INSERT INTO players (name, photo_url, team, team_id, position, stats_points, stats_matches, birth_year, region, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (request.form.get('name'), photo_url,
                  team_name, team['id'] if team else None, request.form.get('position'),
                  request.form.get('stats_points', 0), request.form.get('stats_matches', 0),
                  request.form.get('birth_year'), request.form.get('region'), 1))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/add-horse', methods=['POST'])
def add_horse():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    name = request.form.get('name', '').strip()
    if not name:
        return redirect(url_for('admin_panel') + '#horses')

    uploaded_photo = save_uploaded_file(request.files.get('photo'), IMAGE_EXTENSIONS)
    linked_photo = request.form.get('photo_url', '').strip()
    photo_url = uploaded_photo or linked_photo or HORSE_PHOTO_PLACEHOLDER
    conn = get_db_connection()
    conn.execute('''INSERT INTO horses (name, photo_url, breed, age, color, speed, stamina, points, price, description, is_for_sale, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)''',
                 (name, photo_url,
                  request.form.get('breed', '').strip(),
                  form_int_or_none(request.form.get('age')),
                  request.form.get('color', '').strip(),
                  form_int_or_none(request.form.get('speed')) or 0,
                  form_int_or_none(request.form.get('stamina')) or 0,
                  form_int_or_none(request.form.get('points')) or 0,
                  form_int_or_none(request.form.get('price')),
                  request.form.get('description', '').strip(),
                  1 if request.form.get('is_for_sale') else 0))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel') + '#horses')

@app.route('/admin/update-horse/<int:horse_id>', methods=['POST'])
def update_horse(horse_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    name = request.form.get('name', '').strip()
    if not name:
        return redirect(url_for('admin_panel') + '#horses')

    uploaded_photo = save_uploaded_file(request.files.get('photo'), IMAGE_EXTENSIONS)
    requested_photo = request.form.get('photo_url', '').strip()
    conn = get_db_connection()
    current = conn.execute('SELECT photo_url FROM horses WHERE id = ?', (horse_id,)).fetchone()
    photo_url = uploaded_photo or requested_photo or (current['photo_url'] if current else '')
    conn.execute('''UPDATE horses SET name = ?, photo_url = ?, breed = ?, age = ?, color = ?, speed = ?,
                    stamina = ?, points = ?, price = ?, description = ?, is_for_sale = ?, is_active = ?
                    WHERE id = ?''',
                 (name, photo_url,
                  request.form.get('breed', '').strip(),
                  form_int_or_none(request.form.get('age')),
                  request.form.get('color', '').strip(),
                  form_int_or_none(request.form.get('speed')) or 0,
                  form_int_or_none(request.form.get('stamina')) or 0,
                  form_int_or_none(request.form.get('points')) or 0,
                  form_int_or_none(request.form.get('price')),
                  request.form.get('description', '').strip(),
                  1 if request.form.get('is_for_sale') else 0,
                  1 if request.form.get('is_active') else 0,
                  horse_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel') + '#horses')

@app.route('/admin/update-ticket/<int:ticket_id>', methods=['POST'])
def update_ticket(ticket_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    status = request.form.get('status', 'new')
    if status not in {'new', 'processed', 'cancelled'}:
        status = 'new'
    conn = get_db_connection()
    conn.execute('UPDATE ticket_requests SET status = ? WHERE id = ?', (status, ticket_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel') + '#tickets')

@app.route('/admin/add-contact-card', methods=['POST'])
def add_contact_card():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    conn.execute('''INSERT INTO contact_cards (title, type, value, icon, color, order_num, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)''',
                 (request.form.get('title', '').strip(),
                  request.form.get('type', 'phone').strip(),
                  request.form.get('value', '').strip(),
                  request.form.get('icon', '☎️').strip() or '☎️',
                  request.form.get('color', '#16a34a').strip() or '#16a34a',
                  form_int_or_none(request.form.get('order_num')) or 0))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel') + '#contact-cards')

@app.route('/admin/update-contact-card/<int:card_id>', methods=['POST'])
def update_contact_card(card_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    conn.execute('''UPDATE contact_cards
                    SET title = ?, type = ?, value = ?, icon = ?, color = ?, order_num = ?, is_active = ?
                    WHERE id = ?''',
                 (request.form.get('title', '').strip(),
                  request.form.get('type', 'phone').strip(),
                  request.form.get('value', '').strip(),
                  request.form.get('icon', '☎️').strip() or '☎️',
                  request.form.get('color', '#16a34a').strip() or '#16a34a',
                  form_int_or_none(request.form.get('order_num')) or 0,
                  1 if request.form.get('is_active') else 0,
                  card_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel') + '#contact-cards')

@app.route('/admin/delete-contact-card/<int:card_id>')
def delete_contact_card(card_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    conn.execute('DELETE FROM contact_cards WHERE id = ?', (card_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel') + '#contact-cards')

@app.route('/admin/toggle-contact-card/<int:card_id>')
def toggle_contact_card(card_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    conn.execute('UPDATE contact_cards SET is_active = NOT is_active WHERE id = ?', (card_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel') + '#contact-cards')

@app.route('/admin/add-referee', methods=['POST'])
def add_referee():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    name = request.form.get('name', '').strip()
    if not name:
        return redirect(url_for('admin_panel'))

    photo_url = save_uploaded_file(request.files.get('photo'), IMAGE_EXTENSIONS) or request.form.get('photo_url', '').strip()
    conn = get_db_connection()
    conn.execute('''INSERT INTO referees (name, photo_url, category, experience_years, region, is_active)
                    VALUES (?, ?, ?, ?, ?, 1)''',
                 (name, photo_url, request.form.get('category', '').strip(),
                  form_int_or_none(request.form.get('experience_years')),
                  request.form.get('region', '').strip()))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel') + '#people')

@app.route('/admin/add-hippodrome', methods=['POST'])
def add_hippodrome():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    name = request.form.get('name', '').strip()
    if not name:
        return redirect(url_for('admin_panel'))

    photo_url = save_uploaded_file(request.files.get('photo'), IMAGE_EXTENSIONS) or request.form.get('photo_url', '').strip()
    conn = get_db_connection()
    conn.execute('''INSERT INTO hippodromes (name, location, address, map_url, capacity, surface, description, photo_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                 (name, request.form.get('location', '').strip(),
                  request.form.get('address', '').strip(),
                  request.form.get('map_url', '').strip(),
                  form_int_or_none(request.form.get('capacity')),
                  request.form.get('surface', '').strip(),
                  request.form.get('description', '').strip(),
                  photo_url))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel') + '#venues')

@app.route('/admin/add-video', methods=['POST'])
def add_video():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    video_url = save_uploaded_file(request.files.get('video_file'), VIDEO_EXTENSIONS) or request.form.get('video_url', '').strip()
    thumbnail = save_uploaded_file(request.files.get('thumbnail_file'), IMAGE_EXTENSIONS) or request.form.get('thumbnail', '').strip()
    title = request.form.get('title', '').strip()
    if not title or not video_url:
        return redirect(url_for('admin_panel'))

    conn = get_db_connection()
    conn.execute('''INSERT INTO videos (title, video_url, thumbnail, match_id, upload_date, views, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (title, video_url, thumbnail, form_int_or_none(request.form.get('match_id')),
                  request.form.get('upload_date') or today_iso(), 0,
                  request.form.get('category')))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/create-album', methods=['POST'])
def create_album():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    cover_url = save_uploaded_file(request.files.get('cover_file'), IMAGE_EXTENSIONS) or request.form.get('cover_url', '').strip()
    title = request.form.get('title', '').strip()
    if not title:
        return redirect(url_for('admin_panel'))

    conn = get_db_connection()
    conn.execute('''INSERT INTO photo_albums (title, match_id, cover_url, upload_date, photo_count)
                    VALUES (?, ?, ?, ?, ?)''',
                 (title, form_int_or_none(request.form.get('match_id')),
                  cover_url, request.form.get('upload_date') or today_iso(), 0))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/add-photo/<int:album_id>', methods=['POST'])  # ✅ ИСПРАВЛЕНО
def add_photo(album_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    if 'photo' not in request.files:
        return redirect(url_for('admin_panel'))
    
    file = request.files['photo']
    if file.filename == '' or not allowed_file(file.filename, IMAGE_EXTENSIONS):
        return redirect(url_for('admin_panel'))

    filepath = save_uploaded_file(file, IMAGE_EXTENSIONS)
    
    conn = get_db_connection()
    conn.execute('INSERT INTO photos (album_id, photo_url, caption) VALUES (?, ?, ?)',
                 (album_id, filepath, request.form.get('caption', '')))
    conn.execute('UPDATE photo_albums SET photo_count = photo_count + 1 WHERE id = ?', (album_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete/<table_name>/<int:item_id>')  # ✅ ИСПРАВЛЕНО
def delete_item(table_name, item_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    allowed_tables = ['matches', 'news', 'leagues', 'documents', 'players', 'horses', 'referees', 'hippodromes', 'videos', 'photo_albums', 'photos', 'users', 'ticket_requests', 'contact_cards']
    if table_name not in allowed_tables:
        return redirect(url_for('admin_panel'))
    
    conn = get_db_connection()
    # Using validated table_name from whitelist to prevent SQL injection
    conn.execute(f'DELETE FROM "{table_name}" WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    return redirect(url_for('admin_panel'))

@app.route('/logout')
def user_logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    return redirect(url_for('home'))

def allowed_file(filename, allowed_extensions=None):
    extensions = allowed_extensions or (DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS | VIDEO_EXTENSIONS)
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

# ==========================================
# 🔧 Удаление фото из новости
# ==========================================
@app.route('/admin/delete-news-image/<int:news_id>', methods=['POST'])
def delete_news_image(news_id):
    """Удаление фото из новости"""
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    
    conn = get_db_connection()
    news = conn.execute('SELECT img_url FROM news WHERE id = ?', (news_id,)).fetchone()
    
    if news and news['img_url']:
        # Удаляем файл с диска
        try:
            relative_path = news['img_url'].lstrip('/')
            if relative_path.startswith('static/uploads/'):
                file_path = relative_path
            else:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], relative_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning("Could not delete news image: %s", e)
        
        # Очищаем поле в БД
        conn.execute('UPDATE news SET img_url = ? WHERE id = ?', ('', news_id))
        conn.commit()
    
    conn.close()
    return redirect(url_for('admin_panel') + '#news')

app.register_blueprint(pages_bp)

if __name__ == '__main__':  # ✅ ИСПРАВЛЕНО
    init_db()
    port = int(os.getenv('PORT', 5002))
    app.run(debug=True, host='0.0.0.0', port=port)
    
