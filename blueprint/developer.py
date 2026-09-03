"""
Flask-Login을 사용한 개발자 문의함 관련 라우트
"""

from functools import wraps
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from database.mongodb import (
    get_user,
    get_users_by_ids,
    get_all_threads,
    get_thread_count,
    get_thread,
    send_developer_reply,
    mark_read_by_developer,
)
from .pagination import build_page_numbers

logger = logging.getLogger(__name__)

developer_bp = Blueprint('developer', __name__, url_prefix='/developer')

THREADS_PER_PAGE = 20
MAX_MESSAGE_LENGTH = 1000


def developer_required(f):
    """개발자 권한이 필요한 라우트용 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('로그인이 필요합니다', 'error')
            return redirect(url_for('user.login'))
        if not current_user.is_developer:
            flash('개발자만 접근할 수 있습니다', 'error')
            return redirect(url_for('main_page'))
        return f(*args, **kwargs)
    return decorated_function


@developer_bp.route('/inquiries')
@developer_required
def inquiry_list():
    """개발자 - 문의 목록"""
    try:
        page = request.args.get('page', 1, type=int)

        total_count = get_thread_count()
        total_pages = max(1, (total_count + THREADS_PER_PAGE - 1) // THREADS_PER_PAGE)
        page = max(1, min(page, total_pages))

        threads = get_all_threads(skip=(page - 1) * THREADS_PER_PAGE, limit=THREADS_PER_PAGE)

        # 각 스레드에 사용자 정보 추가 (일괄 조회로 N+1 방지)
        users_by_id = get_users_by_ids([str(t['user_id']) for t in threads])
        for t in threads:
            t['user_info'] = users_by_id.get(str(t['user_id']))
            t['last_message'] = t['messages'][-1] if t.get('messages') else None

        return render_template(
            'developer_inquiries.html',
            threads=threads,
            current_page=page,
            total_pages=total_pages,
            page_numbers=build_page_numbers(page, total_pages),
            total_count=total_count,
        )

    except Exception as e:
        logger.exception('문의 목록 조회 오류')
        flash('문의 목록 조회 중 오류가 발생했습니다', 'error')
        return render_template(
            'developer_inquiries.html', threads=[],
            current_page=1, total_pages=1, page_numbers=[1], total_count=0,
        )


@developer_bp.route('/inquiries/<string:user_id>')
@developer_required
def inquiry_detail(user_id):
    """개발자 - 문의 상세 및 답장"""
    try:
        thread = get_thread(user_id)
        if not thread:
            flash('문의를 찾을 수 없습니다', 'error')
            return redirect(url_for('developer.inquiry_list'))

        mark_read_by_developer(user_id)

        inquiry_user = get_user(user_id)
        return render_template('developer_inquiry_detail.html', thread=thread, inquiry_user=inquiry_user)

    except Exception as e:
        logger.exception('문의 상세 조회 오류')
        flash('문의 조회 중 오류가 발생했습니다', 'error')
        return redirect(url_for('developer.inquiry_list'))


@developer_bp.route('/inquiries/<string:user_id>/reply', methods=['POST'])
@developer_required
def inquiry_reply(user_id):
    """개발자 - 문의 답장 전송"""
    text = request.form.get('text', '').strip()

    if not text:
        flash('답장 내용을 입력해주세요', 'error')
        return redirect(url_for('developer.inquiry_detail', user_id=user_id))
    if len(text) > MAX_MESSAGE_LENGTH:
        flash(f'답장은 {MAX_MESSAGE_LENGTH}자 이하여야 합니다', 'error')
        return redirect(url_for('developer.inquiry_detail', user_id=user_id))

    try:
        send_developer_reply(user_id, current_user.username, text)
        flash('답장을 보냈습니다', 'success')
    except Exception as e:
        logger.exception('문의 답장 전송 오류')
        flash('답장 전송 중 오류가 발생했습니다', 'error')

    return redirect(url_for('developer.inquiry_detail', user_id=user_id))
