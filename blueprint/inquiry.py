"""
Flask-Login을 사용한 문의 위젯 관련 라우트 (사용자용)
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from database.mongodb import get_thread, send_user_message, mark_read_by_user

inquiry_bp = Blueprint('inquiry', __name__, url_prefix='/inquiry')

MAX_MESSAGE_LENGTH = 1000


def _serialize_thread(thread):
    if not thread:
        return {'messages': []}
    return {
        'messages': [
            {
                'sender': m['sender'],
                'name': m['name'],
                'text': m['text'],
                'created_at': m['created_at'].strftime('%Y-%m-%d %H:%M'),
            }
            for m in thread.get('messages', [])
        ]
    }


@inquiry_bp.route('', methods=['GET'])
@login_required
def get_my_thread():
    """내 문의 스레드 조회 (위젯을 열 때 호출)"""
    thread = get_thread(str(current_user.id))
    if thread:
        mark_read_by_user(str(current_user.id))
    return jsonify(_serialize_thread(thread))


@inquiry_bp.route('', methods=['POST'])
@login_required
def post_my_message():
    """문의 메시지 전송"""
    text = (request.get_json(silent=True) or {}).get('text', '').strip()

    if not text:
        return jsonify({'error': '메시지를 입력해주세요'}), 400
    if len(text) > MAX_MESSAGE_LENGTH:
        return jsonify({'error': f'메시지는 {MAX_MESSAGE_LENGTH}자 이하여야 합니다'}), 400

    thread = send_user_message(str(current_user.id), current_user.username, text)
    return jsonify(_serialize_thread(thread))
