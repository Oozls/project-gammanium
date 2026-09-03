# from database import is_account_present, obj
from dotenv import load_dotenv
from flask import Flask, render_template, get_flashed_messages, redirect, request, url_for
from flask_cors import CORS
from flask_login import LoginManager
from os import getenv
from html import escape
import sys

from .user import user_bp
from .record import record_bp
from .admin import admin_bp
from .settings import settings_bp
from .inquiry import inquiry_bp
from .developer import developer_bp
from .user_model import User

load_dotenv()

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

secret_key = getenv('SECRET_KEY')
if not secret_key:
    print("CRITICAL: SECRET_KEY 환경변수가 설정되지 않았습니다. 운영 환경에서는 반드시 설정하세요.", file=sys.stderr)
    secret_key = 'default-secret-key-change-in-production'
app.config['SECRET_KEY'] = secret_key

app.config['SESSION_TYPE'] = 'filesystem'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
app.template_folder = "../templates"
app.static_folder = "../static"

CORS(app, origins=["http://localhost:5000", "http://localhost:8000", "http://127.0.0.1:5000", "http://127.0.0.1:8000"])

# Flask-Login 설정
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'user.login'
login_manager.login_message = '로그인이 필요합니다'


@login_manager.user_loader
def load_user(user_id):
    """사용자 ID로 사용자 객체 로드"""
    return User.get_user_by_id(user_id)


# Context processor for flash messages
@app.context_processor
def inject_flash_messages():
    """모든 템플릿에 플래시 메시지 전달"""
    messages = get_flashed_messages(with_categories=True)
    flash_html = ""

    for category, message in messages:
        flash_type = category if category in ['success', 'error', 'info'] else 'info'
        flash_html += f'<div data-flash-message="{escape(message)}" data-flash-type="{escape(flash_type)}" style="display:none;"></div>'

    return dict(flash_messages_html=flash_html)

# 블루프린트 등록
app.register_blueprint(user_bp)
app.register_blueprint(record_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(inquiry_bp)
app.register_blueprint(developer_bp)

@app.route('/')
def main_page():
    return render_template('index.html')

@app.errorhandler(413)
def request_entity_too_large(e):
    from flask import flash
    flash('파일 크기가 너무 큽니다 (최대 10MB)', 'error')
    return redirect(request.referrer or url_for('main_page')), 413





# from datetime import datetime, timedelta, timezone

# KST = timezone(timedelta(hours=9))
# def unix_to_date(t):
#     date = datetime.fromtimestamp(t)
#     today = datetime.today()
#     diff = today - date

#     if diff.days == 0:
#         return datetime.fromtimestamp(t, tz=KST).strftime('%H:%M')
#     else:
#         return datetime.fromtimestamp(t, tz=KST).strftime('%Y.%m.%d')

# app.jinja_env.filters["unix_to_date"] = unix_to_date




# def id_to_username(id):
#     is_present, users = is_account_present({'_id': obj(id)})
#     if not is_present: return '알 수 없음'
#     user = users[0]
#     return user['username']

# app.jinja_env.filters["id_to_username"] = id_to_username