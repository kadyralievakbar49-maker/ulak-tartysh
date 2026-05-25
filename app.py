from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)  # ✅ ИСПРАВЛЕНО
app.secret_key = 'super_secret_key_for_sessions'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ADMIN_PASSWORD = 'admin'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
    return render_template('documents.html', **site_content())

@app.route('/hippodromes')
def hippodromes_page():
    return render_template('hippodromes.html', **site_content())

@app.route('/referees')
def referees_page():
    return render_template('referees.html', **site_content())

@app.route('/teams')
def teams_page():
    return render_template('teams.html', **site_content())

@app.route('/contacts')
def contacts_page():
    return render_template('contacts.html', **site_content())

@app.route('/api/submit', methods=['POST'])
def handle_submissions():
    data = request.get_json() or request.form.to_dict()
    print(f"[БЭКЕНД] Получены данные: {data}")
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
        'referees': conn.execute('SELECT * FROM referees').fetchall(),
        'hippodromes': conn.execute('SELECT * FROM hippodromes').fetchall(),
        'videos': conn.execute('SELECT * FROM videos').fetchall(),
        'albums': conn.execute('SELECT a.*, COUNT(p.id) as photo_count FROM photo_albums a LEFT JOIN photos p ON a.id = p.album_id GROUP BY a.id').fetchall(),
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
    img_url = request.form.get('img_url', '').strip()
    if not title or not date:
        return redirect(url_for('admin_panel'))

    search_tags = title.lower()
    conn = get_db_connection()
    conn.execute('INSERT INTO news (date, title, img_url, search_tags) VALUES (?, ?, ?, ?)',
                 (date, title, img_url, search_tags))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

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
    if file.filename == '' or not allowed_file(file.filename):
        return redirect(url_for('admin_panel'))
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    conn = get_db_connection()
    conn.execute('''INSERT INTO documents (title, description, file_path, file_type, category, upload_date, is_public) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (request.form.get('title'), request.form.get('description'),
                  filepath, filename.rsplit('.', 1)[1].lower(),
                  request.form.get('category'), request.form.get('upload_date', '2026-05-22'), 1))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/add-player', methods=['POST'])
def add_player():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    conn.execute('''INSERT INTO players (name, photo_url, team, position, stats_points, stats_matches, birth_year, region, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (request.form.get('name'), request.form.get('photo_url') or 'https://placehold.co/300x400',
                  request.form.get('team'), request.form.get('position'),
                  request.form.get('stats_points', 0), request.form.get('stats_matches', 0),
                  request.form.get('birth_year'), request.form.get('region'), 1))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/add-video', methods=['POST'])
def add_video():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    conn.execute('''INSERT INTO videos (title, video_url, thumbnail, match_id, upload_date, views, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (request.form.get('title'), request.form.get('video_url'),
                  request.form.get('thumbnail'), request.form.get('match_id'),
                  request.form.get('upload_date', '2026-05-22'), 0,
                  request.form.get('category')))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/create-album', methods=['POST'])
def create_album():
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    conn = get_db_connection()
    conn.execute('''INSERT INTO photo_albums (title, match_id, cover_url, upload_date, photo_count)
                    VALUES (?, ?, ?, ?, ?)''',
                 (request.form.get('title'), request.form.get('match_id'),
                  request.form.get('cover_url'), request.form.get('upload_date', '2026-05-22'), 0))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/add-photo/<int:album_id>', methods=['POST'])  # ✅ ИСПРАВЛЕНО
def add_photo(album_id):
    if not session.get('logged_in'): return redirect(url_for('admin_panel'))
    if 'photo' not in request.files:
        return redirect(url_for('admin_panel'))
    
    file = request.files['photo']
    if file.filename == '' or not allowed_file(file.filename):
        return redirect(url_for('admin_panel'))
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
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
    allowed_tables = ['matches', 'news', 'leagues', 'documents', 'players', 'referees', 'hippodromes', 'videos', 'photo_albums', 'photos']
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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf', 'docx', 'jpg', 'jpeg', 'png'}

if __name__ == '__main__':  # ✅ ИСПРАВЛЕНО
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
