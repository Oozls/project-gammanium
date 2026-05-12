"""
Flask-Login을 사용한 사용자 인증 라우트
"""

import logging
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database.mongodb.user import (
    get_user_by_username,
    get_user_by_name,
    get_user_by_email,
    create_user,
    get_user_by_student_id,
    update_user,
    get_user,
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
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '').strip()

        # 입력 검증
        if not name or not password:
            flash('실명과 비밀번호를 입력해주세요', 'error')
            return render_template('login.html')

        try:
            # 사용자 조회
            user_data = get_user_by_name(name)
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
                student_id=user_data.get('student_id'),
                role=user_data.get('role'),
                bio=user_data.get('bio', ''),
                name=user_data.get('name', ''),
            )
            login_user(user)

            # 마이그레이션: 학번/역할 없으면 프로필 완성 페이지로 리다이렉트
            if not user_data.get('student_id') or not user_data.get('role'):
                flash('계정을 완성하기 위해 학번과 역할을 입력해주세요', 'info')
                return redirect(url_for('user.complete_profile'))

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
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()
        role = request.form.get('role', '').strip()
        student_id = request.form.get('student_id', '').strip()

        # 입력 검증
        if not name or not username or not email or not password or not password_confirm or not role:
            flash('모든 필드를 입력해주세요', 'error')
            return render_template('signup.html')

        if len(name) < 2:
            flash('실명은 2자 이상이어야 합니다', 'error')
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

        # 역할 검증
        if role not in ['student', 'teacher']:
            flash('올바른 역할을 선택해주세요', 'error')
            return render_template('signup.html')

        # 학번 검증 (역할이 학생이면 필수 및 정규식 적용, 교사면 선택사항)
        student_id_pattern = r'^[123]0[1-8](0[1-9]|[1-2][0-9]|3[0-9])$'
        if role == 'student':
            if not student_id:
                flash('학번을 입력해주세요', 'error')
                return render_template('signup.html')
            if not re.match(student_id_pattern, student_id):
                flash('학번 형식이 올바르지 않습니다 (예: 30209)', 'error')
                return render_template('signup.html')

        try:
            # 중복 확인
            if get_user_by_name(name):
                flash('이미 등록된 실명입니다', 'error')
                return render_template('signup.html')

            if get_user_by_username(username):
                flash('이미 사용 중인 사용자명입니다', 'error')
                return render_template('signup.html')

            if get_user_by_email(email):
                flash('이미 등록된 이메일입니다', 'error')
                return render_template('signup.html')

            # 학번 중복 확인 (학생일 때만)
            if role == 'student' and get_user_by_student_id(student_id):
                flash('이미 등록된 학번입니다', 'error')
                return render_template('signup.html')

            # 비밀번호 해시
            hashed_password = generate_password_hash(password)

            # 사용자 등록
            user_data = {
                'name': name,
                'username': username,
                'email': email,
                'password': hashed_password,
                'is_admin': False,
                'profile_image': '',
                'student_id': student_id if role == 'student' else '',
                'role': role,
            }
            new_user = create_user(user_data)

            # User 객체 생성 및 자동 로그인
            user = User(
                user_id=str(new_user['_id']),
                username=new_user['username'],
                email=new_user['email'],
                is_admin=new_user.get('is_admin', False),
                student_id=new_user.get('student_id'),
                role=new_user.get('role'),
                bio=new_user.get('bio', ''),
                name=new_user.get('name', ''),
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


@user_bp.route('/complete-profile', methods=['GET', 'POST'])
@login_required
def complete_profile():
    """기존 계정의 학번/역할 정보 추가 (마이그레이션)"""
    user_data = get_user(str(current_user.id))

    # 이미 학번/역할이 있으면 홈으로 리다이렉트
    if user_data.get('student_id') and user_data.get('role'):
        return redirect(url_for('main_page'))

    if request.method == 'POST':
        role = request.form.get('role', '').strip()
        student_id = request.form.get('student_id', '').strip()

        # 입력 검증
        if not role:
            flash('역할을 선택해주세요', 'error')
            return render_template('complete_profile.html')

        # 역할 검증
        if role not in ['student', 'teacher']:
            flash('올바른 역할을 선택해주세요', 'error')
            return render_template('complete_profile.html')

        # 학번 검증 (역할이 학생이면 필수 및 정규식 적용)
        student_id_pattern = r'^[123]0[1-8](0[1-9]|[1-2][0-9]|3[0-9])$'
        if role == 'student':
            if not student_id:
                flash('학번을 입력해주세요', 'error')
                return render_template('complete_profile.html')
            if not re.match(student_id_pattern, student_id):
                flash('학번 형식이 올바르지 않습니다 (예: 30209)', 'error')
                return render_template('complete_profile.html')

        try:
            # 학번 중복 확인 (학생일 때만)
            if role == 'student':
                existing_user = get_user_by_student_id(student_id)
                if existing_user:
                    flash('이미 등록된 학번입니다', 'error')
                    return render_template('complete_profile.html')

            # 사용자 정보 업데이트
            update_data = {
                'role': role,
                'student_id': student_id if role == 'student' else '',
            }
            update_user(str(current_user.id), update_data)

            # 세션의 current_user 정보 업데이트
            current_user.student_id = student_id if role == 'student' else ''
            current_user.role = role

            flash('프로필 정보가 저장되었습니다', 'success')
            return redirect(url_for('main_page'))

        except Exception as e:
            logger.exception('프로필 완성 처리 오류')
            flash('프로필 저장 중 오류가 발생했습니다', 'error')
            return render_template('complete_profile.html')

    return render_template('complete_profile.html')


@user_bp.route('/logout')
@login_required
def logout():
    """사용자 로그아웃"""
    logout_user()
    flash('로그아웃되었습니다', 'success')
    return redirect(url_for('main_page'))
