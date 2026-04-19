"""
Flask-Login을 사용한 사용자 인증 라우트
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database.mongodb import (
    get_user_by_username,
    get_user_by_email,
    create_user,
)
from .user_model import User

logger = logging.getLogger(__name__)

user_bp = Blueprint('user', __name__)


@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    """사용자 로그인"""
    # 이미 로그인한 사용자는 홈으로 리다이렉트
    if current_user.is_authenticated:
        return redirect(url_for('main_page'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # 입력 검증
        if not username or not password:
            flash('사용자명과 비밀번호를 입력해주세요', 'error')
            return render_template('login.html')

        try:
            # 사용자 조회
            user_data = get_user_by_username(username)
            if not user_data:
                flash('아이디 또는 비밀번호가 올바르지 않습니다', 'error')
                return render_template('login.html')

            # 비밀번호 확인
            if not check_password_hash(user_data['password'], password):
                flash('아이디 또는 비밀번호가 올바르지 않습니다', 'error')
                return render_template('login.html')

            # User 객체 생성 및 로그인
            user = User(
                user_id=str(user_data['_id']),
                username=user_data['username'],
                email=user_data['email'],
                is_admin=user_data.get('is_admin', False),
            )
            login_user(user)

            flash('로그인되었습니다', 'success')
            return redirect(url_for('main_page'))

        except Exception as e:
            logger.exception('로그인 처리 오류')
            flash('로그인 중 오류가 발생했습니다', 'error')
            return render_template('login.html')

    return render_template('login.html')


@user_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """사용자 회원가입"""
    # 이미 로그인한 사용자는 홈으로 리다이렉트
    if current_user.is_authenticated:
        return redirect(url_for('main_page'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()

        # 입력 검증
        if not username or not email or not password or not password_confirm:
            flash('모든 필드를 입력해주세요', 'error')
            return render_template('signup.html')

        if len(username) < 3:
            flash('사용자명은 3자 이상이어야 합니다', 'error')
            return render_template('signup.html')

        if len(password) < 8:
            flash('비밀번호는 8자 이상이어야 합니다', 'error')
            return render_template('signup.html')

        if password != password_confirm:
            flash('비밀번호가 일치하지 않습니다', 'error')
            return render_template('signup.html')

        try:
            # 중복 확인
            if get_user_by_username(username):
                flash('이미 사용 중인 사용자명입니다', 'error')
                return render_template('signup.html')

            if get_user_by_email(email):
                flash('이미 등록된 이메일입니다', 'error')
                return render_template('signup.html')

            # 비밀번호 해시
            hashed_password = generate_password_hash(password)

            # 사용자 등록
            user_data = {
                'username': username,
                'email': email,
                'password': hashed_password,
                'is_admin': False,
                'name': username,
                'profile_image': '',
            }
            new_user = create_user(user_data)

            # User 객체 생성 및 자동 로그인
            user = User(
                user_id=str(new_user['_id']),
                username=new_user['username'],
                email=new_user['email'],
                is_admin=new_user.get('is_admin', False),
            )
            login_user(user)

            flash('회원가입되었습니다', 'success')
            return redirect(url_for('main_page'))

        except ValueError as e:
            flash(str(e), 'error')
            return render_template('signup.html')
        except Exception as e:
            logger.exception('회원가입 처리 오류')
            flash('회원가입 중 오류가 발생했습니다', 'error')
            return render_template('signup.html')

    return render_template('signup.html')


@user_bp.route('/logout')
@login_required
def logout():
    """사용자 로그아웃"""
    logout_user()
    flash('로그아웃되었습니다', 'success')
    return redirect(url_for('main_page'))
