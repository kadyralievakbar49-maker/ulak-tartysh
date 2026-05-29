from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import os
import random
import smtplib
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from uuid import uuid4
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)  # ✅ ИСПРАВЛЕНО
app.secret_key = os.getenv('SECRET_KEY', 'super_secret_key_for_sessions')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
VIDEO_EXTENSIONS = {'mp4', 'mov', 'webm', 'avi', 'mkv'}
DOCUMENT_EXTENSIONS = {'pdf', 'docx'}

SMTP_HOST = os.getenv('SMTP_HOST', '')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USER or 'noreply@example.com')

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

def send_confirmation_email(email, code):
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
    if not file or file.filename == '' or not allowed_file(file.filename, allowed_extensions):
        return ''

    original = secure_filename(file.filename)
    extension = original.rsplit('.', 1)[1].lower()
    filename = f"{uuid4().hex}.{extension}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    return f"/{filepath}"

def form_int_or_none(value):
    return int(value) if value and str(value).isdigit() else None

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

@app.route('/')
def home():
    conn = get_db_connection()
    matches = conn.execute('SELECT * FROM matches ORDER BY date, time').fetchall()
    news = conn.execute('SELECT * FROM news').fetchall()
    next_match = conn.execute('SELECT * FROM matches WHERE is_next = 1 LIMIT 1').fetchone()
    if not next_match and matches:
        next_match = matches[0]
    
    leagues = conn.execute('SELECT * FROM leagues WHERE is_active = 1 ORDER BY category, name').fetchall()
    players = conn.execute('SELECT * FROM players WHERE is_active = 1 ORDER BY stats_points DESC LIMIT 4').fetchall()
    documents = conn.execute('SELECT * FROM documents WHERE is_public = 1 ORDER BY upload_date DESC').fetchall()
    videos = conn.execute('SELECT * FROM videos ORDER BY upload_date DESC LIMIT 4').fetchall()
    albums = conn.execute('SELECT * FROM photo_albums ORDER BY upload_date DESC LIMIT 4').fetchall()
    conn.close()

    return render_template('index.html', matches=matches, news=news, next_match=next_match,
                          leagues=leagues, players=players, documents=documents,
                          videos=videos, albums=albums)

@app.route('/about')
def about_page():
    return render_template('about.html', **site_content())

@app.route('/documents')
def documents_page():
    content = site_content()
    conn = get_db_connection()
    db_documents = conn.execute('SELECT * FROM documents WHERE is_public = 1 ORDER BY upload_date DESC').fetchall()
    conn.close()
    return render_template('documents.html', **content, db_documents=db_documents)

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
    return render_template('teams.html', **site_content())

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
    return render_template('contacts.html', **site_content())

