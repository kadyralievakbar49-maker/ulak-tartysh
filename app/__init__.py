from flask import Flask
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
import os

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv('SECRET_KEY', 'super_secret_key_for_sessions')
    app.config['UPLOAD_FOLDER'] = 'static/uploads'
    app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

    # Initialize CSRF protection
    csrf = CSRFProtect(app)

    # Register blueprints or routes
    from . import routes
    app.register_blueprint(routes.bp)

    return app