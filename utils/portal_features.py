"""Member features and additive schema upgrades for the federation portal."""
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import json
import re
import secrets
from pathlib import Path
from urllib.parse import unquote, urlparse
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for, Response
from werkzeug.security import generate_password_hash

ENTITIES = {'horse': ('horses', 'horse_detail_page', 'horse_id'),
            'player': ('players', 'player_detail_page', 'player_id'),
            'team': ('teams', 'team_detail_page', 'team_id')}
HORSE_FIELDS = {'owner_name': "TEXT DEFAULT ''", 'region': "TEXT DEFAULT ''",
                'achievements': "TEXT DEFAULT ''", 'player_id': 'INTEGER',
                'rating_note': "TEXT DEFAULT ''"}


def ensure_portal_schema(conn, ensure_column):
    if not conn.in_transaction:
        conn.execute('BEGIN IMMEDIATE')
    ensure_column(conn, 'users', 'auth_version', 'INTEGER NOT NULL DEFAULT 0')
    for column, definition in HORSE_FIELDS.items():
        ensure_column(conn, 'horses', column, definition)
    for column in ['team_id', 'archive_match_id']:
        ensure_column(conn, 'news', column, 'INTEGER')
    conn.executescript('''
      CREATE TABLE IF NOT EXISTS user_favorites (
        user_id INTEGER NOT NULL, entity_type TEXT NOT NULL CHECK(entity_type IN ('horse','player','team')),
        entity_id INTEGER NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY (user_id, entity_type, entity_id));
      CREATE TABLE IF NOT EXISTS team_subscriptions (
        user_id INTEGER NOT NULL, team_id INTEGER NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(user_id, team_id));
      CREATE TABLE IF NOT EXISTS horse_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL,
        breed TEXT DEFAULT '', color TEXT DEFAULT '', age INTEGER, price INTEGER,
        owner_name TEXT NOT NULL, region TEXT NOT NULL, phone TEXT NOT NULL,
        description TEXT NOT NULL, photo_url TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
        review_note TEXT DEFAULT '', horse_id INTEGER, created_at TEXT NOT NULL, reviewed_at TEXT);
      CREATE TABLE IF NOT EXISTS password_resets (
        token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_at TEXT NOT NULL, used_at TEXT);
      CREATE INDEX IF NOT EXISTS idx_submissions_status ON horse_submissions(status, created_at);
    ''')


