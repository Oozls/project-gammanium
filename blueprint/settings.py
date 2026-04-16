"""
Flask-Login을 사용한 사용자 설정 페이지 관련 라우트
"""

import os
import tempfile
from io import BytesIO
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from database import upload_file, fetch_file_bytes
from database.mongodb import update_user, get_user

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings')
@login_required
def settings_page():
    """설정 페이지"""
    return render_template('settings.html')


@settings_bp.route('/settings/profile-image', methods=['POST'])
@login_required
def upload_profile_image():
    """프로필 사진 업로드"""
    try:
        # 이미지 파일 수신
        image_file = request.files.get('profile_image')

        if not image_file or not image_file.filename:
            flash('파일을 선택해주세요', 'error')
            return redirect(url_for('settings.settings_page'))

        # 확장자 검증
        ALLOWED_EXTENSIONS = {'png', 'jpeg', 'jpg'}
        ext = image_file.filename.rsplit('.', 1)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            flash('이미지는 PNG, JPG, JPEG 형식만 허용됩니다', 'error')
            return redirect(url_for('settings.settings_page'))

        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as tmp:
            tmp_path = tmp.name
            image_file.save(tmp_path)

        try:
            # HuggingFace에 업로드
            remote_path = f"data/img/{str(current_user.id)}/profile.{ext}"
            hf_url = upload_file(tmp_path, remote_path)

            # MongoDB에 프로필 이미지 URL 저장
            update_user(str(current_user.id), {'profile_image': hf_url})

            # 현재 사용자의 profile_image 속성 업데이트
            current_user.profile_image = hf_url

            flash('프로필 사진이 업로드되었습니다', 'success')
            return redirect(url_for('settings.settings_page'))

        finally:
            # 임시 파일 삭제
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        flash(f'파일 업로드 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('settings.settings_page'))


@settings_bp.route('/image/profile/<user_id>')
def get_profile_image(user_id):
    """
    사용자의 프로필 이미지를 제공합니다.
    HuggingFace Hub에서 이미지를 메모리에 로드하여 반환합니다.
    """
    try:
        user = get_user(user_id)

        if not user:
            return ('사용자를 찾을 수 없습니다', 404)

        image_url_or_path = user.get('profile_image') if user else None
        if not image_url_or_path:
            return ('이미지가 없습니다', 404)

        if image_url_or_path.startswith('data/img/'):
            remote_file_path = image_url_or_path
        elif image_url_or_path.startswith('http'):
            remote_file_path = image_url_or_path.split('/resolve/main/')[-1]
        else:
            return ('지원하지 않는 이미지 형식입니다', 400)

        image_bytes = fetch_file_bytes(remote_file_path)

        _, ext = os.path.splitext(remote_file_path)
        mime_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
        }
        mime_type = mime_type_map.get(ext.lower(), 'image/jpeg')

        buf = BytesIO(image_bytes)
        buf.seek(0)
        return send_file(buf, mimetype=mime_type, as_attachment=False)

    except Exception as e:
        print(f"프로필 이미지 제공 중 오류: {user_id}, {str(e)}")
        return ('이미지를 불러올 수 없습니다', 500)
