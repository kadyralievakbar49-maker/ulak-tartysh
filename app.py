from flask import Flask, Blueprint, render_template, request, jsonify, redirect, url_for, session, send_from_directory, flash
import hashlib
import sqlite3
import os
import logging
import re
import json
import secrets
import smtplib
from email.message import EmailMessage
from urllib.parse import parse_qs, urlparse
from markupsafe import Markup, escape
from datetime import date, datetime, timedelta
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
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  SESSION_COOKIE_SECURE=os.getenv('SESSION_COOKIE_SECURE', 'false').lower() in {'1','true','yes'})

# Initialize CSRF protection
csrf = CSRFProtect(app)

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

SMTP_HOST = os.getenv('SMTP_HOST', '').strip()
SMTP_PORT = int(os.getenv('SMTP_PORT', '587') or 587)
SMTP_USER = os.getenv('SMTP_USER', '').strip()
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '').strip()
SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USER or 'noreply@example.com').strip()
SMTP_USE_SSL = os.getenv('SMTP_USE_SSL', '').lower() in {'1', 'true', 'yes', 'on'}
SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'true').lower() not in {'0', 'false', 'no', 'off'}
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', '').strip().rstrip('/')
EMAIL_CONFIRMATION_TTL_HOURS = int(os.getenv('EMAIL_CONFIRMATION_TTL_HOURS', '24') or 24)

IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
VIDEO_EXTENSIONS = {'mp4', 'mov', 'webm', 'avi', 'mkv'}
EMBED_VIDEO_EXTENSIONS = VIDEO_EXTENSIONS | {'m4v', 'ogv', 'ogg'}
DOCUMENT_EXTENSIONS = {'pdf', 'docx'}
HORSE_PHOTO_PLACEHOLDER = 'https://placehold.co/800x600/1a2744/f5b041?text=Horse'
DOCUMENT_CATEGORIES = {
    'charters': 'Уставы',
    'rules': 'Правила',
    'regulations': 'Регламенты',
    'applications': 'Заявки',
    'legal': 'Юридические',
    'forms': 'Формы',
}
DOCUMENT_SEED = [
    {
        'title': 'Положение игры «Улак Тартыш» Редакция №1',
        'category': 'rules',
        'official_date': '2026-04-23',
        'reg_number': '',
        'description': 'Официальные правила игры Улак Тартыш, утверждённые Федерацией. Определяет порядок проведения соревнований, права и обязанности участников, судей и организаторов.',
        'filename': 'Положение_Улак_Тартыш_Редакция_№1.pdf',
    },
    {
        'title': 'Заявка команды на участие',
        'category': 'applications',
        'official_date': '2026-01-15',
        'reg_number': '',
        'description': 'Бланк заявки команды для участия в турнирах. Включает состав команды, подписи тренера, капитана и врача.',
        'filename': '№1. заявка команд (2).pdf',
    },
    {
        'title': 'Состав команды (Форма №8)',
        'category': 'forms',
        'official_date': '2026-01-15',
        'reg_number': '',
        'description': 'Форма состава команды с игроками и лошадьми. Указывается ФИО, год рождения, кличка лошади.',
        'filename': '№8 Состав команды-2.pdf',
    },
    {
        'title': 'Выписка Минюст Федерации',
        'category': 'legal',
        'official_date': '2026-04-16',
        'reg_number': '328117-3301-ОО',
        'description': 'Выписка из Министерства Юстиции КР о регистрации ОО «Федерация Улак Тартыш». Рег. номер 328117-3301-ОО.',
        'filename': '№3_Выписка_Мин_Юст_Фед_Улак_Тартыш.pdf',
    },
    {
        'title': 'Доверенность',
        'category': 'legal',
        'official_date': '2026-04-07',
        'reg_number': '',
        'description': 'Доверенность на представление интересов Федерации в государственных органах КР.',
        'filename': '№2. Scanned 7 Apr 2026 at 09_05_49.pdf',
    },
    {
        'title': 'Протокол №1 о создании Федерации',
        'category': 'legal',
        'official_date': '2026-04-16',
        'reg_number': '',
        'description': 'Протокол учредительного собрания о создании Общественного объединения «Федерация Улак Тартыш».',
        'filename': '№_4_Протокол_№1_о_Создании_ОО_Федерация_Улак_Тартыш.pdf',
    },
    {
        'title': 'ULAK TARTYSH (международный стандарт)',
        'category': 'rules',
        'official_date': '2026-04-23',
        'reg_number': '',
        'description': 'Международный стандарт игры Улак-Тартыш (Кок-Бору). Основные правила и регламент международных соревнований.',
        'filename': 'ULAK TARTYSH.pdf',
    },
    {
        'title': 'Улак Тартыш эрежеси',
        'category': 'rules',
        'official_date': '2026-04-23',
        'reg_number': '',
        'description': 'Правила игры на кыргызском языке.',
        'filename': 'УлакТартыш эрежесиd.pdf',
    },
]
DEFAULT_HOMEPAGE_SETTINGS = {
    'section_name': 'hero',
    'title': 'Улак тартыш оюндарын жаңы деңгээлде көрүңүз',
    'subtitle': 'Расмий портал',
    'description': 'Матчтардын календары, лигалар, оюнчулар, жаңылыктар жана медиа бир жерде.',
    'button1_text': 'Оюндарды көрүү',
    'button1_link': '#matches',
    'button2_text': 'Жаңылыктар',
    'button2_link': '/news',
    'background_image': '/static/img/slider/slide1.jpg',
    'overlay_color': 'linear-gradient(90deg, rgba(8, 13, 24, 0.78) 0%, rgba(10, 18, 32, 0.58) 48%, rgba(10, 18, 32, 0.32) 100%)',
    'is_active': 1,
}
DEFAULT_HOMEPAGE_STATS = [
    ('Оюн', 0, 1, 1),
    ('Жаңылык', 3, 2, 1),
    ('Оюнчу', 2, 3, 1),
]

FEATURED_TANDEMS = [
    {
        'player': 'Манас Ниязов',
        'horse': 'Бойка',
        'team': 'Сборная Кыргызстана',
        'position': 'Универсал и лидер атаки',
        'description': 'Тандем, который читает поле на ход вперёд. Манас сочетает силовой подбор с точным завершением, а Бойка даёт резкий старт и устойчивость в плотной борьбе.',
        'achievement': 'Лидер национальной сборной и один из самых узнаваемых улакчы своего поколения.',
        'image_url': 'https://images.pexels.com/photos/11883167/pexels-photo-11883167.jpeg?auto=compress&cs=tinysrgb&w=1200',
    },
    {
        'player': 'Омурбек Эсен уулу',
        'horse': 'Ахиллес',
        'team': 'Ынтымак',
        'position': 'Нападающий, мастер один в один',
        'description': 'Скоростная связка для острых прорывов через центр. Омурбек уверенно держит улак под давлением, а мощный ход Ахиллеса помогает сохранять темп до самой линии тай-казана.',
        'achievement': 'Лучший игрок Кыргызстана 2023 года и многократный призёр крупных турниров.',
        'image_url': 'https://images.pexels.com/photos/7883411/pexels-photo-7883411.jpeg?auto=compress&cs=tinysrgb&w=1200',
    },
    {
        'player': 'Жолдошбек Орозбаев',
        'horse': 'Арбат',
        'team': 'Сборная Кыргызстана',
        'position': 'Капитан и силовой универсал',
        'description': 'Опытная пара для матчей с высокой ценой ошибки. Жолдошбек управляет ритмом и закрывает ключевые зоны, а Арбат известен балансом, выносливостью и спокойствием в контакте.',
        'achievement': 'Капитан сборной и участник международных матчей на легендарном Арбате.',
        'image_url': 'https://images.pexels.com/photos/36775906/pexels-photo-36775906.jpeg?auto=compress&cs=tinysrgb&w=1200',
    },
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
    conn = sqlite3.connect(app.config.get('DATABASE', os.path.join(app.root_path, 'database.db')))
    conn.row_factory = sqlite3.Row
    return conn

def today_iso():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo('Asia/Bishkek')).date().isoformat()

def parse_iso_date(value):
    if not value or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return None
    try:
        parsed = datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None
    if not 1900 <= parsed.year <= 2100:
        return None
    return parsed

def is_valid_iso_date(value):
    return parse_iso_date(value) is not None

def format_display_date(value):
    parsed = parse_iso_date(value)
    return parsed.strftime('%d.%m.%Y') if parsed else (value or '')

app.jinja_env.filters['display_date'] = format_display_date

def token_digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def public_url_for(endpoint, **values):
    external_path = url_for(endpoint, _external=True, **values)
    if not PUBLIC_BASE_URL:
        return external_path
    parsed = urlparse(external_path)
    return f"{PUBLIC_BASE_URL}{parsed.path}"

def smtp_is_configured():
    placeholders = {'your-app-password', 'your-email@example.com', 'your-kanchik787@gmail.com'}
    if not SMTP_HOST:
        return False
    values = {SMTP_USER.lower(), SMTP_PASSWORD.lower(), SMTP_FROM.lower()}
    return not bool(values & placeholders)