def setup_portal(app, get_db, ensure_column, save_file, send_email, public_url):
    bp = Blueprint('portal', __name__)
    # Lazy, once-per-process migration: importing the app must not seed or rewrite data.
    schema_ready = False

    @app.before_request
    def portal_schema():
        nonlocal schema_ready
        if schema_ready or request.path.startswith('/static/') or request.path == '/sw.js':
            return
        conn = get_db()
        try:
            ensure_portal_schema(conn, ensure_column)
            conn.commit()
            schema_ready = True
        finally:
            conn.close()

    @app.before_request
    def check_member_session():
        if not session.get('user_id') or request.path.startswith('/static/'):
            return
        conn = get_db()
        try:
            user = conn.execute('SELECT is_active,auth_version FROM users WHERE id=?', (session['user_id'],)).fetchone()
        finally:
            conn.close()
        if not user or not user['is_active'] or session.get('auth_version', 0) != user['auth_version']:
            for key in ['user_id', 'user_name', 'logged_in', 'auth_version']:
                session.pop(key, None)

    @app.after_request
    def private_responses(response):
        private_path = request.path.startswith(('/profile', '/admin', '/api/', '/forgot-password', '/reset-password', '/confirm-email'))
        if private_path or (session.get('user_id') and not request.path.startswith('/static/')):
            response.headers['Cache-Control'] = 'private, no-store'
        return response

    def member_required(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            conn = get_db()
            try:
                user = conn.execute('SELECT * FROM users WHERE id=? AND is_active=1 AND is_verified=1',
                                    (session.get('user_id'),)).fetchone()
            finally:
                conn.close()
            if not user:
                if request.path.startswith('/api/'):
                    return jsonify(status='error', message='Войдите в подтверждённый аккаунт.', message_key='memberRequired'), 401
                flash('Войдите в подтверждённый аккаунт.', 'error')
                return redirect(url_for('home'))
            return fn(*args, **kwargs)
        return wrapped

    def admin_required(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not session.get('logged_in'):
                return redirect(url_for('admin_panel'))
            return fn(*args, **kwargs)
        return wrapped

    def valid_entity(conn, kind, entity_id):
        if kind not in ENTITIES:
            abort(404)
        table = ENTITIES[kind][0]
        row = conn.execute(f'SELECT * FROM {table} WHERE id=? AND is_active=1', (entity_id,)).fetchone()
        if not row:
            abort(404)
        return row

    def file_available(value):
        if not value:
            return False
        parsed = urlparse(value)
        if parsed.scheme or parsed.netloc:
            return parsed.scheme in ('http', 'https') or not parsed.scheme
        path = unquote(parsed.path)
        if path.startswith('/documents/'):
            path = '/static/documents/' + path[len('/documents/'):]
        if path.startswith(('/static/', 'static/')):
            candidate = (Path(app.root_path) / path.lstrip('/')).resolve()
            return candidate.is_relative_to(Path(app.static_folder).resolve()) and candidate.is_file()
        return True

    @app.context_processor
    def portal_context():
        conn = get_db()
        try:
            favorites = set()
            subscriptions = set()
            if session.get('user_id'):
                favorites = {(r['entity_type'], r['entity_id']) for r in conn.execute(
                    'SELECT entity_type, entity_id FROM user_favorites WHERE user_id=?', (session['user_id'],))}
                subscriptions = {r[0] for r in conn.execute('SELECT team_id FROM team_subscriptions WHERE user_id=?', (session['user_id'],))}
            def related_horses(player_id=None, team_id=None):
                return conn.execute('''SELECT h.* FROM horses h JOIN players p ON p.id=h.player_id
                    WHERE h.is_active=1 AND p.is_active=1 AND (p.id=? OR p.team_id=?) ORDER BY h.points DESC,h.name''',
                    (player_id, team_id)).fetchall()
            # Resolve all related records before closing the connection.
            relations = {}
            args = request.view_args or {}
            if request.endpoint == 'horse_detail_page':
                relations['horse_player'] = conn.execute('''SELECT p.*,t.name AS linked_team_name,t.id AS linked_team_id
                    FROM horses h JOIN players p ON p.id=h.player_id AND p.is_active=1
                    LEFT JOIN teams t ON t.id=p.team_id AND t.is_active=1 WHERE h.id=?''', (args.get('horse_id'),)).fetchone()
            elif request.endpoint == 'player_detail_page':
                relations['linked_horses'] = related_horses(player_id=args.get('player_id'))
            elif request.endpoint == 'team_detail_page':
                relations['linked_horses'] = related_horses(team_id=args.get('team_id'))
            if request.endpoint == 'match_detail':
                match = conn.execute('SELECT * FROM match_archive WHERE id=?', (args.get('match_id'),)).fetchone()
                if match:
                    relations['match_teams'] = {r['name']: r['id'] for r in conn.execute(
                        'SELECT id,name FROM teams WHERE is_active=1 AND name IN (?,?)', (match['team1_name'],match['team2_name']))}
                    relations['related_news'] = conn.execute('SELECT * FROM news WHERE archive_match_id=? AND is_published=1 ORDER BY date DESC', (match['id'],)).fetchall()
            if request.endpoint == 'news_detail_page':
                item = conn.execute('SELECT team_id,archive_match_id FROM news WHERE id=?', (args.get('news_id'),)).fetchone()
                if item:
                    relations['news_team'] = conn.execute('SELECT * FROM teams WHERE id=? AND is_active=1', (item['team_id'],)).fetchone()
                    relations['news_match'] = conn.execute('SELECT * FROM match_archive WHERE id=?', (item['archive_match_id'],)).fetchone()
            return dict(favorite_entities=favorites, subscribed_teams=subscriptions, file_available=file_available, **relations)
        finally:
            conn.close()

    @bp.post('/api/favorites/<kind>/<int:entity_id>')
    @member_required
    def favorite(kind, entity_id):
        data = request.get_json(silent=True) or {}
        desired = data.get('saved')
        if not isinstance(desired, bool):
            return jsonify(status='error', message_key='invalidRequest'), 400
        conn = get_db()
        try:
            valid_entity(conn, kind, entity_id)
            if desired:
                conn.execute('INSERT OR IGNORE INTO user_favorites VALUES (?,?,?,?)', (session['user_id'],kind,entity_id,datetime.now(timezone.utc).replace(tzinfo=None).isoformat()))
            else:
                conn.execute('DELETE FROM user_favorites WHERE user_id=? AND entity_type=? AND entity_id=?', (session['user_id'],kind,entity_id))
            conn.commit()
        finally:
            conn.close()
        return jsonify(status='success', saved=desired)

    @bp.post('/api/subscriptions/<int:team_id>')
    @member_required
    def subscribe(team_id):
        desired = (request.get_json(silent=True) or {}).get('subscribed')
        if not isinstance(desired, bool):
            return jsonify(status='error', message_key='invalidRequest'), 400
        conn=get_db()
        try:
            valid_entity(conn,'team',team_id)
            if desired:
                conn.execute('INSERT OR IGNORE INTO team_subscriptions VALUES (?,?,?)', (session['user_id'],team_id,datetime.now(timezone.utc).replace(tzinfo=None).isoformat()))
            else:
                conn.execute('DELETE FROM team_subscriptions WHERE user_id=? AND team_id=?',(session['user_id'],team_id))
            conn.commit()
        finally:
            conn.close()
        return jsonify(status='success', subscribed=desired)

    @bp.get('/profile/saved')
    @member_required
    def saved():
        conn=get_db()
        try:
            groups={}
            for kind,(table,endpoint,param) in ENTITIES.items():
                groups[kind]=conn.execute(f'''SELECT e.* FROM {table} e JOIN user_favorites f ON f.entity_id=e.id
                    WHERE f.entity_type=? AND f.user_id=? AND e.is_active=1 ORDER BY f.created_at DESC''',(kind,session['user_id'])).fetchall()
            teams=conn.execute('''SELECT t.* FROM teams t JOIN team_subscriptions s ON t.id=s.team_id
                WHERE s.user_id=? AND t.is_active=1 ORDER BY t.name''',(session['user_id'],)).fetchall()
            matches=conn.execute('''SELECT DISTINCT m.* FROM matches m JOIN teams t ON t.name=m.team1 OR t.name=m.team2
                JOIN team_subscriptions s ON s.team_id=t.id WHERE s.user_id=? AND t.is_active=1
                AND m.date>=? AND COALESCE(m.status,'scheduled') NOT IN ('finished','cancelled')
                ORDER BY m.date,m.time,m.id''',(session['user_id'],datetime.now(ZoneInfo('Asia/Bishkek')).date().isoformat())).fetchall()
            submissions=conn.execute('SELECT * FROM horse_submissions WHERE user_id=? ORDER BY created_at DESC',(session['user_id'],)).fetchall()
        finally:
            conn.close()
        return render_template('saved.html',groups=groups,subscription_teams=teams,subscription_matches=matches,submissions=submissions)

    @bp.get('/teams/<int:team_id>/calendar.ics')
    def calendar(team_id):
        conn=get_db()
        try:
            team=valid_entity(conn,'team',team_id)
            rows=conn.execute('''SELECT * FROM matches WHERE (team1=? OR team2=?) AND date>=?
                AND COALESCE(status,'scheduled') NOT IN ('finished','cancelled') ORDER BY date,time''',
                (team['name'],team['name'],datetime.now(ZoneInfo('Asia/Bishkek')).date().isoformat())).fetchall()
        finally:
            conn.close()
        def text(value):
            return str(value or '').replace('\\','\\\\').replace('\n','\\n').replace('\r','').replace(';','\\;').replace(',','\\,')
        lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Ulak Tartysh//Team Schedule//RU','CALSCALE:GREGORIAN']
        for match in rows:
            try:
                when=datetime.strptime(match['date']+' '+(match['time'] or '00:00'),'%Y-%m-%d %H:%M')
            except ValueError:
                continue
            lines+=['BEGIN:VEVENT',f'UID:match-{match["id"]}@ulak-tartysh', 'DTSTAMP:'+datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y%m%dT%H%M%SZ')]
            if match['time']:
                utc=when.replace(tzinfo=ZoneInfo('Asia/Bishkek')).astimezone(timezone.utc)
                lines+=['DTSTART:'+utc.strftime('%Y%m%dT%H%M%SZ')]
            else:
                lines+=['DTSTART;VALUE=DATE:'+when.strftime('%Y%m%d')]
            lines+=['SUMMARY:'+text(match['team1']+' — '+match['team2']), 'LOCATION:'+text(match['location']), 'END:VEVENT']
        lines+=['END:VCALENDAR']
        # RFC 5545: fold at 75 octets, preserving UTF-8 character boundaries.
        folded=[]
        for line in lines:
            segment=''
            for char in line:
                if len((segment+char).encode('utf-8'))>75:
                    folded.append(segment)
                    segment=' '+char
                else:
                    segment+=char
            folded.append(segment)
        return Response('\r\n'.join(folded)+'\r\n',mimetype='text/calendar',headers={'Content-Disposition':f'attachment; filename="team-{team_id}.ics"'})

    @bp.route('/profile/horse/new',methods=['GET','POST'])
    @member_required
    def submit_horse():
        errors=[]
        if request.method=='POST':
            data={key:request.form.get(key,'').strip() for key in ['name','breed','color','owner_name','region','phone','description']}
            for key in ['name','owner_name','region','phone','description']:
                if not data[key]: errors.append('submissionRequired')
            if any(len(value)>200 for key,value in data.items() if key!='description') or len(data['description'])>4000:
                errors.append('submissionTooLong')
            if not re.fullmatch(r'\+?[\d ()-]{7,25}',data['phone']): errors.append('submissionPhoneInvalid')
            numbers={}
            for key,maximum in [('age',50),('price',1000000000)]:
                value=request.form.get(key,'').strip()
                if value and (not value.isdigit() or not 1<=int(value)<=maximum): errors.append('submissionNumbersInvalid')
                numbers[key]=int(value) if value.isdigit() and len(value)<12 else None
            photo=request.files.get('photo')
            if photo and photo.filename:
                photo.stream.seek(0,2)
                size=photo.stream.tell()
                photo.stream.seek(0)
                if size>10*1024*1024: errors.append('submissionPhotoInvalid')
            if not errors:
                photo_url=save_file(photo,{'jpg','jpeg','png','webp'}) if photo and photo.filename else ''
                if photo and photo.filename and not photo_url: errors.append('submissionPhotoInvalid')
                else:
                    conn=get_db()
                    try:
                        conn.execute('''INSERT INTO horse_submissions
                            (user_id,name,breed,color,age,price,owner_name,region,phone,description,photo_url,created_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',(session['user_id'],data['name'],data['breed'],data['color'],numbers['age'],numbers['price'],data['owner_name'],data['region'],data['phone'],data['description'],photo_url,datetime.now(timezone.utc).replace(tzinfo=None).isoformat()))
                        conn.commit()
                    finally:
                        conn.close()
                    return redirect(url_for('portal.saved')+'#my-submissions')
        return render_template('horse_submit.html',errors=list(dict.fromkeys(errors)))

    @bp.get('/admin/readiness')
    @admin_required
    def readiness():
        from scripts.check_site_data import audit
        database = app.config.get('DATABASE', str(Path(app.root_path) / 'database.db'))
        report = audit(database)
        return render_template('admin/readiness.html', report=report)

    @bp.get('/admin/horse-submissions')
    @admin_required
    def review_submissions():
        conn=get_db()
        try:
            rows=conn.execute('''SELECT s.*,u.full_name,u.email FROM horse_submissions s
                JOIN users u ON u.id=s.user_id ORDER BY CASE s.status WHEN 'pending' THEN 0 ELSE 1 END,s.created_at DESC''').fetchall()
        finally:
            conn.close()
        return render_template('admin/horse_submissions.html',submissions=rows)

    @bp.post('/admin/horse-submissions/<int:submission_id>')
    @admin_required
    def review_submission(submission_id):
        action=request.form.get('action')
        if action not in ['approved','rejected']: abort(400)
        conn=get_db()
        try:
            conn.execute('BEGIN IMMEDIATE')
            row=conn.execute('SELECT * FROM horse_submissions WHERE id=?',(submission_id,)).fetchone()
            if not row: abort(404)
            if row['status']!='pending': abort(409)
            horse_id=None
            if action=='approved':
                horse_id=conn.execute('''INSERT INTO horses
                    (name,breed,color,age,price,owner_name,region,phone,description,photo_url,photo_urls,is_for_sale,is_active)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,1,1)''',tuple(row[k] for k in ['name','breed','color','age','price','owner_name','region','phone','description','photo_url'])+(json.dumps([row['photo_url']]) if row['photo_url'] else '[]',)).lastrowid
            conn.execute('UPDATE horse_submissions SET status=?,review_note=?,horse_id=?,reviewed_at=? WHERE id=?',
                (action,request.form.get('review_note','').strip()[:1000],horse_id,datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),submission_id))
            conn.commit()
        finally:
            conn.close()
        flash('Объявление опубликовано.' if action=='approved' else 'Объявление отклонено.','success')
        return redirect(url_for('portal.review_submissions'))

    @bp.route('/forgot-password',methods=['GET','POST'])
    def forgot_password():
        sent=False
        error=False
        if request.method=='POST':
            email=request.form.get('email','').strip().lower()
            if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email):
                return render_template('forgot_password.html',sent=False,error=True),400
            conn=get_db()
            try:
                user=conn.execute('SELECT id FROM users WHERE email=? AND is_active=1 AND is_verified=1',(email,)).fetchone()
                if user:
                    # At most one reset email per account per minute.
                    recent=conn.execute('SELECT 1 FROM password_resets WHERE user_id=? AND expires_at>? AND used_at IS NULL',
                        (user['id'],(datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(minutes=29)).isoformat())).fetchone()
                    if not recent:
                        token=secrets.token_urlsafe(32)
                        conn.execute('UPDATE password_resets SET used_at=? WHERE user_id=? AND used_at IS NULL',(datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),user['id']))
                        conn.execute('INSERT INTO password_resets VALUES (?,?,?,NULL)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],(datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(minutes=30)).isoformat()))
                        conn.commit()
                        try:
                            send_email(email,'Восстановление пароля — Улак Тартыш', 'Для смены пароля откройте ссылку (действует 30 минут):\n'+public_url('portal.reset_password',token=token)+'\nЕсли вы не запрашивали смену пароля, проигнорируйте письмо.')
                        except Exception:
                            app.logger.exception('Password reset email delivery failed')
                sent=True
            finally:
                conn.close()
        return render_template('forgot_password.html',sent=sent,error=error)

    @bp.route('/reset-password/<token>',methods=['GET','POST'])
    def reset_password(token):
        digest=hashlib.sha256(token.encode()).hexdigest()
        conn=get_db()
        try:
            row=conn.execute('''SELECT r.* FROM password_resets r JOIN users u ON u.id=r.user_id
                WHERE token_hash=? AND used_at IS NULL AND expires_at>? AND u.is_active=1 AND u.is_verified=1''',(digest,datetime.now(timezone.utc).replace(tzinfo=None).isoformat())).fetchone()
            if not row: return render_template('reset_password.html',invalid=True),400
            error=False
            if request.method=='POST':
                password=request.form.get('password','')
                if len(password)<6 or len(password)>128 or password!=request.form.get('confirm_password'):
                    error=True
                else:
                    # Claim token atomically so concurrent requests cannot reuse it.
                    changed=conn.execute('UPDATE password_resets SET used_at=? WHERE token_hash=? AND used_at IS NULL AND expires_at>?',
                        (datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),digest,datetime.now(timezone.utc).replace(tzinfo=None).isoformat())).rowcount
                    if not changed: return render_template('reset_password.html',invalid=True),400
                    conn.execute('UPDATE users SET password_hash=?,auth_version=auth_version+1 WHERE id=?',(generate_password_hash(password),row['user_id']))
                    conn.execute('UPDATE password_resets SET used_at=? WHERE user_id=? AND used_at IS NULL',(datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),row['user_id']))
                    conn.commit()
                    session.clear()
                    return render_template('reset_password.html',done=True)
            return render_template('reset_password.html',error=error,invalid=False)
        finally:
            conn.close()

    app.register_blueprint(bp)
