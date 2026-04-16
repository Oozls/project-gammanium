"""
Flask-Login을 사용한 관리자 페이지 관련 라우트
"""

from functools import wraps
from io import BytesIO
import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, session
from flask_login import current_user
from database import fetch_file_bytes
from database.mongodb import (
    get_all_records,
    get_record,
    update_record_status,
    delete_record,
    get_global_stats,
    get_user,
)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """관리자 권한이 필요한 라우트용 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('로그인이 필요합니다', 'error')
            return redirect(url_for('user.login'))
        if not current_user.is_admin:
            flash('관리자만 접근할 수 있습니다', 'error')
            return redirect(url_for('main_page'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/records')
@admin_required
def admin_records():
    """관리자 - 등록 기록 검토 목록"""
    status_filter = request.args.get('status', '')

    try:
        records = get_all_records(status=status_filter if status_filter else None, limit=100)
        stats = get_global_stats()

        # 각 기록에 사용자 정보 추가
        for record in records:
            user = get_user(str(record['user_id']))
            record['user_info'] = user if user else {'username': '알 수 없음', 'email': ''}

        return render_template(
            'admin_records.html',
            records=records,
            stats=stats,
            status_filter=status_filter,
        )

    except Exception as e:
        flash(f'기록 조회 중 오류가 발생했습니다: {str(e)}', 'error')
        return render_template(
            'admin_records.html',
            records=[],
            stats={'total_records': 0, 'pending': 0, 'approved': 0, 'rejected': 0},
            status_filter=status_filter,
        )


@admin_bp.route('/records/<string:record_id>')
@admin_required
def admin_record_detail(record_id):
    """관리자 - 등록 기록 검토 상세"""
    try:
        record = get_record(record_id)

        if not record:
            flash('기록을 찾을 수 없습니다', 'error')
            return redirect(url_for('admin.admin_records'))

        user = get_user(str(record['user_id']))

        return render_template('admin_record_detail.html', record=record, user=user)

    except Exception as e:
        flash(f'기록 조회 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('admin.admin_records'))


@admin_bp.route('/records/<string:record_id>/review', methods=['POST'])
@admin_required
def admin_review_record(record_id):
    """관리자 - 기록 승인/거절 처리"""
    # Prevent duplicate submissions within 2 seconds
    last_submit_key = f"admin_review_{current_user.id}_{record_id}"
    last_submit_time = session.get(last_submit_key)
    current_time = datetime.now().timestamp()

    if last_submit_time and (current_time - last_submit_time) < 2:
        flash('요청이 너무 빠릅니다. 잠시 후 다시 시도해주세요', 'error')
        return redirect(url_for('admin.admin_record_detail', record_id=record_id))

    # Update last submit time
    session[last_submit_key] = current_time

    decision = request.form.get('decision')
    admin_comment = request.form.get('admin_comment', '').strip()

    if decision not in ['approve', 'reject']:
        flash('올바른 결정을 선택해주세요', 'error')
        return redirect(url_for('admin.admin_record_detail', record_id=record_id))

    status = 'approved' if decision == 'approve' else 'rejected'

    try:
        record = get_record(record_id)

        if not record:
            flash('기록을 찾을 수 없습니다', 'error')
            return redirect(url_for('admin.admin_records'))

        update_record_status(record_id, status, admin_comment)

        if status == 'approved':
            flash('기록이 승인되었습니다', 'success')
        else:
            flash('기록이 거절되었습니다', 'warning')

        return redirect(url_for('admin.admin_records'))

    except Exception as e:
        flash(f'처리 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('admin.admin_record_detail', record_id=record_id))


@admin_bp.route('/records/<string:record_id>/delete', methods=['POST'])
@admin_required
def admin_delete_record(record_id):
    """관리자 - 기록 삭제"""
    # Prevent duplicate submissions within 2 seconds
    last_submit_key = f"admin_delete_{current_user.id}_{record_id}"
    last_submit_time = session.get(last_submit_key)
    current_time = datetime.now().timestamp()

    if last_submit_time and (current_time - last_submit_time) < 2:
        flash('요청이 너무 빠릅니다. 잠시 후 다시 시도해주세요', 'error')
        return redirect(url_for('admin.admin_record_detail', record_id=record_id))

    # Update last submit time
    session[last_submit_key] = current_time

    try:
        record = get_record(record_id)

        if not record:
            flash('기록을 찾을 수 없습니다', 'error')
            return redirect(url_for('admin.admin_records'))

        delete_record(record_id)
        flash('기록이 삭제되었습니다', 'success')
        return redirect(url_for('admin.admin_records'))

    except Exception as e:
        flash(f'삭제 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('admin.admin_record_detail', record_id=record_id))


@admin_bp.route('/records/<string:record_id>/image')
@admin_required
def admin_record_image(record_id):
    """관리자 - 기록 증거 이미지 제공"""
    try:
        record = get_record(record_id)

        if not record:
            flash('기록을 찾을 수 없습니다', 'error')
            return redirect(url_for('admin.admin_records'))

        image_url_or_path = record.get('evidence_image')
        if not image_url_or_path:
            flash('이미지가 없습니다', 'error')
            return redirect(url_for('admin.admin_record_detail', record_id=record_id))

        if image_url_or_path.startswith('data/img/'):
            remote_file_path = image_url_or_path
        elif image_url_or_path.startswith('http'):
            remote_file_path = image_url_or_path.split('/resolve/main/')[-1]
        else:
            flash('지원하지 않는 이미지 형식입니다', 'error')
            return redirect(url_for('admin.admin_record_detail', record_id=record_id))

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
        print(f"어드민 이미지 제공 중 오류: {record_id}, {str(e)}")
        flash('이미지를 불러올 수 없습니다', 'error')
        return redirect(url_for('admin.admin_record_detail', record_id=record_id))