def send_email_message(to_email, subject, text_body, html_body=None):
    if not smtp_is_configured():
        logger.info("SMTP is not configured; email to %s was printed in development mode.", to_email)
        print(f"[EMAIL DEV] To: {to_email}\nSubject: {subject}\n\n{text_body}")
        return False

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = SMTP_FROM
    message['To'] = to_email
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype='html')

    smtp_class = smtplib.SMTP_SSL if SMTP_USE_SSL or SMTP_PORT == 465 else smtplib.SMTP
    with smtp_class(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        if smtp_class is smtplib.SMTP and SMTP_USE_TLS:
            server.starttls()
        if SMTP_USER and SMTP_PASSWORD:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(message)
    return True

def smtp_user_message(error):
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return "Gmail отклонил SMTP-логин. Проверьте email и 16-значный пароль приложения Google."
    return "Письмо отправить не удалось. Проверьте SMTP-настройки."

def create_email_confirmation(conn, user_id, email):
    now = datetime.utcnow()
    token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(hours=EMAIL_CONFIRMATION_TTL_HOURS)
    conn.execute(
        '''UPDATE email_confirmations
           SET used_at = ?
           WHERE user_id = ? AND used_at IS NULL''',
        (now.isoformat(), user_id)
    )
    conn.execute(
        '''INSERT INTO email_confirmations (user_id, email, token_hash, expires_at, created_at)
           VALUES (?, ?, ?, ?, ?)''',
        (user_id, email, token_digest(token), expires_at.isoformat(), now.isoformat())
    )
    return token, expires_at

def send_registration_confirmation(email, full_name, token, expires_at):
    confirm_url = public_url_for('confirm_email', token=token)
    subject = 'Подтверждение регистрации на сайте Федерации Улак Тартыш'
    text_body = (
        f"Здравствуйте, {full_name}!\n\n"
        "Для завершения регистрации подтвердите email по ссылке:\n"
        f"{confirm_url}\n\n"
        f"Ссылка действует до {expires_at.strftime('%d.%m.%Y %H:%M')} UTC.\n"
        "Если вы не регистрировались на сайте, просто игнорируйте это письмо."
    )
    html_body = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#1a2744">
      <h2 style="margin:0 0 12px">Подтверждение регистрации</h2>
      <p>Здравствуйте, {escape(full_name)}!</p>
      <p>Нажмите на кнопку ниже, чтобы подтвердить email и завершить регистрацию.</p>
      <p>
        <a href="{confirm_url}" style="display:inline-block;padding:12px 18px;border-radius:8px;background:#d32f2f;color:#fff;text-decoration:none;font-weight:700">
          Подтвердить email
        </a>
      </p>
      <p style="color:#667085;font-size:13px">Ссылка действует до {expires_at.strftime('%d.%m.%Y %H:%M')} UTC.</p>
    </div>
    """
    return send_email_message(email, subject, text_body, html_body)

def save_uploaded_file(file, allowed_extensions):
    if not file or file.filename == '' or not allowed_file(file.filename, allowed_extensions):
        return ''

    original = secure_filename(file.filename)
    if '.' not in original:
        return ''

    extension = original.rsplit('.', 1)[1].lower()
    upload_folder = os.path.join(app.static_folder, 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
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
            filename = f"{base_name}.jpg"
            filepath = os.path.join(upload_folder, filename)
            image.save(filepath, 'JPEG', quality=85, optimize=True)

            thumbnail = image.copy()
            thumbnail.thumbnail((400, 300), Image.Resampling.LANCZOS)
            thumbnail_path = os.path.join(upload_folder, f"{base_name}_thumb.jpg")
            thumbnail.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
            return f"/static/uploads/{filename}"

        filename = f"{uuid4().hex}.{extension}"
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        return f"/static/uploads/{filename}"
    except Exception:
        logger.exception("Could not save uploaded file: %s", original)
        return ''

def form_int_or_none(value):
    return int(value) if value and str(value).isdigit() else None

def ensure_column(conn, table, column, definition):
    columns = {row[1] for row in conn.execute(f'PRAGMA table_info({table})').fetchall()}
    if column not in columns:
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')

def ensure_email_confirmations_schema(conn):
    required_columns = {'id', 'user_id', 'email', 'token_hash', 'expires_at', 'created_at', 'used_at'}
    existing_columns = {row[1] for row in conn.execute('PRAGMA table_info(email_confirmations)').fetchall()}
    if existing_columns and not required_columns.issubset(existing_columns):
        conn.execute('DROP TABLE email_confirmations')
    conn.execute('''CREATE TABLE IF NOT EXISTS email_confirmations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        email TEXT NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        used_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')

def admin_redirect(section='overview', message='', category='success'):
    if message:
        flash(message, category)
    suffix = f"#{section}" if section else ''
    return redirect(url_for('admin_panel') + suffix)

def row_to_dict(row):
    return dict(row) if row else {}

def plain_summary(text, limit=160):
    cleaned = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', text or '')).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit - 1].rstrip() + '…'

def document_url(filename):
    return f"/documents/{filename}"

def document_disk_path(file_url_or_name):
    value = (file_url_or_name or '').strip()
    if value.startswith('/documents/'):
        value = value[len('/documents/'):]
    elif value.startswith('documents/'):
        value = value[len('documents/'):]
    elif value.startswith('/static/documents/'):
        value = value[len('/static/documents/'):]
    elif value.startswith('static/documents/'):
        value = value[len('static/documents/'):]
    if not value or value.startswith(('http://', 'https://', '#')):
        return ''
    return os.path.join(app.static_folder, 'documents', value)

def document_file_size(file_url_or_name):
    path = document_disk_path(file_url_or_name)
    return os.path.getsize(path) if path and os.path.exists(path) else 0

def document_size_mb(size):
    try:
        return f"{(int(size or 0) / (1024 * 1024)):.2f}"
    except (TypeError, ValueError):
        return "0.00"

app.jinja_env.filters['document_size_mb'] = document_size_mb

def _clean_video_id(value):
    value = (value or '').strip().split('?')[0].split('&')[0]
    match = re.match(r'^[A-Za-z0-9_-]{6,}$', value)
    return value if match else ''

def video_embed(url):
    value = (url or '').strip()
    if not value:
        return {'type': 'empty', 'src': ''}

    parsed = urlparse(value if re.match(r'^[a-z]+://', value, re.I) else f"//{value}")
    path = parsed.path or value
    extension = path.rsplit('.', 1)[-1].lower() if '.' in path.rsplit('/', 1)[-1] else ''
    if extension in EMBED_VIDEO_EXTENSIONS:
        return {'type': 'direct', 'src': value}

    host = parsed.netloc.lower().split(':')[0]
    if host.startswith('www.'):
        host = host[4:]
    if host in {'youtu.be'}:
        video_id = _clean_video_id(parsed.path.strip('/').split('/')[0])
        if video_id:
            return {'type': 'embed', 'src': f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0"}
    if host.endswith('youtube.com') or host.endswith('youtube-nocookie.com'):
        parts = [part for part in parsed.path.split('/') if part]
        video_id = ''
        if parts and parts[0] in {'embed', 'shorts', 'live', 'v'} and len(parts) > 1:
            video_id = _clean_video_id(parts[1])
        elif parsed.path in {'/watch', 'watch'}:
            video_id = _clean_video_id(parse_qs(parsed.query).get('v', [''])[0])
        if video_id:
            return {'type': 'embed', 'src': f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0"}

    if host in {'vimeo.com', 'player.vimeo.com'} or host.endswith('.vimeo.com'):
        parts = [part for part in parsed.path.split('/') if part]
        video_id = next((part for part in parts if part.isdigit()), '')
        if video_id:
            return {'type': 'embed', 'src': f"https://player.vimeo.com/video/{video_id}"}

    if host == 'instagram.com' or host.endswith('.instagram.com'):
        parts = [part for part in parsed.path.split('/') if part]
        for index, part in enumerate(parts):
            if part in {'p', 'reel', 'tv'} and len(parts) > index + 1 and re.match(r'^[A-Za-z0-9_-]+$', parts[index + 1]):
                return {'type': 'embed', 'src': f"https://www.instagram.com/{part}/{parts[index + 1]}/embed"}

    return {'type': 'external', 'src': value}

def ensure_video_comments_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS video_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY (video_id) REFERENCES videos (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    ensure_column(conn, 'video_comments', 'is_active', 'INTEGER DEFAULT 1')

def save_document_pdf(file):
    if not file or file.filename == '' or not allowed_file(file.filename, {'pdf'}):
        return None
    original = secure_filename(file.filename) or 'document.pdf'
    if not original.lower().endswith('.pdf'):
        original = f"{original}.pdf"
    filename = f"{uuid4().hex}_{original}"
    upload_folder = os.path.join(app.static_folder, 'documents')
    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)
    return {
        'file_url': document_url(filename),
        'file_name': file.filename,
        'file_path': f"static/documents/{filename}",
        'file_size': os.path.getsize(filepath),
    }

def ensure_documents_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS documents (
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
    ensure_column(conn, 'documents', 'file_url', "TEXT DEFAULT ''")
    ensure_column(conn, 'documents', 'file_name', "TEXT DEFAULT ''")
    ensure_column(conn, 'documents', 'file_size', 'INTEGER DEFAULT 0')
    ensure_column(conn, 'documents', 'official_date', "TEXT DEFAULT ''")
    ensure_column(conn, 'documents', 'reg_number', "TEXT DEFAULT ''")
    ensure_column(conn, 'documents', 'is_active', 'INTEGER DEFAULT 1')
    ensure_column(conn, 'documents', 'created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    ensure_column(conn, 'documents', 'file_path', "TEXT DEFAULT ''")
    ensure_column(conn, 'documents', 'file_type', "TEXT DEFAULT 'pdf'")
    ensure_column(conn, 'documents', 'upload_date', "TEXT DEFAULT ''")
    ensure_column(conn, 'documents', 'is_public', 'INTEGER DEFAULT 1')
    conn.execute(
        '''UPDATE documents
           SET file_url = CASE
                 WHEN COALESCE(file_url, '') != '' THEN file_url
                 WHEN COALESCE(file_path, '') LIKE 'static/documents/%' THEN '/' || substr(file_path, 8)
                 WHEN COALESCE(file_path, '') LIKE '/static/documents/%' THEN substr(file_path, 8)
                 WHEN COALESCE(file_path, '') LIKE 'documents/%' THEN '/' || file_path
                 WHEN COALESCE(file_path, '') LIKE '/documents/%' THEN file_path
                 ELSE COALESCE(file_path, '')
               END,
               official_date = COALESCE(NULLIF(official_date, ''), upload_date),
               is_active = COALESCE(is_active, is_public, 1)
           WHERE COALESCE(file_url, '') = ''
              OR COALESCE(official_date, '') = ''
              OR is_active IS NULL'''
    )

def seed_documents(conn):
    real_docs = conn.execute(
        "SELECT 1 FROM documents WHERE COALESCE(file_url, file_path, '') LIKE '%/documents/%' LIMIT 1"
    ).fetchone()
    if real_docs:
        return
    for item in DOCUMENT_SEED:
        file_url = document_url(item['filename'])
        conn.execute(
            '''INSERT INTO documents
               (title, category, description, file_url, file_name, file_size, official_date,
                reg_number, is_active, file_path, file_type, upload_date, is_public)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 'pdf', ?, 1)''',
            (
                item['title'],
                item['category'],
                item['description'],
                file_url,
                item['filename'],
                document_file_size(file_url),
                item['official_date'],
                item['reg_number'],
                f"static/documents/{item['filename']}",
                item['official_date'],
            ),
        )

def parse_photo_urls(value, fallback=''):
    photos = []
    if value:
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                photos.extend(str(item).strip() for item in parsed if str(item).strip())
        except (TypeError, ValueError, json.JSONDecodeError):
            photos.extend(item.strip() for item in str(value).split(',') if item.strip())
    if fallback and fallback not in photos:
        photos.insert(0, fallback)
    return list(dict.fromkeys(photos))

def form_photo_urls(value):
    return [item.strip() for item in (value or '').split(',') if item.strip()]

def horse_photo_files():
    files = []
    for field_name in ('horse_photo', 'horse_photos', 'photo'):
        files.extend(request.files.getlist(field_name))
    return [file for file in files if file and file.filename]

@app.template_filter('photo_urls_text')
def photo_urls_text(value):
    return ', '.join(parse_photo_urls(value))

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
    today = today_iso()
    matches = conn.execute('''SELECT * FROM matches
                              WHERE date >= ? AND COALESCE(status, 'scheduled') NOT IN ('finished', 'cancelled')
                              ORDER BY date, time, id''', (today,)).fetchall()
    total_news = conn.execute('SELECT COUNT(*) FROM news WHERE COALESCE(is_published, 1) = 1').fetchone()[0]
    news = conn.execute(
        '''SELECT * FROM news
           WHERE COALESCE(is_published, 1) = 1
           ORDER BY date DESC, id DESC LIMIT ? OFFSET ?''',
        (per_page, offset)
    ).fetchall()
    next_match = conn.execute(
        '''SELECT * FROM matches
           WHERE is_next = 1 AND date >= ? AND COALESCE(status, 'scheduled') NOT IN ('finished', 'cancelled')
           ORDER BY date,time,id LIMIT 1''', (today,)
    ).fetchone()
    if not next_match:
        next_match = conn.execute(
            '''SELECT * FROM matches
               WHERE date >= ? AND COALESCE(status, 'scheduled') NOT IN ('finished', 'cancelled')
               ORDER BY date, time, id LIMIT 1''',
            (today,)
        ).fetchone()

    context = {
        'matches': matches,
        'news': news,
        'next_match': next_match,
        'latest_result': conn.execute(
            '''SELECT * FROM match_archive
               ORDER BY match_date DESC, created_at DESC, id DESC LIMIT 1'''
        ).fetchone(),
        'top_teams': conn.execute(
            '''SELECT t.*, COUNT(p.id) AS player_count
               FROM teams t
               LEFT JOIN players p ON p.team_id = t.id OR (p.team_id IS NULL AND p.team = t.name)
               WHERE t.is_active = 1
               GROUP BY t.id
               ORDER BY t.points DESC, t.wins DESC, t.name LIMIT 6'''
        ).fetchall(),
        'leagues': conn.execute('SELECT * FROM leagues WHERE is_active = 1 ORDER BY category, name').fetchall(),
        'players': conn.execute('SELECT * FROM players WHERE is_active = 1 ORDER BY stats_points DESC, name').fetchall(),
        'documents': conn.execute('SELECT * FROM documents WHERE is_public = 1 ORDER BY upload_date DESC').fetchall(),
        'videos': conn.execute('''SELECT v.*, t.name AS team_name
                                  FROM videos v
                                  LEFT JOIN teams t ON t.id = v.team_id
                                  WHERE COALESCE(v.is_active, 1) = 1
                                  ORDER BY v.upload_date DESC, v.id DESC LIMIT 4''').fetchall(),
        'albums': conn.execute('''SELECT a.*, t.name AS team_name
                                  FROM photo_albums a
                                  LEFT JOIN teams t ON t.id = a.team_id
                                  WHERE COALESCE(a.is_active, 1) = 1
                                  ORDER BY a.upload_date DESC, a.id DESC LIMIT 4''').fetchall(),
        'homepage_settings': get_homepage_settings(conn),
        'homepage_stats': get_homepage_stats(conn),
        'featured_tandems': FEATURED_TANDEMS,
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
               WHERE COALESCE(is_published, 1) = 1
                 AND (title LIKE ? OR COALESCE(body, '') LIKE ?)
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
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        return jsonify({"status": "error", "message": "Введите корректный email."}), 400
    if len(password) < 6:
        return jsonify({"status": "error", "message": "Пароль должен быть минимум 6 символов."}), 400
    if password != confirm_password:
        return jsonify({"status": "error", "message": "Пароли не совпадают."}), 400

    now = datetime.utcnow()
    password_hash = generate_password_hash(password)
    conn = get_db_connection()
    existing = conn.execute('SELECT id, is_verified FROM users WHERE email = ?', (email,)).fetchone()

    if existing and existing['is_verified']:
        conn.close()
        return jsonify({"status": "error", "message": "Пользователь с таким email уже существует."}), 409

    if existing:
        user_id = existing['id']
        conn.execute(
            '''UPDATE users
               SET full_name = ?, password_hash = ?, is_active = 1, is_verified = 0, email_verified_at = NULL
               WHERE id = ?''',
            (fullname, password_hash, user_id)
        )
    else:
        conn.execute('''INSERT INTO users (full_name, email, password_hash, role, is_active, is_verified, created_at)
                        VALUES (?, ?, ?, 'user', 1, 0, ?)''',
                     (fullname, email, password_hash, now.isoformat()))
        user_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

    token, expires_at = create_email_confirmation(conn, user_id, email)
    conn.commit()
    conn.close()

    try:
        sent = send_registration_confirmation(email, fullname, token, expires_at)
    except Exception as error:
        logger.exception("Could not send registration confirmation to %s", email)
        return jsonify({
            "status": "error",
            "message": f"Аккаунт создан, но письмо подтверждения не отправилось. {smtp_user_message(error)}"
        }), 500

    message = "Мы отправили письмо с подтверждением. Откройте ссылку из письма, чтобы завершить регистрацию."
    if not sent:
        message = "Регистрация создана, но письмо не отправлено: SMTP не настроен. Ссылка подтверждения выведена в консоль сервера."
    return jsonify({"status": "success", "message": message})

@app.context_processor
def inject_contact_cards():
    try:
        return {'footer_contact_cards': get_active_contact_cards(), 'video_embed': video_embed}
    except sqlite3.Error:
        return {'footer_contact_cards': [], 'video_embed': video_embed}

def init_db():
    conn = get_db_connection()
    
    conn.execute('''CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, time TEXT, league TEXT,
        team1 TEXT, team2 TEXT, search_tags TEXT, is_next INTEGER DEFAULT 0
    )''')
    ensure_column(conn, 'matches', 'status', "TEXT DEFAULT 'scheduled'")
    ensure_column(conn, 'matches', 'location', "TEXT DEFAULT ''")
    ensure_column(conn, 'matches', 'tournament_name', "TEXT DEFAULT ''")
    ensure_column(conn, 'matches', 'round_name', "TEXT DEFAULT ''")

    conn.execute('''CREATE TABLE IF NOT EXISTS match_archive (
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
    conn.execute('CREATE INDEX IF NOT EXISTS idx_match_archive_date ON match_archive(match_date DESC, created_at DESC)')

    conn.execute('''CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, title TEXT, img_url TEXT, search_tags TEXT
    )''')

    news_columns = {row[1] for row in conn.execute('PRAGMA table_info(news)').fetchall()}
    if 'body' not in news_columns:
        conn.execute('ALTER TABLE news ADD COLUMN body TEXT')
    ensure_column(conn, 'news', 'is_published', 'INTEGER DEFAULT 1')
    ensure_column(conn, 'news', 'meta_title', "TEXT DEFAULT ''")
    ensure_column(conn, 'news', 'meta_description', "TEXT DEFAULT ''")

    conn.execute('''CREATE TABLE IF NOT EXISTS leagues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, category TEXT, description TEXT,
        teams_count INTEGER, stage TEXT, is_active INTEGER DEFAULT 1
    )''')

    ensure_documents_schema(conn)
    seed_documents(conn)

    conn.execute('''CREATE TABLE IF NOT EXISTS rules_sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        order_num INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS regulations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        file_path TEXT,
        regulation_date TEXT,
        order_num INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player TEXT NOT NULL,
        from_team TEXT NOT NULL,
        to_team TEXT NOT NULL,
        transfer_date TEXT NOT NULL,
        status TEXT DEFAULT 'На рассмотрении'
    )''')

    if not conn.execute('SELECT 1 FROM rules_sections LIMIT 1').fetchone():
        rules_sections = [
            ('1. Жалпы жоболор', '<p>Республиканын аймагында «Улак тартыш» оюну боюнча спорттук мелдештер <strong>«Улак тартыш» коомдук бирикмесинин</strong> чечими менен өткөрүлөт.</p><h3>Мелдештердин негизги максаттары:</h3><ul><li>«Улак тартыш» оюнун кеңири жайылтуу;</li><li>улуттук ат спортун өнүктүрүү;</li><li>көчмөн маданияттын салттарын сактоо;</li><li>спортчулардын чеберчилигин жогорулатуу.</li></ul>', 1, 1),
            ('2. Оюн аянтчасы', '<p>Оюн <strong>атайын даярдалган аянтчада</strong> өткөрүлөт.</p><h3>Аянтчанын негизги элементтери:</h3><ul><li>борбордук сызык жана борбордук аймак;</li><li>эсептик аймак (маара);</li><li>каптал жана маңдайкы чек аралар;</li><li>калыстар үчүн коопсуз аймак.</li></ul>', 2, 1),
            ('3. Командалар, убакыт жана объект', '<h3>Командалар жана курамы</h3><ul><li>6 негизги оюнчу талаада;</li><li>4 запастагы оюнчу алмаштыруу үчүн.</li></ul><h3>Оюндун узактыгы</h3><ul><li>негизги убакыт: 15 мүнөт;</li><li>кошумча тайм: 10 мүнөт.</li></ul>', 3, 1),
            ('4. Оюндун башталышы жана жүрүшү', '<h3>Оюндун башталышы</h3><ul><li>оюн аянтчанын төмөнкү аймагынан башталат;</li><li>калыс текени белгиленген жерге коёт;</li><li>ышкырыктан кийин оюнчулар күрөшкө киришет.</li></ul><p>Кооптуу кырдаал жаралса, калыс оюнду дароо токтотот.</p>', 4, 1),
            ('5. Талаптар, коопсуздук жана уюштуруу', '<h3>Аттарга жана катышуучуларга талаптар</h3><ul><li>аттар ден соолугу чың жана даяр болушу керек;</li><li>ветеринардык кароодон өтпөгөн аттар оюнга киргизилбейт;</li><li>кооптуу аракеттерге жана агрессияга тыюу салынат.</li></ul>', 5, 1),
        ]
        conn.executemany(
            'INSERT INTO rules_sections (title, content, order_num, is_active) VALUES (?, ?, ?, ?)',
            rules_sections,
        )

    if not conn.execute('SELECT 1 FROM regulations LIMIT 1').fetchone():
        regulations = [
            ('Регламент сезона 2026', 'Порядок проведения официальных матчей и турнирных этапов.', '/static/docs/ulak-tartysh-regulation-1.pdf', '2026-03-01', 1, 1),
            ('Положение о заявках команд', 'Требования к составам, срокам подачи и подтверждению заявок.', '/static/docs/team-application-1.pdf', '2026-02-15', 2, 1),
            ('Положение о судействе', 'Регламент назначения судей и оформления протоколов матчей.', '/static/docs/federation-protocol-4.pdf', '2026-01-20', 3, 1),
        ]
        conn.executemany(
            '''INSERT INTO regulations
               (title, description, file_path, regulation_date, order_num, is_active)
               VALUES (?, ?, ?, ?, ?, ?)''',
            regulations,
        )

    if not conn.execute('SELECT 1 FROM transfers LIMIT 1').fetchone():
        transfers = [
            ('Айбек Абдыразаков', 'Достук', 'Ынтымак', '2026-05-12', 'Подтверждён'),
            ('Руслан Ниязов', 'Ынтымак', 'Достук', '2026-04-28', 'На рассмотрении'),
            ('Тилек Сагынбаев', 'Намыс', 'Сары-Өзөн', '2026-04-10', 'Подтверждён'),
        ]
        conn.executemany(
            '''INSERT INTO transfers (player, from_team, to_team, transfer_date, status)
               VALUES (?, ?, ?, ?, ?)''',
            transfers,
        )

    conn.execute('''CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, photo_url TEXT, team TEXT, position TEXT,
        stats_points INTEGER DEFAULT 0, stats_matches INTEGER DEFAULT 0,
        birth_year INTEGER, region TEXT, is_active INTEGER DEFAULT 1
    )''')

    player_columns = {row[1] for row in conn.execute('PRAGMA table_info(players)').fetchall()}
    if 'team_id' not in player_columns:
        conn.execute('ALTER TABLE players ADD COLUMN team_id INTEGER')
    ensure_column(conn, 'players', 'jersey_number', 'INTEGER')
    ensure_column(conn, 'players', 'bio', "TEXT DEFAULT ''")

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
    horse_columns = {row[1] for row in conn.execute('PRAGMA table_info(horses)').fetchall()}
    if 'photo_urls' not in horse_columns:
        conn.execute("ALTER TABLE horses ADD COLUMN photo_urls TEXT DEFAULT ''")
    if 'phone' not in horse_columns:
        conn.execute("ALTER TABLE horses ADD COLUMN phone TEXT DEFAULT ''")
    legacy_horse_photos = conn.execute(
        '''SELECT id, photo_url FROM horses
           WHERE COALESCE(photo_urls, '') = '' AND COALESCE(photo_url, '') != '' '''
    ).fetchall()
    conn.executemany(
        'UPDATE horses SET photo_urls = ? WHERE id = ?',
        [(json.dumps([row['photo_url']]), row['id']) for row in legacy_horse_photos],
    )

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
    ensure_column(conn, 'videos', 'archive_match_id', 'INTEGER')
    ensure_column(conn, 'videos', 'team_id', 'INTEGER')
    ensure_column(conn, 'videos', 'tournament_name', "TEXT DEFAULT ''")
    ensure_column(conn, 'videos', 'description', "TEXT DEFAULT ''")
    ensure_column(conn, 'videos', 'is_active', 'INTEGER DEFAULT 1')

    conn.execute('''CREATE TABLE IF NOT EXISTS photo_albums (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, match_id INTEGER, cover_url TEXT,
        upload_date TEXT, photo_count INTEGER DEFAULT 0
    )''')
    ensure_column(conn, 'photo_albums', 'archive_match_id', 'INTEGER')
    ensure_column(conn, 'photo_albums', 'team_id', 'INTEGER')
    ensure_column(conn, 'photo_albums', 'tournament_name', "TEXT DEFAULT ''")
    ensure_column(conn, 'photo_albums', 'description', "TEXT DEFAULT ''")
    ensure_column(conn, 'photo_albums', 'is_active', 'INTEGER DEFAULT 1')
    ensure_column(conn, 'photo_albums', 'meta_title', "TEXT DEFAULT ''")
    ensure_column(conn, 'photo_albums', 'meta_description', "TEXT DEFAULT ''")

    conn.execute('''CREATE TABLE IF NOT EXISTS photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        album_id INTEGER, photo_url TEXT, caption TEXT,
        FOREIGN KEY (album_id) REFERENCES photo_albums (id)
    )''')
    ensure_column(conn, 'photos', 'order_num', 'INTEGER DEFAULT 0')

    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        is_active INTEGER DEFAULT 1,
        is_verified INTEGER DEFAULT 1,
        email_verified_at TEXT,
        created_at TEXT NOT NULL
    )''')
    user_columns = {row[1] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
    if 'photo_url' not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN photo_url TEXT DEFAULT ''")
    if 'phone' not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''")
    if 'role' not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    if 'is_active' not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
    if 'is_verified' not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 1")
    if 'email_verified_at' not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN email_verified_at TEXT")
    conn.execute("UPDATE users SET role = 'user' WHERE role IS NULL OR role NOT IN ('user', 'admin')")
    conn.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
    conn.execute("UPDATE users SET is_verified = 1 WHERE is_verified IS NULL")

    ensure_email_confirmations_schema(conn)
    ensure_video_comments_schema(conn)
    conn.execute('DROP TABLE IF EXISTS ticket_requests')

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
    conn = get_db_connection()
    sections = conn.execute(
        '''SELECT * FROM rules_sections
           WHERE is_active = 1
           ORDER BY order_num, id'''
    ).fetchall()
    conn.close()
    return render_template('rules.html', sections=sections)

@app.route('/documents')
def documents_page():
    content = site_content()
    conn = get_db_connection()
    db_documents = conn.execute('SELECT * FROM documents WHERE is_public = 1 ORDER BY upload_date DESC').fetchall()
    conn.close()
    return render_template('documents.html', **content, db_documents=db_documents)

@app.route('/all-documents')
def all_documents():
    conn = get_db_connection()
    documents = conn.execute(
        '''SELECT * FROM documents
           WHERE COALESCE(is_active, is_public, 1) = 1
           ORDER BY COALESCE(NULLIF(official_date, ''), upload_date) DESC, id DESC'''
    ).fetchall()
    conn.close()
    return render_template('all_documents.html', documents=documents)

@app.route('/documents/<path:filename>')
def document_file(filename):
    return send_from_directory(
        os.path.join(app.static_folder, 'documents'),
        filename,
        as_attachment=request.args.get('view') != '1',
    )

@app.route('/media')
def media_page():
    conn = get_db_connection()
    videos = conn.execute(
        '''SELECT v.*, m.date AS match_date, m.team1, m.team2,
                  ma.match_date AS archive_match_date, ma.team1_name, ma.team2_name,
                  t.name AS team_name
           FROM videos v
           LEFT JOIN matches m ON m.id = v.match_id
           LEFT JOIN match_archive ma ON ma.id = v.archive_match_id
           LEFT JOIN teams t ON t.id = v.team_id
           WHERE COALESCE(v.is_active, 1) = 1
             AND TRIM(COALESCE(v.category, '')) NOT IN
                 ('Обзор', 'обзор', 'Review', 'review', 'Overview', 'overview')
           ORDER BY v.upload_date DESC, v.id DESC'''
    ).fetchall()
    reviews = conn.execute(
        '''SELECT v.*, m.date AS match_date, m.team1, m.team2,
                  ma.match_date AS archive_match_date, ma.team1_name, ma.team2_name,
                  t.name AS team_name
           FROM videos v
           LEFT JOIN matches m ON m.id = v.match_id
           LEFT JOIN match_archive ma ON ma.id = v.archive_match_id
           LEFT JOIN teams t ON t.id = v.team_id
           WHERE COALESCE(v.is_active, 1) = 1
             AND TRIM(COALESCE(v.category, '')) IN
                 ('Обзор', 'обзор', 'Review', 'review', 'Overview', 'overview')
           ORDER BY v.upload_date DESC, v.id DESC'''
    ).fetchall()
    albums = conn.execute(
        '''SELECT a.*, COUNT(p.id) AS actual_photo_count,
                  COALESCE(NULLIF(a.cover_url, ''), MIN(p.photo_url)) AS cover_image,
                  m.date AS match_date, m.team1, m.team2,
                  ma.match_date AS archive_match_date, ma.team1_name, ma.team2_name,
                  t.name AS team_name
           FROM photo_albums a
           LEFT JOIN photos p ON p.album_id = a.id
           LEFT JOIN matches m ON m.id = a.match_id
           LEFT JOIN match_archive ma ON ma.id = a.archive_match_id
           LEFT JOIN teams t ON t.id = a.team_id
           WHERE COALESCE(a.is_active, 1) = 1
           GROUP BY a.id
           ORDER BY a.upload_date DESC, a.id DESC'''
    ).fetchall()
    conn.close()
    return render_template('media.html', videos=videos, reviews=reviews, albums=albums)

@app.route('/media/<int:video_id>')
def media_detail(video_id):
    conn = get_db_connection()
    ensure_video_comments_schema(conn)
    video = conn.execute(
        '''SELECT v.*, m.date AS match_date, m.team1, m.team2,
                  ma.match_date AS archive_match_date, ma.team1_name, ma.team2_name,
                  t.name AS team_name
           FROM videos v
           LEFT JOIN matches m ON m.id = v.match_id
           LEFT JOIN match_archive ma ON ma.id = v.archive_match_id
           LEFT JOIN teams t ON t.id = v.team_id
           WHERE v.id = ? AND COALESCE(v.is_active, 1) = 1''',
        (video_id,)
    ).fetchone()
    if not video:
        conn.close()
        return render_template('errors/404.html'), 404

    conn.execute('UPDATE videos SET views = COALESCE(views, 0) + 1 WHERE id = ?', (video_id,))
    comments = conn.execute(
        '''SELECT c.*, u.full_name, u.photo_url
           FROM video_comments c
           LEFT JOIN users u ON u.id = c.user_id
           WHERE c.video_id = ? AND COALESCE(c.is_active, 1) = 1
           ORDER BY c.created_at DESC, c.id DESC''',
        (video_id,)
    ).fetchall()
    other_videos = conn.execute(
        '''SELECT v.*, t.name AS team_name
           FROM videos v
           LEFT JOIN teams t ON t.id = v.team_id
           WHERE v.id != ? AND COALESCE(v.is_active, 1) = 1
           ORDER BY CASE WHEN COALESCE(v.category, '') = COALESCE(?, '') THEN 0 ELSE 1 END,
                    v.upload_date DESC, v.id DESC
           LIMIT 8''',
        (video_id, video['category'] or '')
    ).fetchall()
    conn.commit()
    conn.close()
    return render_template('video_detail.html', video=video, comments=comments, other_videos=other_videos)

@app.route('/media/<int:video_id>/comments', methods=['POST'])
def add_video_comment(video_id):
    user_id = session.get('user_id')
    if not user_id:
        flash('Комментарий калтыруу үчүн кириңиз же катталыңыз.', 'error')
        return redirect(url_for('media_detail', video_id=video_id) + '#comments')

    body = request.form.get('body', '').strip()
    if not body or len(body) > 1000:
        flash('Комментарий должен содержать от 1 до 1000 символов.', 'error')
        return redirect(url_for('media_detail', video_id=video_id) + '#comments')

    conn = get_db_connection()
    ensure_video_comments_schema(conn)
    video = conn.execute('SELECT id FROM videos WHERE id = ? AND COALESCE(is_active, 1) = 1', (video_id,)).fetchone()
    user = conn.execute('SELECT id, is_active FROM users WHERE id = ?', (user_id,)).fetchone()
    if not video or not user or not user['is_active']:
        conn.close()
        flash('Комментарий сакталган жок.', 'error')
        return redirect(url_for('media_detail', video_id=video_id))

    conn.execute(
        '''INSERT INTO video_comments (video_id, user_id, body, created_at, is_active)
           VALUES (?, ?, ?, ?, 1)''',
        (video_id, user_id, body, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    flash('Комментарий кошулду.', 'success')
    return redirect(url_for('media_detail', video_id=video_id) + '#comments')

@app.route('/media/albums/<int:album_id>')
def album_detail(album_id):
    conn = get_db_connection()
    album = conn.execute(
        '''SELECT a.*, COUNT(p.id) AS actual_photo_count,
                  COALESCE(NULLIF(a.cover_url, ''), MIN(p.photo_url)) AS cover_image,
                  m.date AS match_date, m.team1, m.team2,
                  ma.match_date AS archive_match_date, ma.team1_name, ma.team2_name,
                  t.name AS team_name
           FROM photo_albums a
           LEFT JOIN photos p ON p.album_id = a.id
           LEFT JOIN matches m ON m.id = a.match_id
           LEFT JOIN match_archive ma ON ma.id = a.archive_match_id
           LEFT JOIN teams t ON t.id = a.team_id
           WHERE a.id = ? AND COALESCE(a.is_active, 1) = 1
           GROUP BY a.id''',
        (album_id,)
    ).fetchone()
    if not album:
        conn.close()
        return render_template('errors/404.html'), 404
    photos = conn.execute(
        '''SELECT * FROM photos
           WHERE album_id = ?
           ORDER BY order_num, id''',
        (album_id,)
    ).fetchall()
    conn.close()
    gallery_photos = [row_to_dict(photo) for photo in photos]
    if album['cover_image'] and not any(photo['photo_url'] == album['cover_image'] for photo in gallery_photos):
        gallery_photos.insert(0, {'id': 0, 'album_id': album_id, 'photo_url': album['cover_image'], 'caption': album['title'], 'order_num': 0})
    album_image = album['cover_image'] or (gallery_photos[0]['photo_url'] if gallery_photos else '')
    if album_image and album_image.startswith('/'):
        album_image = request.url_root.rstrip('/') + album_image
    return render_template('album_detail.html', album=album, photos=gallery_photos, album_og_image=album_image)

@app.route('/archive')
def archive():
    conn = get_db_connection()
    matches = conn.execute('''
        SELECT * FROM match_archive
        ORDER BY match_date DESC, created_at DESC
    ''').fetchall()
    seasons = conn.execute('''
        SELECT DISTINCT season FROM match_archive
        WHERE COALESCE(season, '') != ''
        ORDER BY season DESC
    ''').fetchall()
    leagues = conn.execute('''
        SELECT DISTINCT league FROM match_archive
        WHERE COALESCE(league, '') != ''
        ORDER BY league
    ''').fetchall()
    tournaments = conn.execute('''
        SELECT DISTINCT tournament_name FROM match_archive
        WHERE COALESCE(tournament_name, '') != ''
        ORDER BY tournament_name
    ''').fetchall()
    conn.close()
    return render_template(
        'archive.html',
        matches=matches,
        seasons=seasons,
        leagues=leagues,
        tournaments=tournaments,
    )

@app.route('/archive/match/<int:match_id>')
def match_detail(match_id):
    conn = get_db_connection()
    match = conn.execute('SELECT * FROM match_archive WHERE id = ?', (match_id,)).fetchone()
    if not match:
        conn.close()
        return render_template('errors/404.html'), 404
    gallery = [item.strip() for item in (match['photo_gallery'] or '').split(',') if item.strip()]
    videos = conn.execute(
        '''SELECT * FROM videos
           WHERE archive_match_id = ?
              OR (COALESCE(tournament_name, '') != '' AND tournament_name = ?)
           ORDER BY upload_date DESC, id DESC''',
        (match_id, match['tournament_name'] or '')
    ).fetchall()
    albums = conn.execute(
        '''SELECT a.*, COUNT(p.id) AS actual_photo_count,
                  COALESCE(NULLIF(a.cover_url, ''), MIN(p.photo_url)) AS cover_image
           FROM photo_albums a
           LEFT JOIN photos p ON p.album_id = a.id
           WHERE a.archive_match_id = ?
              OR (COALESCE(a.tournament_name, '') != '' AND a.tournament_name = ?)
           GROUP BY a.id
           ORDER BY a.upload_date DESC, a.id DESC''',
        (match_id, match['tournament_name'] or '')
    ).fetchall()
    conn.close()
    return render_template('match_detail.html', match=match, gallery=gallery, videos=videos, albums=albums)

@app.route('/news')
@app.route('/newlist')
def news_page():
    conn = get_db_connection()
    news = conn.execute(
        '''SELECT * FROM news
           WHERE COALESCE(is_published, 1) = 1
           ORDER BY date DESC, id DESC'''
    ).fetchall()
    conn.close()
    return render_template('newlist.html', news=news)

@app.route('/news/<int:news_id>')
def news_detail_page(news_id):
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM news WHERE id = ?', (news_id,)).fetchone()
    conn.close()
    if not item or (not session.get('logged_in') and not item['is_published']):
        return render_template('errors/404.html'), 404
    og_image = item['img_url'] or ''
    if og_image and og_image.startswith('/'):
        og_image = request.url_root.rstrip('/') + og_image
    return render_template('news_detail.html', item=item, news_og_image=og_image)


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
    upcoming_matches = conn.execute(
        '''SELECT * FROM matches
           WHERE (team1 = ? OR team2 = ?) AND date >= ? AND COALESCE(status, 'scheduled') NOT IN ('finished','cancelled')
           ORDER BY date, time, id LIMIT 6''',
        (team['name'], team['name'], today_iso())
    ).fetchall()
    archive_matches = conn.execute(
        '''SELECT * FROM match_archive
           WHERE team1_name = ? OR team2_name = ?
           ORDER BY match_date DESC, created_at DESC LIMIT 6''',
        (team['name'], team['name'])
    ).fetchall()
    videos = conn.execute(
        '''SELECT * FROM videos
           WHERE team_id = ?
           ORDER BY upload_date DESC, id DESC LIMIT 4''',
        (team_id,)
    ).fetchall()
    albums = conn.execute(
        '''SELECT a.*, COUNT(p.id) AS actual_photo_count,
                  COALESCE(NULLIF(a.cover_url, ''), MIN(p.photo_url)) AS cover_image
           FROM photo_albums a
           LEFT JOIN photos p ON p.album_id = a.id
           WHERE a.team_id = ?
           GROUP BY a.id
           ORDER BY a.upload_date DESC, a.id DESC LIMIT 4''',
        (team_id,)
    ).fetchall()
    conn.close()
    return render_template(
        'team_detail.html',
        team=team,
        players=players,
        upcoming_matches=upcoming_matches,
        archive_matches=archive_matches,
        videos=videos,
        albums=albums,
    )

@app.route('/players')
def players_page():
    conn = get_db_connection()
    players = conn.execute(
        '''SELECT p.*, t.name AS team_name, t.photo_url AS team_photo, t.league AS team_league
           FROM players p
           LEFT JOIN teams t ON t.id = p.team_id
           WHERE p.is_active = 1
           ORDER BY p.stats_points DESC, p.stats_matches DESC, p.name'''
    ).fetchall()
    teams = conn.execute(
        'SELECT id, name FROM teams WHERE is_active = 1 ORDER BY name'
    ).fetchall()
    conn.close()
    return render_template('players.html', players=players, teams=teams)

@app.route('/players/<int:player_id>')
def player_detail_page(player_id):
    conn = get_db_connection()
    player = conn.execute(
        '''SELECT p.*, t.id AS linked_team_id, t.name AS team_name, t.region AS team_region,
                  t.league AS team_league, t.photo_url AS team_photo, t.wins AS team_wins,
                  t.points AS team_points
           FROM players p
           LEFT JOIN teams t ON t.id = p.team_id OR (p.team_id IS NULL AND t.name = p.team)
           WHERE p.id = ? AND p.is_active = 1''',
        (player_id,)
    ).fetchone()
    if not player:
        conn.close()
        return render_template('errors/404.html'), 404

    team_name = player['team_name'] or player['team'] or ''
    upcoming_matches = conn.execute(
        '''SELECT * FROM matches
           WHERE (team1 = ? OR team2 = ?) AND date >= ? AND COALESCE(status, 'scheduled') NOT IN ('finished','cancelled')
           ORDER BY date, time, id LIMIT 8''',
        (team_name, team_name, today_iso())
    ).fetchall()
    archive_matches = conn.execute(
        '''SELECT * FROM match_archive
           WHERE team1_name = ? OR team2_name = ?
           ORDER BY match_date DESC, created_at DESC LIMIT 8''',
        (team_name, team_name)
    ).fetchall()
    team_players = conn.execute(
        '''SELECT id, name, position, stats_points
           FROM players
           WHERE is_active = 1 AND id != ? AND (team = ? OR team_id = ?)
           ORDER BY stats_points DESC, name LIMIT 4''',
        (player_id, team_name, player['linked_team_id'])
    ).fetchall()
    conn.close()
    return render_template(
        'player_detail.html',
        player=player,
        upcoming_matches=upcoming_matches,
        archive_matches=archive_matches,
        team_players=team_players,
    )

@app.route('/statistics')
def statistics_page():
    conn = get_db_connection()
    top_teams = conn.execute(
        '''SELECT t.*, COUNT(p.id) AS player_count
           FROM teams t
           LEFT JOIN players p ON p.team_id = t.id OR (p.team_id IS NULL AND p.team = t.name)
           WHERE t.is_active = 1
           GROUP BY t.id
           ORDER BY t.points DESC, t.wins DESC, t.name'''
    ).fetchall()
    top_players = conn.execute(
        '''SELECT p.*, COALESCE(t.name, p.team) AS display_team
           FROM players p
           LEFT JOIN teams t ON t.id = p.team_id
           WHERE p.is_active = 1
           ORDER BY p.stats_points DESC, p.stats_matches DESC, p.name LIMIT 12'''
    ).fetchall()
    recent_matches = conn.execute(
        '''SELECT * FROM match_archive
           ORDER BY match_date DESC, created_at DESC, id DESC LIMIT 12'''
    ).fetchall()
    league_totals = conn.execute(
        '''SELECT league,
                  COUNT(*) AS matches_count,
                  SUM(team1_score + team2_score) AS total_points
           FROM match_archive
           WHERE COALESCE(league, '') != ''
           GROUP BY league
           ORDER BY matches_count DESC, league'''
    ).fetchall()
    conn.close()
    return render_template(
        'statistics.html',
        top_teams=top_teams,
        top_players=top_players,
        recent_matches=recent_matches,
        league_totals=league_totals,
    )

@app.route('/horses')
def horses_page():
    filters = {key: request.args.get(key, '').strip()[:100]
               for key in ['q', 'breed', 'region', 'sale', 'min_price', 'max_price', 'min_age', 'max_age', 'sort']}
    where, params = ['is_active = 1'], []
    if filters['q']:
        where.append('(name LIKE ? OR breed LIKE ? OR color LIKE ? OR owner_name LIKE ?)')
        params.extend(['%' + filters['q'] + '%'] * 4)
    for field in ['breed', 'region']:
        if filters[field]:
            where.append(field + ' = ?')
            params.append(filters[field])
    if filters['sale'] in ['sale', 'not-sale']:
        where.append('is_for_sale = ?')
        params.append(int(filters['sale'] == 'sale'))
    for key,field,operator in [('min_price','price','>='),('max_price','price','<='),('min_age','age','>='),('max_age','age','<=')]:
        if filters[key].isdigit() and len(filters[key]) <= 10:
            where.append(f'{field} {operator} ?')
            params.append(int(filters[key]))
        else:
            filters[key] = ''
    sort = {'points': 'points DESC, name', 'price': 'price IS NULL, price, name',
            'age': 'age IS NULL, age, name', 'name': 'name'}.get(filters['sort'], 'points DESC, name')
    conn = get_db_connection()
    try:
        total = conn.execute('SELECT COUNT(*) FROM horses WHERE ' + ' AND '.join(where), params).fetchone()[0]
        pages = max(1, (total + 23) // 24)
        page = min(max(form_int_or_none(request.args.get('page')) or 1, 1), pages)
        horses = conn.execute('SELECT * FROM horses WHERE ' + ' AND '.join(where) + ' ORDER BY ' + sort + ' LIMIT 24 OFFSET ?', params + [(page - 1) * 24]).fetchall()
        breeds = [row[0] for row in conn.execute("SELECT DISTINCT breed FROM horses WHERE is_active=1 AND COALESCE(breed,'')!='' ORDER BY breed")]
        regions = [row[0] for row in conn.execute("SELECT DISTINCT region FROM horses WHERE is_active=1 AND COALESCE(region,'')!='' ORDER BY region")]
    finally:
        conn.close()
    def page_url(number):
        return url_for('horses_page', **{k:v for k,v in filters.items() if v}, page=number)
    return render_template('horses.html', horses=horses, filters=filters, breeds=breeds,
                           regions=regions, total=total, page=page, pages=pages, page_url=page_url)

@app.route('/horses/<int:horse_id>')
def horse_detail_page(horse_id):
    conn = get_db_connection()
    horse = conn.execute('SELECT * FROM horses WHERE id = ? AND is_active = 1', (horse_id,)).fetchone()
    conn.close()
    if not horse:
        return render_template('errors/404.html'), 404
    photos = parse_photo_urls(horse['photo_urls'], horse['photo_url'])
    return render_template(
        'horse_detail.html',
        horse=horse,
        photos=photos,
        main_photo=photos[0] if photos else '',
        phone_href=re.sub(r'[^\d+]', '', horse['phone'] or ''),
        whatsapp_phone=re.sub(r'\D', '', horse['phone'] or ''),
    )

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
    user = conn.execute('''SELECT id, full_name, email, photo_url, phone, created_at, role, is_active
                           FROM users WHERE id = ?''', (user_id,)).fetchone()
    if not user or not user['is_active']:
        conn.close()
        session.pop('user_id', None)
        session.pop('user_name', None)
        session.pop('logged_in', None)
        return redirect(url_for('home'))

    conn.close()
    return render_template('profile.html', user=user)

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
    user = conn.execute('SELECT is_active FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user or not user['is_active']:
        conn.close()
        session.clear()
        return jsonify({'status': 'error', 'message': 'Аккаунт заблокирован администратором.'}), 403
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
    if not 6 <= len(new_password) <= 128:
        return jsonify({'status': 'error', 'message': 'Жаңы сыр сөз кеминде 6 символ болушу керек.'}), 400

    conn = get_db_connection()
    user = conn.execute('SELECT password_hash, is_active FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user or not user['is_active']:
        conn.close()
        session.clear()
        return jsonify({'status': 'error', 'message': 'Аккаунт заблокирован администратором.'}), 403
    if not check_password_hash(user['password_hash'], old_password):
        conn.close()
        return jsonify({'status': 'error', 'message': 'Эски сыр сөз туура эмес.'}), 400

    conn.execute('UPDATE users SET password_hash = ?, auth_version=auth_version+1 WHERE id = ?', (generate_password_hash(new_password), user_id))
    session['auth_version'] = conn.execute('SELECT auth_version FROM users WHERE id=?', (user_id,)).fetchone()[0]
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
    conn = get_db_connection()
    regulations = conn.execute(
        '''SELECT * FROM regulations
           WHERE is_active = 1
           ORDER BY order_num, regulation_date DESC, id'''
    ).fetchall()
    conn.close()
    return render_template('regulations.html', regulations=regulations)

@pages_bp.route('/transfers')
def transfers_page():
    conn = get_db_connection()
    transfers = conn.execute(
        'SELECT * FROM transfers ORDER BY transfer_date DESC, id DESC'
    ).fetchall()
    conn.close()
    return render_template('transfers.html', transfers=transfers)

@pages_bp.route('/league/higher')
def league_higher_page():
    standings, matches = league_payload('Жогорку лига')
    return render_template('league_higher.html', league_name='Жогорку лига', standings=standings, matches=matches)

@pages_bp.route('/league/first')
def league_first_page():
    standings, matches = league_payload('Биринчи лига')
    return render_template('league_first.html', league_name='Биринчи лига', standings=standings, matches=matches)

@app.route('/confirm-email/<token>')
def confirm_email(token):
    conn = get_db_connection()
    confirmation = conn.execute(
        '''SELECT ec.id, ec.user_id, ec.email, ec.expires_at, ec.used_at, u.full_name, u.is_active
           FROM email_confirmations ec
           JOIN users u ON u.id = ec.user_id
           WHERE ec.token_hash = ?''',
        (token_digest(token),)
    ).fetchone()

    if not confirmation or confirmation['used_at']:
        conn.close()
        flash('Ссылка подтверждения недействительна или уже использована.', 'error')
        return redirect(url_for('home'))

    try:
        expires_at = datetime.fromisoformat(confirmation['expires_at'])
    except ValueError:
        expires_at = datetime.utcnow() - timedelta(seconds=1)

    if expires_at < datetime.utcnow():
        conn.execute('UPDATE email_confirmations SET used_at = ? WHERE id = ?', (datetime.utcnow().isoformat(), confirmation['id']))
        conn.commit()
        conn.close()
        flash('Срок действия ссылки истёк. Зарегистрируйтесь ещё раз, чтобы получить новую ссылку.', 'error')
        return redirect(url_for('home'))

    if not confirmation['is_active']:
        conn.close()
        flash('Аккаунт заблокирован администратором.', 'error')
        return redirect(url_for('home'))

    now = datetime.utcnow().isoformat()
    conn.execute(
        'UPDATE users SET is_verified = 1, email_verified_at = ? WHERE id = ?',
        (now, confirmation['user_id'])
    )
    conn.execute(
        'UPDATE email_confirmations SET used_at = ? WHERE id = ?',
        (now, confirmation['id'])
    )
    conn.commit()
    conn.close()

    auth_conn = get_db_connection()
    session['auth_version'] = auth_conn.execute('SELECT auth_version FROM users WHERE id=?', (confirmation['user_id'],)).fetchone()[0]
    auth_conn.close()
    session['user_id'] = confirmation['user_id']
    session['user_name'] = confirmation['full_name']
    flash('Email подтверждён. Регистрация завершена.', 'success')
    return redirect(url_for('profile_page'))

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json() or request.form.to_dict()
    payload = data.get('payload') if isinstance(data, dict) and data.get('payload') else data
    return register_user_from_payload(payload)

@app.route('/api/submit', methods=['POST'])
def handle_submissions():
    data = request.get_json() or request.form.to_dict()
    # Never log form payloads: login and registration contain passwords.

    if data.get('form_type') == 'register':
        return register_user_from_payload(data.get('payload') or {})

    if data.get('form_type') == 'login':
        payload = data.get('payload') or {}
        email = payload.get('email', '').strip().lower()
        password = payload.get('password', '')

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

        if not user or not check_password_hash(user['password_hash'], password):
            conn.close()
            return jsonify({"status": "error", "message": "Неверный email или пароль."}), 401
        if not user['is_active']:
            conn.close()
            return jsonify({"status": "error", "message": "Аккаунт заблокирован администратором."}), 403
        if user['role'] != 'admin' and not user['is_verified']:
            token, expires_at = create_email_confirmation(conn, user['id'], user['email'])
            conn.commit()
            conn.close()
            try:
                sent = send_registration_confirmation(user['email'], user['full_name'], token, expires_at)
            except Exception as error:
                logger.exception("Could not resend registration confirmation to %s", user['email'])
                return jsonify({
                    "status": "error",
                    "message": f"Email ещё не подтверждён. {smtp_user_message(error)}"
                }), 500
            if not sent:
                return jsonify({
                    "status": "error",
                    "message": "Email ещё не подтверждён. SMTP не настроен, ссылка подтверждения выведена в консоль сервера."
                }), 403
            return jsonify({
                "status": "error",
                "message": "Email ещё не подтверждён. Мы отправили новое письмо со ссылкой подтверждения."
            }), 403

        session['auth_version'] = user['auth_version']
        session['user_id'] = user['id']
        session['user_name'] = user['full_name']
        if user['role'] == 'admin':
            session['logged_in'] = True
        conn.close()
        return jsonify({"status": "success", "message": f"Добро пожаловать, {user['full_name']}!", "reload": True})

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
        'news': conn.execute('SELECT * FROM news ORDER BY date DESC, id DESC').fetchall(),
        'news_totals': conn.execute(
            '''SELECT COUNT(*) AS total,
                      SUM(CASE WHEN COALESCE(is_published, 1) = 1 THEN 1 ELSE 0 END) AS published,
                      SUM(CASE WHEN COALESCE(is_published, 1) = 0 THEN 1 ELSE 0 END) AS drafts
               FROM news'''
        ).fetchone(),
        'leagues': conn.execute('SELECT * FROM leagues').fetchall(),
        'teams': conn.execute('SELECT * FROM teams WHERE is_active = 1 ORDER BY league, name').fetchall(),
        'documents': conn.execute(
            '''SELECT * FROM documents
               ORDER BY COALESCE(NULLIF(official_date, ''), upload_date) DESC, id DESC'''
        ).fetchall(),
        'document_categories': DOCUMENT_CATEGORIES,
        'players': conn.execute('SELECT * FROM players ORDER BY stats_points DESC, name').fetchall(),
        'horses': conn.execute('SELECT * FROM horses ORDER BY points DESC, name').fetchall(),
        'referees': conn.execute('SELECT * FROM referees').fetchall(),
        'hippodromes': conn.execute('SELECT * FROM hippodromes').fetchall(),
        'videos': conn.execute('''SELECT v.*, t.name AS team_name
                                  FROM videos v
                                  LEFT JOIN teams t ON t.id = v.team_id
                                  ORDER BY v.upload_date DESC, v.id DESC''').fetchall(),
        'albums': conn.execute('''SELECT a.*, COUNT(p.id) as actual_photo_count, t.name AS team_name,
                                         COALESCE(NULLIF(a.cover_url, ''), MIN(p.photo_url)) AS cover_image
                                  FROM photo_albums a
                                  LEFT JOIN photos p ON a.id = p.album_id
                                  LEFT JOIN teams t ON t.id = a.team_id
                                  GROUP BY a.id
                                  ORDER BY a.upload_date DESC, a.id DESC''').fetchall(),
        'album_photos': conn.execute('SELECT * FROM photos ORDER BY album_id, order_num, id').fetchall(),
        'archive_matches': conn.execute('SELECT * FROM match_archive ORDER BY match_date DESC, created_at DESC').fetchall(),
        'users': conn.execute('''SELECT id, full_name, email, phone, role, is_active, created_at
                                 FROM users ORDER BY created_at DESC''').fetchall(),
        'contact_cards': conn.execute('SELECT * FROM contact_cards ORDER BY order_num, id').fetchall(),
        'homepage_settings': get_homepage_settings(conn),
        'homepage_stats': conn.execute('SELECT * FROM homepage_stats ORDER BY order_num, id').fetchall(),
    }
    conn.close()
    return render_template('admin/dashboard.html', **data)

@app.route('/admin/users')
def admin_users():
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))

    query = request.args.get('q', '').strip()
    role = request.args.get('role', '').strip()
    status = request.args.get('status', '').strip()
    conditions = []
    params = []

    if query:
        conditions.append('(full_name LIKE ? OR email LIKE ? OR COALESCE(phone, "") LIKE ?)')
        search_term = f'%{query}%'
        params.extend([search_term, search_term, search_term])
    if role in {'user', 'admin'}:
        conditions.append('role = ?')
        params.append(role)
    if status in {'active', 'blocked'}:
        conditions.append('is_active = ?')
        params.append(1 if status == 'active' else 0)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ''
    conn = get_db_connection()
    users = conn.execute(
        f'''SELECT id, full_name, email, phone, role, is_active, created_at
            FROM users {where_clause}
            ORDER BY created_at DESC, id DESC''',
        params,
    ).fetchall()
    totals = conn.execute(
        '''SELECT COUNT(*) AS total,
                  SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END) AS admins,
                  SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) AS blocked
           FROM users'''
    ).fetchone()
    conn.close()
    return render_template(
        'admin/users.html',
        users=users,
        totals=totals,
        query=query,
        role_filter=role,
        status_filter=status,
    )

@app.route('/admin/users/<int:user_id>')
def admin_user_detail(user_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))

    conn = get_db_connection()
    user = conn.execute(
        '''SELECT id, full_name, email, phone, photo_url, role, is_active, created_at
           FROM users WHERE id = ?''',
        (user_id,),
    ).fetchone()
    conn.close()
    if not user:
        return redirect(url_for('admin_users', error='Пользователь не найден.'))
    return render_template('admin/user_detail.html', user=user)

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
def admin_user_edit(user_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        return redirect(url_for('admin_users', error='Пользователь не найден.'))

    if request.method == 'GET':
        conn.close()
        return render_template('admin/user_edit.html', user=user)

    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'user')
    is_active = 1 if request.form.get('is_active') else 0

    if not full_name or not email:
        conn.close()
        return render_template('admin/user_edit.html', user=user, error='Имя и email обязательны.')
    if role not in {'user', 'admin'}:
        role = 'user'
    if password and len(password) < 6:
        conn.close()
        return render_template('admin/user_edit.html', user=user, error='Пароль должен содержать минимум 6 символов.')

    try:
        if password:
            conn.execute(
                '''UPDATE users
                   SET full_name = ?, email = ?, phone = ?, password_hash = ?, role = ?, is_active = ?
                   WHERE id = ?''',
                (full_name, email, phone, generate_password_hash(password), role, is_active, user_id),
            )
        else:
            conn.execute(
                '''UPDATE users
                   SET full_name = ?, email = ?, phone = ?, role = ?, is_active = ?
                   WHERE id = ?''',
                (full_name, email, phone, role, is_active, user_id),
            )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return render_template('admin/user_edit.html', user=user, error='Этот email уже используется.')
    conn.close()

    if session.get('user_id') == user_id:
        session['user_name'] = full_name
        if role != 'admin' or not is_active:
            session.pop('logged_in', None)
    return redirect(url_for('admin_user_detail', user_id=user_id, saved=1))

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
def admin_user_delete(user_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))

    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    if session.get('user_id') == user_id:
        session.clear()
        return redirect(url_for('home'))
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/toggle-role', methods=['POST'])
def admin_user_toggle_role(user_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))

    conn = get_db_connection()
    conn.execute(
        '''UPDATE users
           SET role = CASE WHEN role = 'admin' THEN 'user' ELSE 'admin' END
           WHERE id = ?''',
        (user_id,),
    )
    conn.commit()
    user = conn.execute('SELECT role FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if session.get('user_id') == user_id and user and user['role'] != 'admin':
        session.pop('logged_in', None)
        return redirect(url_for('home'))
    return redirect(request.referrer or url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/toggle-block', methods=['POST'])
def admin_user_toggle_block(user_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))

    conn = get_db_connection()
    conn.execute(
        'UPDATE users SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?',
        (user_id,),
    )
    conn.commit()
    user = conn.execute('SELECT is_active FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if session.get('user_id') == user_id and user and not user['is_active']:
        session.clear()
        return redirect(url_for('home'))
    return redirect(request.referrer or url_for('admin_users'))

@app.route('/admin/rules')
def admin_rules():
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    sections = conn.execute(
        'SELECT * FROM rules_sections ORDER BY order_num, id'
    ).fetchall()
    conn.close()
    return render_template('admin/rules.html', sections=sections)

@app.route('/admin/rules/add', methods=['GET', 'POST'])
def admin_rule_add():
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    if request.method == 'GET':
        return render_template('admin/rule_form.html', section=None)

    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    if not title or not content:
        return render_template(
            'admin/rule_form.html',
            section=None,
            error='Заголовок и содержимое обязательны.',
        )

    conn = get_db_connection()
    next_order = conn.execute(
        'SELECT COALESCE(MAX(order_num), 0) + 1 FROM rules_sections'
    ).fetchone()[0]
    conn.execute(
        '''INSERT INTO rules_sections (title, content, order_num, is_active)
           VALUES (?, ?, ?, ?)''',
        (title, content, next_order, 1 if request.form.get('is_active') else 0),
    )
    conn.commit()
    conn.close()
    return redirect(url_for('admin_rules'))

@app.route('/admin/rules/<int:section_id>/edit', methods=['GET', 'POST'])
def admin_rule_edit(section_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    section = conn.execute(
        'SELECT * FROM rules_sections WHERE id = ?', (section_id,)
    ).fetchone()
    if not section:
        conn.close()
        return redirect(url_for('admin_rules'))
    if request.method == 'GET':
        conn.close()
        return render_template('admin/rule_form.html', section=section)

    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    if not title or not content:
        conn.close()
        return render_template(
            'admin/rule_form.html',
            section=section,
            error='Заголовок и содержимое обязательны.',
        )
    conn.execute(
        '''UPDATE rules_sections
           SET title = ?, content = ?, order_num = ?, is_active = ?
           WHERE id = ?''',
        (
            title,
            content,
            form_int_or_none(request.form.get('order_num')) or section['order_num'],
            1 if request.form.get('is_active') else 0,
            section_id,
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for('admin_rules'))

@app.route('/admin/rules/<int:section_id>/delete', methods=['POST'])
def admin_rule_delete(section_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    conn.execute('DELETE FROM rules_sections WHERE id = ?', (section_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_rules'))

@app.route('/admin/rules/<int:section_id>/move', methods=['POST'])
def admin_rule_move(section_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    direction = request.form.get('direction')
    if direction not in {'up', 'down'}:
        return redirect(url_for('admin_rules'))

    conn = get_db_connection()
    current = conn.execute(
        'SELECT id, order_num FROM rules_sections WHERE id = ?', (section_id,)
    ).fetchone()
    if current:
        operator = '<' if direction == 'up' else '>'
        ordering = 'DESC' if direction == 'up' else 'ASC'
        neighbour = conn.execute(
            f'''SELECT id, order_num FROM rules_sections
                WHERE order_num {operator} ?
                ORDER BY order_num {ordering}, id {ordering}
                LIMIT 1''',
            (current['order_num'],),
        ).fetchone()
        if neighbour:
            conn.execute(
                'UPDATE rules_sections SET order_num = ? WHERE id = ?',
                (neighbour['order_num'], current['id']),
            )
            conn.execute(
                'UPDATE rules_sections SET order_num = ? WHERE id = ?',
                (current['order_num'], neighbour['id']),
            )
            conn.commit()
    conn.close()
    return redirect(url_for('admin_rules'))

@app.route('/admin/regulations')
def admin_regulations():
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    regulations = conn.execute(
        'SELECT * FROM regulations ORDER BY order_num, regulation_date DESC, id'
    ).fetchall()
    conn.close()
    return render_template('admin/regulations.html', regulations=regulations)

@app.route('/admin/regulations/add', methods=['GET', 'POST'])
def admin_regulation_add():
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    if request.method == 'GET':
        return render_template('admin/regulation_form.html', regulation=None)

    title = request.form.get('title', '').strip()
    if not title:
        return render_template(
            'admin/regulation_form.html',
            regulation=None,
            error='Название обязательно.',
        )
    uploaded_file = save_uploaded_file(
        request.files.get('file'), DOCUMENT_EXTENSIONS
    )
    file_path = uploaded_file or request.form.get('file_url', '').strip()
    conn = get_db_connection()
    next_order = conn.execute(
        'SELECT COALESCE(MAX(order_num), 0) + 1 FROM regulations'
    ).fetchone()[0]
    conn.execute(
        '''INSERT INTO regulations
           (title, description, file_path, regulation_date, order_num, is_active)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (
            title,
            request.form.get('description', '').strip(),
            file_path,
            request.form.get('regulation_date') or today_iso(),
            next_order,
            1 if request.form.get('is_active') else 0,
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for('admin_regulations'))

@app.route('/admin/regulations/<int:regulation_id>/edit', methods=['GET', 'POST'])
def admin_regulation_edit(regulation_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    regulation = conn.execute(
        'SELECT * FROM regulations WHERE id = ?', (regulation_id,)
    ).fetchone()
    if not regulation:
        conn.close()
        return redirect(url_for('admin_regulations'))
    if request.method == 'GET':
        conn.close()
        return render_template(
            'admin/regulation_form.html', regulation=regulation
        )

    title = request.form.get('title', '').strip()
    if not title:
        conn.close()
        return render_template(
            'admin/regulation_form.html',
            regulation=regulation,
            error='Название обязательно.',
        )
    uploaded_file = save_uploaded_file(
        request.files.get('file'), DOCUMENT_EXTENSIONS
    )
    file_path = (
        uploaded_file
        or request.form.get('file_url', '').strip()
        or regulation['file_path']
    )
    conn.execute(
        '''UPDATE regulations
           SET title = ?, description = ?, file_path = ?, regulation_date = ?,
               order_num = ?, is_active = ?
           WHERE id = ?''',
        (
            title,
            request.form.get('description', '').strip(),
            file_path,
            request.form.get('regulation_date') or regulation['regulation_date'],
            form_int_or_none(request.form.get('order_num')) or regulation['order_num'],
            1 if request.form.get('is_active') else 0,
            regulation_id,
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for('admin_regulations'))

@app.route('/admin/regulations/<int:regulation_id>/delete', methods=['POST'])
def admin_regulation_delete(regulation_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    conn.execute('DELETE FROM regulations WHERE id = ?', (regulation_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_regulations'))

@app.route('/admin/transfers')
def admin_transfers():
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    transfers = conn.execute(
        'SELECT * FROM transfers ORDER BY transfer_date DESC, id DESC'
    ).fetchall()
    conn.close()
    return render_template('admin/transfers.html', transfers=transfers)

@app.route('/admin/transfers/add', methods=['GET', 'POST'])
def admin_transfer_add():
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    if request.method == 'GET':
        return render_template('admin/transfer_form.html', transfer=None)
    values = (
        request.form.get('player', '').strip(),
        request.form.get('from_team', '').strip(),
        request.form.get('to_team', '').strip(),
        request.form.get('transfer_date') or today_iso(),
        request.form.get('status', 'На рассмотрении'),
    )
    if not all(values[:3]):
        return render_template(
            'admin/transfer_form.html',
            transfer=None,
            error='Игрок и обе команды обязательны.',
        )
    if values[4] not in {'На рассмотрении', 'Подтверждён', 'Отклонён'}:
        values = (*values[:4], 'На рассмотрении')
    conn = get_db_connection()
    conn.execute(
        '''INSERT INTO transfers
           (player, from_team, to_team, transfer_date, status)
           VALUES (?, ?, ?, ?, ?)''',
        values,
    )
    conn.commit()
    conn.close()
    return redirect(url_for('admin_transfers'))

@app.route('/admin/transfers/<int:transfer_id>/edit', methods=['GET', 'POST'])
def admin_transfer_edit(transfer_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    transfer = conn.execute(
        'SELECT * FROM transfers WHERE id = ?', (transfer_id,)
    ).fetchone()
    if not transfer:
        conn.close()
        return redirect(url_for('admin_transfers'))
    if request.method == 'GET':
        conn.close()
        return render_template('admin/transfer_form.html', transfer=transfer)

    status = request.form.get('status', 'На рассмотрении')
    if status not in {'На рассмотрении', 'Подтверждён', 'Отклонён'}:
        status = 'На рассмотрении'
    conn.execute(
        '''UPDATE transfers
           SET player = ?, from_team = ?, to_team = ?, transfer_date = ?, status = ?
           WHERE id = ?''',
        (
            request.form.get('player', '').strip(),
            request.form.get('from_team', '').strip(),
            request.form.get('to_team', '').strip(),
            request.form.get('transfer_date') or transfer['transfer_date'],
            status,
            transfer_id,
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for('admin_transfers'))

@app.route('/admin/transfers/<int:transfer_id>/delete', methods=['POST'])
def admin_transfer_delete(transfer_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    conn.execute('DELETE FROM transfers WHERE id = ?', (transfer_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_transfers'))

@app.route('/admin/transfers/<int:transfer_id>/status', methods=['POST'])
def admin_transfer_status(transfer_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    status = request.form.get('status', 'На рассмотрении')
    if status not in {'На рассмотрении', 'Подтверждён', 'Отклонён'}:
        status = 'На рассмотрении'
    conn = get_db_connection()
    conn.execute(
        'UPDATE transfers SET status = ? WHERE id = ?', (status, transfer_id)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('admin_transfers'))

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
    if request.form.get('archive_form') == '1':
        team1_name = request.form.get('team1_name', '').strip()
        team2_name = request.form.get('team2_name', '').strip()
        match_date = request.form.get('match_date', '').strip()
        if not all([team1_name, team2_name, match_date]):
            return redirect(url_for('admin_panel') + '#archive')

        winner_team = request.form.get('winner_team', '').strip()
        if winner_team not in {'', 'team1', 'team2'}:
            winner_team = ''

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO match_archive
            (team1_name, team2_name, team1_score, team2_score, match_date, match_time,
             location, league, season, tournament_name, description, video_url,
             winner_team, stage, is_playoff)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            team1_name,
            team2_name,
            form_int_or_none(request.form.get('team1_score')) or 0,
            form_int_or_none(request.form.get('team2_score')) or 0,
            match_date,
            request.form.get('match_time', '').strip(),
            request.form.get('location', '').strip(),
            request.form.get('league', '').strip(),
            request.form.get('season', '').strip(),
            request.form.get('tournament_name', '').strip(),
            request.form.get('description', '').strip(),
            request.form.get('video_url', '').strip(),
            winner_team,
            request.form.get('stage', '').strip(),
            1 if request.form.get('is_playoff') else 0,
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('admin_panel') + '#archive')

    team1 = request.form.get('team1', '').strip()
    team2 = request.form.get('team2', '').strip()
    league = request.form.get('league', '').strip()
    date = request.form.get('date', '').strip()
    time = request.form.get('time', '').strip()
    if not all([team1, team2, league, date, time]):
        return redirect(url_for('admin_panel'))

    location = request.form.get('location', '').strip()
    tournament_name = request.form.get('tournament_name', '').strip()
    round_name = request.form.get('round_name', '').strip()
    status = request.form.get('status', 'scheduled').strip()
    if status not in {'scheduled', 'live', 'finished', 'postponed'}:
        status = 'scheduled'
    search_tags = f"{team1} {team2} {league} {location} {tournament_name}".lower()
    is_next = 1 if request.form.get('is_next') else 0
    conn = get_db_connection()
    if is_next:
        conn.execute('UPDATE matches SET is_next = 0')
    conn.execute('''INSERT INTO matches
                    (date, time, league, team1, team2, search_tags, is_next, status, location, tournament_name, round_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (date, time, league, team1, team2, search_tags, is_next, status, location, tournament_name, round_name))
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
        return admin_redirect('news', 'Заполните дату и заголовок новости.', 'error')
    if not is_valid_iso_date(date):
        return admin_redirect('news', 'Введите дату новости в формате дд.мм.гггг.', 'error')

    search_tags = title.lower()
    is_published = 1 if request.form.get('is_published') else 0
    meta_title = request.form.get('meta_title', '').strip()
    meta_description = request.form.get('meta_description', '').strip()
    conn = get_db_connection()
    conn.execute('''INSERT INTO news
                    (date, title, img_url, search_tags, body, is_published, meta_title, meta_description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                 (date, title, img_url, search_tags, body, is_published, meta_title, meta_description))
    metadata_id = news_id if 'news_id' in locals() else conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    team_id = form_int_or_none(request.form.get('news_team_id'))
    match_id = form_int_or_none(request.form.get('news_archive_match_id'))
    if team_id and not conn.execute('SELECT 1 FROM teams WHERE id=? AND is_active=1', (team_id,)).fetchone():
        team_id = None
    if match_id and not conn.execute('SELECT 1 FROM match_archive WHERE id=?', (match_id,)).fetchone():
        match_id = None
    conn.execute('UPDATE news SET team_id=?,archive_match_id=? WHERE id=?', (team_id,match_id,metadata_id))
    conn.commit()
    conn.close()
    return admin_redirect('news', 'Новость опубликована.' if is_published else 'Новость сохранена как черновик.')

@app.route('/admin/update-news/<int:news_id>', methods=['POST'])
def update_news(news_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    title = request.form.get('title', '').strip()
    date_value = request.form.get('date', '').strip()
    if not title or not date_value:
        return admin_redirect('news', 'Заполните дату и заголовок новости.', 'error')
    if not is_valid_iso_date(date_value):
        return admin_redirect('news', 'Введите дату новости в формате дд.мм.гггг.', 'error')

    img_url = save_uploaded_file(request.files.get('image'), IMAGE_EXTENSIONS) or request.form.get('img_url', '').strip()
    body = request.form.get('body', '').strip()
    is_published = 1 if request.form.get('is_published') else 0
    meta_title = request.form.get('meta_title', '').strip()
    meta_description = request.form.get('meta_description', '').strip()
    conn = get_db_connection()
    current = conn.execute('SELECT img_url FROM news WHERE id = ?', (news_id,)).fetchone()
    final_img_url = img_url or (current['img_url'] if current else '')
    conn.execute('''UPDATE news
                    SET date = ?, title = ?, img_url = ?, search_tags = ?, body = ?,
                        is_published = ?, meta_title = ?, meta_description = ?
                    WHERE id = ?''',
                 (date_value, title, final_img_url, title.lower(), body,
                  is_published, meta_title, meta_description, news_id))
    metadata_id = news_id if 'news_id' in locals() else conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    team_id = form_int_or_none(request.form.get('news_team_id'))
    match_id = form_int_or_none(request.form.get('news_archive_match_id'))
    if team_id and not conn.execute('SELECT 1 FROM teams WHERE id=? AND is_active=1', (team_id,)).fetchone():
        team_id = None
    if match_id and not conn.execute('SELECT 1 FROM match_archive WHERE id=?', (match_id,)).fetchone():
        match_id = None
    conn.execute('UPDATE news SET team_id=?,archive_match_id=? WHERE id=?', (team_id,match_id,metadata_id))
    conn.commit()
    conn.close()
    return admin_redirect('news', 'Новость обновлена.' if is_published else 'Черновик новости сохранён.')

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

    location = request.form.get('location', '').strip()
    tournament_name = request.form.get('tournament_name', '').strip()
    round_name = request.form.get('round_name', '').strip()
    status = request.form.get('status', 'scheduled').strip()
    if status not in {'scheduled', 'live', 'finished', 'postponed'}:
        status = 'scheduled'
    is_next = 1 if request.form.get('is_next') else 0
    conn = get_db_connection()
    if is_next:
        conn.execute('UPDATE matches SET is_next = 0')
    conn.execute('''UPDATE matches
                    SET date = ?, time = ?, league = ?, team1 = ?, team2 = ?, search_tags = ?, is_next = ?,
                        status = ?, location = ?, tournament_name = ?, round_name = ?
                    WHERE id = ?''',
                 (
                     date_value,
                     time_value,
                     league,
                     team1,
                     team2,
                     f"{team1} {team2} {league} {location} {tournament_name}".lower(),
                     is_next,
                     status,
                     location,
                     tournament_name,
                     round_name,
                     match_id,
                 ))
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
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    file = request.files.get('file')
    saved = save_document_pdf(file)
    if not saved:
        return admin_redirect('all-documents', 'Загрузите PDF файл.', 'error')
    category = request.form.get('category') if request.form.get('category') in DOCUMENT_CATEGORIES else 'regulations'
    official_date = request.form.get('official_date') or today_iso()
    conn = get_db_connection()
    conn.execute(
        '''INSERT INTO documents
           (title, category, description, file_url, file_name, file_size, official_date,
            reg_number, is_active, file_path, file_type, upload_date, is_public)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 'pdf', ?, 1)''',
        (
            request.form.get('title', '').strip(),
            category,
            request.form.get('description', '').strip(),
            saved['file_url'],
            saved['file_name'],
            saved['file_size'],
            official_date,
            request.form.get('reg_number', '').strip(),
            saved['file_path'],
            official_date,
        ),
    )
    conn.commit()
    conn.close()
    return admin_redirect('all-documents', 'Документ загружен.')

@app.route('/admin/edit-document/<int:document_id>', methods=['GET', 'POST'])
def edit_document(document_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    document = conn.execute('SELECT * FROM documents WHERE id = ?', (document_id,)).fetchone()
    if not document:
        conn.close()
        return admin_redirect('all-documents', 'Документ не найден.', 'error')

    if request.method == 'POST':
        category = request.form.get('category') if request.form.get('category') in DOCUMENT_CATEGORIES else 'regulations'
        title = request.form.get('title', '').strip()
        if not title:
            conn.close()
            return render_template(
                'admin/document_form.html',
                document=document,
                categories=DOCUMENT_CATEGORIES,
                error='Укажите название документа.',
            )
        file = request.files.get('file')
        saved = save_document_pdf(file) if file and file.filename else None
        if saved:
            old_path = document_disk_path(document['file_url'] or document['file_path'])
            if old_path and os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    logger.warning("Could not delete old document file: %s", old_path)
            file_url = saved['file_url']
            file_name = saved['file_name']
            file_size = saved['file_size']
            file_path = saved['file_path']
        else:
            file_url = document['file_url'] or ''
            file_name = document['file_name'] or ''
            file_size = document['file_size'] or document_file_size(file_url or document['file_path'])
            file_path = document['file_path'] or ''

        official_date = request.form.get('official_date') or document['official_date'] or today_iso()
        conn.execute(
            '''UPDATE documents
               SET title = ?, category = ?, description = ?, official_date = ?, reg_number = ?,
                   file_url = ?, file_name = ?, file_size = ?, file_path = ?,
                   upload_date = ?, is_active = 1, is_public = 1, file_type = 'pdf'
               WHERE id = ?''',
            (
                title,
                category,
                request.form.get('description', '').strip(),
                official_date,
                request.form.get('reg_number', '').strip(),
                file_url,
                file_name,
                file_size,
                file_path,
                official_date,
                document_id,
            ),
        )
        conn.commit()
        conn.close()
        return admin_redirect('all-documents', 'Документ обновлён.')

    conn.close()
    return render_template('admin/document_form.html', document=document, categories=DOCUMENT_CATEGORIES, error='')

@app.route('/admin/delete-document/<int:document_id>')
def delete_document(document_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    document = conn.execute('SELECT * FROM documents WHERE id = ?', (document_id,)).fetchone()
    if not document:
        conn.close()
        return admin_redirect('all-documents', 'Документ не найден.', 'error')
    file_path = document_disk_path(document['file_url'] or document['file_path'])
    conn.execute('DELETE FROM documents WHERE id = ?', (document_id,))
    conn.commit()
    conn.close()
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            logger.warning("Could not delete document file: %s", file_path)
    return admin_redirect('all-documents', 'Документ удалён.')

@app.route('/admin/add-player', methods=['POST'])
def add_player():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    photo_url = save_uploaded_file(request.files.get('photo'), IMAGE_EXTENSIONS) or request.form.get('photo_url') or 'https://placehold.co/300x400'
    team_name = request.form.get('team', '').strip()
    conn = get_db_connection()
    team = conn.execute('SELECT id FROM teams WHERE name = ?', (team_name,)).fetchone()
    conn.execute('''INSERT INTO players
                    (name, photo_url, team, team_id, position, stats_points, stats_matches,
                     birth_year, region, jersey_number, bio, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (request.form.get('name'), photo_url,
                  team_name, team['id'] if team else None, request.form.get('position'),
                  request.form.get('stats_points', 0), request.form.get('stats_matches', 0),
                  request.form.get('birth_year'), request.form.get('region'),
                  form_int_or_none(request.form.get('jersey_number')),
                  request.form.get('bio', '').strip(), 1))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/add-horse', methods=['POST'])
def add_horse():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    name = request.form.get('name', '').strip()
    if not name:
        return redirect(url_for('admin_panel') + '#horses')

    photos = []
    for photo_file in horse_photo_files():
        uploaded_url = save_uploaded_file(photo_file, IMAGE_EXTENSIONS)
        if uploaded_url:
            photos.append(uploaded_url)
    photos.extend(form_photo_urls(request.form.get('horse_photo_urls')))
    photos = list(dict.fromkeys(photos))
    photo_url = photos[0] if photos else HORSE_PHOTO_PLACEHOLDER
    if not photos:
        photos = [photo_url]
    conn = get_db_connection()
    conn.execute('''INSERT INTO horses (
                        name, photo_url, photo_urls, breed, age, color, speed, stamina,
                        points, price, description, phone, is_for_sale, is_active
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)''',
                 (name, photo_url, json.dumps(photos),
                  request.form.get('breed', '').strip(),
                  form_int_or_none(request.form.get('age')),
                  request.form.get('color', '').strip(),
                  form_int_or_none(request.form.get('speed')) or 0,
                  form_int_or_none(request.form.get('stamina')) or 0,
                  form_int_or_none(request.form.get('points')) or 0,
                  form_int_or_none(request.form.get('price')),
                  request.form.get('horse_description', '').strip(),
                  request.form.get('horse_phone', '').strip(),
                  1 if request.form.get('is_for_sale') else 0))
    from utils.portal_features import HORSE_FIELDS
    metadata = [form_int_or_none(request.form.get('horse_player_id')) if key == 'player_id'
                else request.form.get('horse_' + key, '').strip() for key in HORSE_FIELDS]
    metadata_id = horse_id if 'horse_id' in locals() else conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    if metadata[3] and not conn.execute('SELECT 1 FROM players WHERE id=? AND is_active=1', (metadata[3],)).fetchone():
        metadata[3] = None
    conn.execute('UPDATE horses SET owner_name=?,region=?,achievements=?,player_id=?,rating_note=? WHERE id=?', metadata + [metadata_id])
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel') + '#horses')

@app.route('/admin/update-horse/<int:horse_id>', methods=['POST'])
def update_horse(horse_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    name = request.form.get('name', '').strip()
    if not name:
        return redirect(url_for('admin_panel') + '#horses')

    conn = get_db_connection()
    current = conn.execute(
        'SELECT photo_url, photo_urls FROM horses WHERE id = ?', (horse_id,)
    ).fetchone()
    photos = form_photo_urls(request.form.get('horse_photo_urls'))
    for photo_file in horse_photo_files():
        uploaded_url = save_uploaded_file(photo_file, IMAGE_EXTENSIONS)
        if uploaded_url:
            photos.append(uploaded_url)
    if not photos and current:
        photos = parse_photo_urls(current['photo_urls'], current['photo_url'])
    photos = list(dict.fromkeys(photos))
    photo_url = photos[0] if photos else HORSE_PHOTO_PLACEHOLDER
    conn.execute('''UPDATE horses SET name = ?, photo_url = ?, photo_urls = ?, breed = ?, age = ?, color = ?, speed = ?,
                    stamina = ?, points = ?, price = ?, description = ?, phone = ?, is_for_sale = ?, is_active = ?
                    WHERE id = ?''',
                 (name, photo_url, json.dumps(photos),
                  request.form.get('breed', '').strip(),
                  form_int_or_none(request.form.get('age')),
                  request.form.get('color', '').strip(),
                  form_int_or_none(request.form.get('speed')) or 0,
                  form_int_or_none(request.form.get('stamina')) or 0,
                  form_int_or_none(request.form.get('points')) or 0,
                  form_int_or_none(request.form.get('price')),
                  request.form.get('horse_description', '').strip(),
                  request.form.get('horse_phone', '').strip(),
                  1 if request.form.get('is_for_sale') else 0,
                  1 if request.form.get('is_active') else 0,
                  horse_id))
    from utils.portal_features import HORSE_FIELDS
    metadata = [form_int_or_none(request.form.get('horse_player_id')) if key == 'player_id'
                else request.form.get('horse_' + key, '').strip() for key in HORSE_FIELDS]
    metadata_id = horse_id if 'horse_id' in locals() else conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    if metadata[3] and not conn.execute('SELECT 1 FROM players WHERE id=? AND is_active=1', (metadata[3],)).fetchone():
        metadata[3] = None
    conn.execute('UPDATE horses SET owner_name=?,region=?,achievements=?,player_id=?,rating_note=? WHERE id=?', metadata + [metadata_id])
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel') + '#horses')

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
        return admin_redirect('media', 'Укажите название и видеофайл или ссылку.', 'error')

    category = request.form.get('category', '').strip()
    if category not in ('Видео', 'Обзор', 'Матч', 'Интервью', 'Тренировка'):
        category = 'Видео'

    conn = get_db_connection()
    conn.execute('''INSERT INTO videos
                    (title, video_url, thumbnail, match_id, archive_match_id, team_id,
                     tournament_name, upload_date, views, category, description, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (title, video_url, thumbnail,
                  form_int_or_none(request.form.get('match_id')),
                  form_int_or_none(request.form.get('archive_match_id')),
                  form_int_or_none(request.form.get('team_id')),
                  request.form.get('tournament_name', '').strip(),
                  request.form.get('upload_date') or today_iso(), 0,
                  category,
                  request.form.get('description', '').strip(),
                  1 if request.form.get('is_active', '1') else 0))
    conn.commit()
    conn.close()
    return admin_redirect('media', 'Видео добавлено.')

@app.route('/admin/update-video/<int:video_id>', methods=['POST'])
def update_video(video_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    title = request.form.get('title', '').strip()
    if not title:
        return admin_redirect('media', 'Название видео обязательно.', 'error')
    conn = get_db_connection()
    current = conn.execute('SELECT video_url, thumbnail FROM videos WHERE id = ?', (video_id,)).fetchone()
    if not current:
        conn.close()
        return admin_redirect('media', 'Видео не найдено.', 'error')
    video_url = (
        save_uploaded_file(request.files.get('video_file'), VIDEO_EXTENSIONS)
        or request.form.get('video_url', '').strip()
        or current['video_url']
    )
    thumbnail = (
        save_uploaded_file(request.files.get('thumbnail_file'), IMAGE_EXTENSIONS)
        or request.form.get('thumbnail', '').strip()
        or current['thumbnail']
    )
    category = request.form.get('category', '').strip()
    if category not in ('Видео', 'Обзор', 'Матч', 'Интервью', 'Тренировка'):
        category = 'Видео'

    conn.execute('''UPDATE videos
                    SET title = ?, video_url = ?, thumbnail = ?, match_id = ?, archive_match_id = ?,
                        team_id = ?, tournament_name = ?, upload_date = ?, category = ?,
                        description = ?, is_active = ?
                    WHERE id = ?''',
                 (
                     title,
                     video_url,
                     thumbnail,
                     form_int_or_none(request.form.get('match_id')),
                     form_int_or_none(request.form.get('archive_match_id')),
                     form_int_or_none(request.form.get('team_id')),
                     request.form.get('tournament_name', '').strip(),
                     request.form.get('upload_date') or today_iso(),
                     category,
                     request.form.get('description', '').strip(),
                     1 if request.form.get('is_active') else 0,
                     video_id,
                 ))
    conn.commit()
    conn.close()
    return admin_redirect('media', 'Видео обновлено.')

@app.route('/admin/create-album', methods=['POST'])
def create_album():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    cover_url = save_uploaded_file(request.files.get('cover_file'), IMAGE_EXTENSIONS) or request.form.get('cover_url', '').strip()
    title = request.form.get('title', '').strip()
    if not title:
        return admin_redirect('media', 'Название альбома обязательно.', 'error')

    conn = get_db_connection()
    conn.execute('''INSERT INTO photo_albums
                    (title, match_id, archive_match_id, team_id, tournament_name, cover_url,
                     upload_date, photo_count, description, is_active, meta_title, meta_description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (title, form_int_or_none(request.form.get('match_id')),
                  form_int_or_none(request.form.get('archive_match_id')),
                  form_int_or_none(request.form.get('team_id')),
                  request.form.get('tournament_name', '').strip(),
                  cover_url, request.form.get('upload_date') or today_iso(), 0,
                  request.form.get('description', '').strip(),
                  1 if request.form.get('is_active', '1') else 0,
                  request.form.get('meta_title', '').strip(),
                  request.form.get('meta_description', '').strip()))
    conn.commit()
    conn.close()
    return admin_redirect('media', 'Фотоальбом создан.')

@app.route('/admin/update-album/<int:album_id>', methods=['POST'])
def update_album(album_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    title = request.form.get('title', '').strip()
    if not title:
        return admin_redirect('media', 'Название альбома обязательно.', 'error')
    conn = get_db_connection()
    current = conn.execute('SELECT cover_url FROM photo_albums WHERE id = ?', (album_id,)).fetchone()
    if not current:
        conn.close()
        return admin_redirect('media', 'Альбом не найден.', 'error')
    cover_url = (
        save_uploaded_file(request.files.get('cover_file'), IMAGE_EXTENSIONS)
        or request.form.get('cover_url', '').strip()
        or current['cover_url']
    )
    conn.execute('''UPDATE photo_albums
                    SET title = ?, match_id = ?, archive_match_id = ?, team_id = ?, tournament_name = ?,
                        cover_url = ?, upload_date = ?, description = ?, is_active = ?,
                        meta_title = ?, meta_description = ?
                    WHERE id = ?''',
                 (
                     title,
                     form_int_or_none(request.form.get('match_id')),
                     form_int_or_none(request.form.get('archive_match_id')),
                     form_int_or_none(request.form.get('team_id')),
                     request.form.get('tournament_name', '').strip(),
                     cover_url,
                     request.form.get('upload_date') or today_iso(),
                     request.form.get('description', '').strip(),
                     1 if request.form.get('is_active') else 0,
                     request.form.get('meta_title', '').strip(),
                     request.form.get('meta_description', '').strip(),
                     album_id,
                 ))
    conn.commit()
    conn.close()
    return admin_redirect('media', 'Фотоальбом обновлён.')

@app.route('/admin/add-photo/<int:album_id>', methods=['POST'])  # ✅ ИСПРАВЛЕНО
def add_photo(album_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    if 'photo' not in request.files:
        return admin_redirect('media', 'Выберите фото для загрузки.', 'error')
    
    file = request.files['photo']
    if file.filename == '' or not allowed_file(file.filename, IMAGE_EXTENSIONS):
        return admin_redirect('media', 'Фото должно быть в формате JPG, PNG или WEBP.', 'error')

    filepath = save_uploaded_file(file, IMAGE_EXTENSIONS)
    
    conn = get_db_connection()
    next_order = conn.execute('SELECT COALESCE(MAX(order_num), 0) + 1 FROM photos WHERE album_id = ?', (album_id,)).fetchone()[0]
    conn.execute('INSERT INTO photos (album_id, photo_url, caption, order_num) VALUES (?, ?, ?, ?)',
                 (album_id, filepath, request.form.get('caption', ''), next_order))
    conn.execute('UPDATE photo_albums SET photo_count = photo_count + 1 WHERE id = ?', (album_id,))
    conn.commit()
    conn.close()
    return admin_redirect('media', 'Фото загружено.')

@app.route('/admin/update-photo/<int:photo_id>', methods=['POST'])
def update_photo(photo_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    conn.execute(
        'UPDATE photos SET caption = ?, order_num = ? WHERE id = ?',
        (
            request.form.get('caption', '').strip(),
            form_int_or_none(request.form.get('order_num')) or 0,
            photo_id,
        )
    )
    conn.commit()
    conn.close()
    return admin_redirect('media', 'Фото обновлено.')

@app.route('/admin/delete-photo/<int:photo_id>', methods=['POST'])
def delete_photo(photo_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    photo = conn.execute('SELECT album_id FROM photos WHERE id = ?', (photo_id,)).fetchone()
    conn.execute('DELETE FROM photos WHERE id = ?', (photo_id,))
    if photo:
        conn.execute(
            '''UPDATE photo_albums
               SET photo_count = (SELECT COUNT(*) FROM photos WHERE album_id = ?)
               WHERE id = ?''',
            (photo['album_id'], photo['album_id'])
        )
    conn.commit()
    conn.close()
    return admin_redirect('media', 'Фото удалено.')

@app.route('/admin/delete/<table_name>/<int:item_id>', methods=['POST'])  # ✅ ИСПРАВЛЕНО
def delete_item(table_name, item_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    allowed_tables = ['matches', 'match_archive', 'news', 'leagues', 'documents', 'players', 'horses', 'referees', 'hippodromes', 'videos', 'photo_albums', 'photos', 'contact_cards']
    if table_name not in allowed_tables:
        return admin_redirect('overview', 'Нельзя удалить эту запись.', 'error')
    
    conn = get_db_connection()
    # Using validated table_name from whitelist to prevent SQL injection
    conn.execute(f'DELETE FROM "{table_name}" WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    section = {
        'news': 'news',
        'videos': 'media',
        'photo_albums': 'media',
        'photos': 'media',
        'documents': 'all-documents',
        'matches': 'matches',
        'match_archive': 'archive',
        'horses': 'horses',
        'players': 'people',
        'referees': 'people',
        'hippodromes': 'venues',
        'contact_cards': 'contact-cards',
    }.get(table_name, 'overview')
    return admin_redirect(section, 'Запись удалена.')

@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    return redirect(url_for('admin_panel'))

@app.route('/logout')
def user_logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('logged_in', None)
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
    return admin_redirect('news', 'Фото новости удалено.')

app.register_blueprint(pages_bp)

from utils.portal_features import setup_portal
setup_portal(app, get_db_connection, ensure_column, save_uploaded_file, send_email_message, public_url_for)

if __name__ == '__main__':  # ✅ ИСПРАВЛЕНО
    init_db()
    port = int(os.getenv('PORT', 5002))
    app.run(debug=os.getenv('DEBUG', 'false').lower() in {'1', 'true', 'yes'}, host='0.0.0.0', port=port)
    