@app.route('/api/submit', methods=['POST'])
def handle_submissions():
    data = request.get_json() or request.form.to_dict()
    print(f"[БЭКЕНД] Получены данные: {data}")

    if data.get('form_type') == 'register':
        payload = data.get('payload') or {}
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

        conn = get_db_connection()
        existing = conn.execute('SELECT id, is_verified FROM users WHERE email = ?', (email,)).fetchone()
        if existing and existing['is_verified']:
            conn.close()
            return jsonify({"status": "error", "message": "Этот email уже зарегистрирован."}), 409

        now = datetime.utcnow()
        code = f"{random.randint(100000, 999999)}"
        password_hash = generate_password_hash(password)

        if existing:
            conn.execute('''UPDATE users SET full_name = ?, password_hash = ?, is_verified = 0
                            WHERE email = ?''', (fullname, password_hash, email))
        else:
            conn.execute('''INSERT INTO users (full_name, email, password_hash, is_verified, created_at)
                            VALUES (?, ?, ?, 0, ?)''',
                         (fullname, email, password_hash, now.isoformat()))

        conn.execute('DELETE FROM email_confirmations WHERE email = ?', (email,))
        conn.execute('''INSERT INTO email_confirmations (email, code, expires_at, created_at)
                        VALUES (?, ?, ?, ?)''',
                     (email, code, (now + timedelta(minutes=15)).isoformat(), now.isoformat()))
        conn.commit()
        conn.close()

        try:
            email_sent = send_confirmation_email(email, code)
        except Exception as error:
            print(f"[EMAIL ERROR] {error}")
            return jsonify({"status": "error", "message": "Не удалось отправить письмо. Проверьте настройки SMTP."}), 500

        message = "Код подтверждения отправлен на email."
        if not email_sent:
            message = "SMTP не настроен. Код подтверждения выведен в консоль Flask."
        return jsonify({"status": "verification_required", "message": message, "email": email})

    if data.get('form_type') == 'login':
        payload = data.get('payload') or {}
        email = payload.get('email', '').strip().lower()
        password = payload.get('password', '')

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if not user or not check_password_hash(user['password_hash'], password):
            return jsonify({"status": "error", "message": "Неверный email или пароль."}), 401
        if not user['is_verified']:
            return jsonify({"status": "error", "message": "Сначала подтвердите email."}), 403

        session['user_id'] = user['id']
        session['user_name'] = user['full_name']
        return jsonify({"status": "success", "message": f"Добро пожаловать, {user['full_name']}!", "reload": True})

    if data.get('form_type') == 'verify_email':
        payload = data.get('payload') or {}
        email = payload.get('email', '').strip().lower()
        code = payload.get('code', '').strip()

        conn = get_db_connection()
        confirmation = conn.execute('''SELECT * FROM email_confirmations
                                       WHERE email = ? AND code = ?
                                       ORDER BY created_at DESC LIMIT 1''',
                                    (email, code)).fetchone()
        if not confirmation:
            conn.close()
            return jsonify({"status": "error", "message": "Неверный код подтверждения."}), 400

        if datetime.fromisoformat(confirmation['expires_at']) < datetime.utcnow():
            conn.close()
            return jsonify({"status": "error", "message": "Код истёк. Зарегистрируйтесь ещё раз."}), 400

        conn.execute('UPDATE users SET is_verified = 1 WHERE email = ?', (email,))
        conn.execute('DELETE FROM email_confirmations WHERE email = ?', (email,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Email подтверждён. Регистрация завершена."})

    if data.get('form_type') == 'tickets':
        payload = data.get('payload') or {}
        phone = payload.get('phone', '').strip()
        if not phone:
            return jsonify({"status": "error", "message": "Укажите телефон для бронирования."}), 400

        conn = get_db_connection()
        conn.execute('''INSERT INTO ticket_requests (match_name, count, phone, email, status, created_at)
                        VALUES (?, ?, ?, ?, 'new', ?)''',
                     (payload.get('match', '').strip(),
                      form_int_or_none(payload.get('count')) or 1,
                      phone,
                      payload.get('email', '').strip(),
                      datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Заявка на билет сохранена. Мы свяжемся с вами."})

    return jsonify({"status": "success", "message": "Маалымат ийгиликтүү жөнөтүлдү!"})

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
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
        'users': conn.execute('SELECT id, full_name, email, is_verified, created_at FROM users ORDER BY created_at DESC').fetchall(),
        'ticket_requests': conn.execute('SELECT * FROM ticket_requests ORDER BY created_at DESC').fetchall(),
    }
    conn.close()
    return render_template('admin/dashboard.html', **data)

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
    conn = get_db_connection()
    conn.execute('''INSERT INTO players (name, photo_url, team, position, stats_points, stats_matches, birth_year, region, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (request.form.get('name'), photo_url,
                  request.form.get('team'), request.form.get('position'),
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

    photo_url = save_uploaded_file(request.files.get('photo'), IMAGE_EXTENSIONS) or request.form.get('photo_url', '').strip()
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
    allowed_tables = ['matches', 'news', 'leagues', 'documents', 'players', 'horses', 'referees', 'hippodromes', 'videos', 'photo_albums', 'photos', 'users', 'ticket_requests']
    if table_name not in allowed_tables:
        return redirect(url_for('admin_panel'))
    
    conn = get_db_connection()
    conn.execute(f'DELETE FROM {table_name} WHERE id = ?', (item_id,))
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

if __name__ == '__main__':  # ✅ ИСПРАВЛЕНО
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5001)
    
