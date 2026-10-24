"""Behavior checks run exclusively against a temporary copy of the site's database."""
from contextlib import closing
import hashlib
import importlib.util
import io
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('portal_app_tests', ROOT / 'app.py')
portal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portal)
from utils.portal_features import ensure_portal_schema


class PortalFeaturesTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / 'test.db'
        with closing(sqlite3.connect(f'file:{ROOT / "database.db"}?mode=ro', uri=True)) as source, closing(sqlite3.connect(self.database)) as target:
            source.backup(target)
            ensure_portal_schema(target, portal.ensure_column)
            self.user_id = target.execute('''INSERT INTO users
                (full_name,email,password_hash,is_active,is_verified,role,created_at)
                VALUES (?,?,?,1,1,'user',?)''', ('Test Member','portal-test@example.invalid', generate_password_hash('old-password'),datetime.now(timezone.utc).replace(tzinfo=None).isoformat())).lastrowid
            self.team_id = target.execute("INSERT INTO teams(name,is_active,region) VALUES ('Portal Test Team',1,'Test Region')").lastrowid
            self.player_id = target.execute("INSERT INTO players(name,team_id,is_active) VALUES ('Portal Test Player',?,1)",(self.team_id,)).lastrowid
            self.horse_id = target.execute('''INSERT INTO horses
                (name,breed,color,age,price,owner_name,region,player_id,is_active,is_for_sale)
                VALUES ('Portal Test Horse','Test Breed','Bay',7,250000,'Test Owner','Test Region',?,1,1)''',(self.player_id,)).lastrowid
            self.match_id=target.execute("INSERT INTO matches(date,time,team1,team2,status,location) VALUES ('2099-01-01','12:00','Portal Test Team','Opponent','scheduled','Test Venue')").lastrowid
            self.archive_id=target.execute("INSERT INTO match_archive(team1_name,team2_name,match_date) VALUES ('Portal Test Team','Opponent','2026-01-01')").lastrowid
            target.commit()
        portal.app.config.update(TESTING=True,DATABASE=str(self.database),WTF_CSRF_ENABLED=False)
        self.client=portal.app.test_client()

    def tearDown(self):
        self.temporary.cleanup()

    def login(self, admin=False):
        with self.client.session_transaction() as session:
            session['user_id']=self.user_id
            session['user_name']='Test Member'
            if admin: session['logged_in']=True

    def query(self,sql,args=()):
        with closing(sqlite3.connect(self.database)) as conn:
            rows=conn.execute(sql,args).fetchall()
            conn.commit()
            return rows

    def test_public_pages_and_missing_records(self):
        paths=['/','/horses','/horses/'+str(self.horse_id),'/players/'+str(self.player_id),'/team/'+str(self.team_id),'/archive/match/'+str(self.archive_id),'/news','/media','/archive','/statistics','/players','/documents','/all-documents','/regulations','/transfers','/rules','/contacts','/about','/hippodromes','/referees','/league/higher','/league/first','/forgot-password']
        for path in paths:
            with self.subTest(path=path): self.assertEqual(self.client.get(path).status_code,200)
        self.assertEqual(self.client.get('/horses/99999999').status_code,404)

    def test_home_without_media_and_future_matches(self):
        self.query('DELETE FROM matches')
        self.query('DELETE FROM videos')
        self.query('DELETE FROM photo_albums')
        response=self.client.get('/')
        self.assertEqual(response.status_code,200)
        self.assertIn('homeNoMediaTitle',response.text)

    def test_filter_combination_and_unknown_values(self):
        page=self.client.get('/horses?breed=Test+Breed&region=Test+Region&sale=sale&min_price=200000&max_price=300000&min_age=6&max_age=8&sort=price').text
        self.assertIn('Portal Test Horse',page)
        self.assertNotIn('Portal Test Horse',self.client.get('/horses?breed=Test+Breed&max_price=1').text)
        self.assertEqual(self.client.get('/horses?sort=INVALID&min_price=garbage&page=999').status_code,200)
        self.assertNotIn('Portal Test Horse',self.client.get('/horses?q=%27+OR+1%3D1--').text)

    def test_favorites_require_member_and_are_idempotent(self):
        url=f'/api/favorites/horse/{self.horse_id}'
        self.assertEqual(self.client.post(url,json={'saved':True}).status_code,401)
        self.login()
        for _ in range(2): self.assertEqual(self.client.post(url,json={'saved':True}).status_code,200)
        self.assertEqual(len(self.query('SELECT * FROM user_favorites WHERE user_id=?',(self.user_id,))),1)
        self.assertIn('Portal Test Horse',self.client.get('/profile/saved').text)
        self.client.post(url,json={'saved':False})
        self.assertNotIn('Portal Test Horse',self.client.get('/profile/saved').text)
        self.assertEqual(self.client.post(url,json={'saved':'yes'}).status_code,400)
        self.assertEqual(self.client.post('/api/favorites/bogus/1',json={'saved':True}).status_code,404)

    def test_favorites_isolation_and_blocked_user(self):
        self.login()
        self.client.post(f'/api/favorites/team/{self.team_id}',json={'saved':True})
        with self.client.session_transaction() as session: session['user_id']=99999999
        self.assertEqual(self.client.get('/profile/saved').status_code,302)
        self.login()
        self.query('UPDATE users SET is_active=0 WHERE id=?',(self.user_id,))
        self.assertEqual(self.client.post(f'/api/favorites/team/{self.team_id}',json={'saved':False}).status_code,401)

    def test_subscription_and_calendar_timezone(self):
        self.login()
        self.client.post(f'/api/subscriptions/{self.team_id}',json={'subscribed':True})
        self.assertIn('2099',self.client.get('/profile/saved').text)
        calendar=self.client.get(f'/teams/{self.team_id}/calendar.ics')
        self.assertEqual(calendar.status_code,200)
        self.assertIn('DTSTART:20990101T060000Z',calendar.text)
        self.assertTrue(all(len(line.encode())<=75 for line in calendar.text.split('\r\n')))
        self.client.post(f'/api/subscriptions/{self.team_id}',json={'subscribed':False})
        self.assertNotIn('2099',self.client.get('/profile/saved').text)

    def test_submission_and_moderation_are_separate(self):
        self.login()
        payload=dict(name='Submitted Horse',owner_name='Test Owner',region='Test Region',phone='+996 700 123 456',description='Description',price='100000',age='8')
        self.assertEqual(self.client.post('/profile/horse/new',data=payload).status_code,302)
        self.assertFalse(self.query("SELECT * FROM horses WHERE name='Submitted Horse'"))
        row_id=self.query('SELECT id FROM horse_submissions WHERE user_id=?',(self.user_id,))[0][0]
        self.assertEqual(self.client.post(f'/admin/horse-submissions/{row_id}',data={'action':'approved'}).status_code,302)
        self.assertFalse(self.query("SELECT * FROM horses WHERE name='Submitted Horse'"))
        self.login(admin=True)
        self.assertEqual(self.client.get('/admin/horse-submissions').status_code,200)
        self.assertEqual(self.client.post(f'/admin/horse-submissions/{row_id}',data={'action':'approved'}).status_code,302)
        self.assertEqual(len(self.query("SELECT * FROM horses WHERE name='Submitted Horse'")),1)
        self.assertEqual(self.client.post(f'/admin/horse-submissions/{row_id}',data={'action':'approved'}).status_code,409)

    def test_submission_validation(self):
        self.login()
        self.client.post('/profile/horse/new',data={'name':'Invalid','price':'-10','age':'100'})
        self.assertFalse(self.query('SELECT id FROM horse_submissions WHERE user_id=?',(self.user_id,)))
        with self.assertLogs(portal.logger,level='ERROR'):
            response=self.client.post('/profile/horse/new',data=dict(name='Invalid',owner_name='Owner',region='Region',phone='+996 700 123 456',description='Text',photo=(io.BytesIO(b'not an image'),'test.jpg')))
        self.assertIn('submissionPhotoInvalid',response.text)
        self.assertFalse(self.query('SELECT id FROM horse_submissions WHERE user_id=?',(self.user_id,)))

    def test_password_reset_single_use_and_expiry(self):
        token='portal-test-token'
        digest=hashlib.sha256(token.encode()).hexdigest()
        self.query('INSERT INTO password_resets VALUES (?,?,?,NULL)',(digest,self.user_id,(datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(minutes=30)).isoformat()))
        response=self.client.post('/reset-password/'+token,data={'password':'new-password','confirm_password':'new-password'})
        self.assertEqual(response.status_code,200)
        hashed=self.query('SELECT password_hash FROM users WHERE id=?',(self.user_id,))[0][0]
        self.assertTrue(check_password_hash(hashed,'new-password'))
        self.assertEqual(self.client.get('/reset-password/'+token).status_code,400)
        self.query('INSERT INTO password_resets VALUES (?,?,?,NULL)',(hashlib.sha256(b'expired').hexdigest(),self.user_id,(datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(minutes=1)).isoformat()))
        self.assertEqual(self.client.get('/reset-password/expired').status_code,400)

    def test_forgot_password_does_not_disclose_accounts(self):
        # No real emails leave the process.
        with patch.object(portal,'smtp_is_configured',return_value=True),patch.object(portal.smtplib,'SMTP') as smtp,patch.object(portal.smtplib,'SMTP_SSL'):
            existing=self.client.post('/forgot-password',data={'email':'portal-test@example.invalid'})
            missing=self.client.post('/forgot-password',data={'email':'unknown@example.invalid'})
            self.assertEqual(existing.status_code,200)
            self.assertIn('resetEmailSent',existing.text)
            self.assertIn('resetEmailSent',missing.text)
            self.assertEqual(len(self.query('SELECT * FROM password_resets WHERE user_id=?',(self.user_id,))),1)
            self.client.post('/forgot-password',data={'email':'portal-test@example.invalid'})
            self.assertEqual(len(self.query('SELECT * FROM password_resets WHERE user_id=?',(self.user_id,))),1)

    def test_csrf_is_required(self):
        self.login()
        portal.app.config['WTF_CSRF_ENABLED']=True
        self.assertEqual(self.client.post(f'/api/favorites/horse/{self.horse_id}',json={'saved':True}).status_code,400)
        html=self.client.get('/horses/'+str(self.horse_id)).text
        token=re.search(r'name="csrf-token" content="([^"]+)"',html)[1]
        self.assertEqual(self.client.post(f'/api/favorites/horse/{self.horse_id}',json={'saved':True},headers={'X-CSRFToken':token}).status_code,200)

    def test_member_pages_are_not_cached(self):
        self.login()
        self.assertEqual(self.client.get('/profile/saved').headers['Cache-Control'],'private, no-store')
        self.assertEqual(self.client.get('/horses').headers['Cache-Control'],'private, no-store')

    def test_password_reset_revokes_existing_session(self):
        self.login()
        self.assertEqual(self.client.get('/profile/saved').status_code,200)
        self.query('UPDATE users SET auth_version=auth_version+1 WHERE id=?',(self.user_id,))
        self.assertEqual(self.client.get('/profile/saved').status_code,302)

    def test_delete_requires_post_and_csrf(self):
        self.login(admin=True)
        url='/admin/delete/horses/'+str(self.horse_id)
        self.assertEqual(self.client.get(url).status_code,405)
        portal.app.config['WTF_CSRF_ENABLED']=True
        self.assertEqual(self.client.post(url).status_code,400)
        self.assertTrue(self.query('SELECT id FROM horses WHERE id=?',(self.horse_id,)))

    def test_registration_email_confirmation(self):
        with patch.object(portal,'send_registration_confirmation',return_value=True) as mail:
            payload=dict(fullname='New Member',email='new-member@example.invalid',password='test-password',confirm_password='test-password')
            response=self.client.post('/api/register',json=payload)
            self.assertEqual(response.status_code,200)
            token=mail.call_args.args[2]
        row=self.query("SELECT id,is_verified FROM users WHERE email='new-member@example.invalid'")[0]
        self.assertEqual(row[1],0)
        self.assertEqual(self.client.get('/confirm-email/'+token).status_code,302)
        self.assertEqual(self.query('SELECT is_verified FROM users WHERE id=?',(row[0],))[0][0],1)
        self.assertEqual(self.client.post('/api/register',json=payload).status_code,409)
        with self.client.session_transaction() as session: session.clear()
        self.client.get('/confirm-email/'+token)
        with self.client.session_transaction() as session: self.assertNotIn('user_id',session)

    def test_backup_can_restore_database_and_assets(self):
        from scripts.backup_site import create_backup
        import tarfile
        from contextlib import closing
        temporary_root=Path(self.temporary.name)/'backup-root'
        (temporary_root/'static/uploads').mkdir(parents=True)
        (temporary_root/'static/uploads/test.txt').write_text('test asset')
        (temporary_root/'.env').write_text('SECRET_KEY=not-for-backup')
        archive=create_backup(temporary_root,self.database,temporary_root/'backups')
        restored=temporary_root/'restored'
        with tarfile.open(archive) as tar:
            self.assertNotIn('.env',tar.getnames())
            tar.extractall(restored,filter='data')
        with closing(sqlite3.connect(restored/'database.db')) as conn:
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(conn.execute('SELECT name FROM horses WHERE id=?',(self.horse_id,)).fetchone()[0],'Portal Test Horse')
        self.assertEqual((restored/'static/uploads/test.txt').read_text(),'test asset')

    def test_admin_horse_and_news_metadata(self):
        self.login(admin=True)
        self.assertEqual(self.client.get('/admin').status_code,200)
        self.assertEqual(self.client.get('/admin/readiness').status_code,200)
        self.client.post('/admin/update-horse/'+str(self.horse_id),data=dict(name='Portal Test Horse',horse_owner_name='Edited owner',horse_region='Edited region',horse_player_id=str(self.player_id),horse_achievements='Cup',horse_rating_note='Assessment',is_active='1'))
        self.assertEqual(self.query('SELECT owner_name,region,player_id FROM horses WHERE id=?',(self.horse_id,))[0],('Edited owner','Edited region',self.player_id))
        self.client.post('/admin/add-news',data=dict(title='Test related news',date='2026-10-06',is_published='1',news_team_id=str(self.team_id),news_archive_match_id=str(self.archive_id)))
        row=self.query("SELECT id,team_id,archive_match_id FROM news WHERE title='Test related news'")[0]
        self.assertEqual(row[1:],(self.team_id,self.archive_id))
        self.assertIn('Portal Test Team',self.client.get('/news/'+str(row[0])).text)
        self.assertIn('Test related news',self.client.get('/archive/match/'+str(self.archive_id)).text)


if __name__=='__main__': unittest.main()
