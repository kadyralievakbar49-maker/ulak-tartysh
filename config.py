import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_key_change_in_prod')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'database.db')
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    @staticmethod
    def init_app(app):
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        for sub in ['teams', 'players', 'horses', 'documents', 'news', 'matches']:
            os.makedirs(os.path.join(Config.UPLOAD_FOLDER, sub), exist_ok=True)