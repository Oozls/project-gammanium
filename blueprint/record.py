"""
Flask-Login을 사용한 런닝 기록 관련 라우트
"""

import os
import tempfile
from io import BytesIO
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from database import upload_file, fetch_file_bytes, delete_file
from database.mongodb import (
    create_record,
    get_record,
    get_user_records,
    get_user_record_stats,
    update_record,
    delete_record,
    get_leaderboard,
    get_user,
)

record_bp = Blueprint('record', __name__)


@record_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def running_record():
    """기록 등록 페이지"""
    if request.method == 'POST':
        # Prevent duplicate submissions within 2 seconds
        last_submit_key = f"last_submit_{current_user.id}"
        last_submit_time = session.get(last_submit_key)
        current_time = datetime.now().timestamp()

        if last_submit_time and (current_time - last_submit_time) < 2:
            flash('요청이 너무 빠릅니다. 잠시 후 다시 시도해주세요', 'error')
            return render_template('submit.html')

        # Update last submit time
        session[last_submit_key] = current_time

        distance = request.form.get('distance', '').strip()
        date = request.form.get('date', '').strip()
        comment = request.form.get('comment', '').strip()

        # 파일 수신 (선택 사항)
        image_file = request.files.get('evidence_image')

        # 확장자 검증 (파일이 있을 때만)
        ALLOWED_EXTENSIONS = {'png', 'jpeg', 'jpg'}
        if image_file and image_file.filename:
            ext = image_file.filename.rsplit('.', 1)[-1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                flash('이미지는 PNG, JPG, JPEG 형식만 허용됩니다', 'error')
                return render_template('submit.html')

        # 입력 검증
        if not distance or not date:
            flash('거리와 날짜는 필수 입력 항목입니다', 'error')
            return render_template('submit.html')

        try:
            # 거리 값 검증
            distance_km = float(distance)
            if distance_km <= 0:
                flash('거리는 0보다 커야 합니다', 'error')
                return render_template('submit.html')

            # 1단계: 기록을 일단 빈 증거이미지로 생성
            record_data = {
                'distance': distance_km,
                'date': date,
                'comment': comment,
                'evidence_image': '',
            }
            new_record = create_record(str(current_user.id), record_data)
            record_id = str(new_record['_id'])

            # 2단계: 이미지 파일이 있으면 HuggingFace에 업로드 후 URL 갱신
            if image_file and image_file.filename:
                try:
                    original_filename = secure_filename(image_file.filename)
                    ext = original_filename.rsplit('.', 1)[-1].lower()
                    remote_path = f"data/img/{str(current_user.id)}/{record_id}/{original_filename}"

                    # 임시 파일로 저장
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as tmp:
                        tmp_path = tmp.name
                        image_file.save(tmp_path)

                    try:
                        # HuggingFace에 업로드
                        hf_url = upload_file(tmp_path, remote_path)
                        # 기록의 이미지 URL 갱신
                        update_record(record_id, {'evidence_image': hf_url})
                    finally:
                        # 임시 파일 삭제
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)

                except Exception as img_err:
                    # 이미지 업로드 실패 시 기록은 그대로 유지, 경고 메시지만 표시
                    flash(f'기록은 저장되었으나 이미지 업로드에 실패했습니다: {str(img_err)}', 'warning')

            flash('기록이 등록되었습니다. 관리자의 검토를 기다려주세요', 'success')
            return redirect(url_for('record.my_records'))

        except ValueError as e:
            flash(f'입력 오류: {str(e)}', 'error')
            return render_template('submit.html')
        except Exception as e:
            flash(f'기록 등록 중 오류가 발생했습니다: {str(e)}', 'error')
            return render_template('submit.html')

    return render_template('submit.html')


@record_bp.route('/leaderboard')
def leaderboard():
    """리더보드 페이지"""
    try:
        # 페이지 번호 및 필터 설정
        page = request.args.get('page', 1, type=int)
        current_filter = request.args.get('filter', 'all')
        items_per_page = 10

        # 날짜 범위 계산
        now = datetime.now(timezone.utc)
        start_date = None

        if current_filter == 'week':
            start_date = now - timedelta(days=7)
        elif current_filter == 'month':
            start_date = now - timedelta(days=30)
        # 'all'일 때는 start_date = None

        # 승인된 기록 기준 리더보드 조회
        leaderboard_data = get_leaderboard(start_date=start_date)

        # 각 사용자 정보 추가
        leaderboard_with_users = []
        for idx, entry in enumerate(leaderboard_data, 1):
            user = get_user(str(entry['_id']))
            leaderboard_with_users.append({
                'rank': idx,
                'user_id': entry['_id'],
                'user': user,
                'total_distance': entry['total_distance'],
                'count': entry['count'],
                'average_distance': entry['average_distance'],
            })

        # 전체 페이지 수 계산
        total_count = len(leaderboard_with_users)
        total_pages = (total_count + items_per_page - 1) // items_per_page

        # 유효한 페이지 범위 확인
        if page < 1 or page > total_pages:
            page = 1

        # 현재 페이지의 데이터
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        leaderboard_page = leaderboard_with_users[start_idx:end_idx]

        # 전체 통계 (항상 전체 시간 기준으로 표시)
        from database.mongodb import get_global_stats
        global_stats = get_global_stats()

        # 페이지 번호 리스트 생성 (최대 5개 표시, 현재 페이지 기준)
        page_numbers = []
        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)

        if start_page > 1:
            page_numbers.append(1)
            if start_page > 2:
                page_numbers.append('...')

        for p in range(start_page, end_page + 1):
            page_numbers.append(p)

        if end_page < total_pages:
            if end_page < total_pages - 1:
                page_numbers.append('...')
            page_numbers.append(total_pages)

        return render_template(
            'leaderboard.html',
            leaderboard=leaderboard_page,
            leaderboard_all=leaderboard_with_users,
            stats=global_stats,
            current_page=page,
            total_pages=total_pages,
            page_numbers=page_numbers,
            current_filter=current_filter,
        )

    except Exception as e:
        print(f"리더보드 조회 중 오류: {str(e)}")
        return render_template(
            'leaderboard.html',
            leaderboard=[],
            leaderboard_all=[],
            stats={'total_distance': 0, 'total_records': 0},
            current_page=1,
            total_pages=1,
            page_numbers=[1],
            current_filter='all',
        )


@record_bp.route('/records')
@login_required
def my_records():
    """사용자의 등록 요청 목록"""
    try:
        # 현재 사용자의 모든 기록 조회
        records = get_user_records(str(current_user.id))

        # 사용자의 기록 통계 조회
        stats = get_user_record_stats(str(current_user.id))

        return render_template(
            'my_records.html',
            records=records,
            stats=stats
        )

    except Exception as e:
        flash(f'기록 조회 중 오류가 발생했습니다: {str(e)}', 'error')
        return render_template(
            'my_records.html',
            records=[],
            stats={
                'total': 0,
                'pending': 0,
                'approved': 0,
                'rejected': 0,
                'total_distance': 0,
            }
        )


@record_bp.route('/records/<record_id>')
@login_required
def my_record_detail(record_id):
    """사용자의 등록 요청 상세 내용"""
    try:
        record = get_record(record_id)

        # 기록이 없거나 현재 사용자의 기록이 아닌 경우
        if not record:
            flash('기록을 찾을 수 없습니다', 'error')
            return redirect(url_for('record.my_records'))

        if str(record.get('user_id')) != str(current_user.id):
            flash('이 기록에 접근할 권한이 없습니다', 'error')
            return redirect(url_for('record.my_records'))

        return render_template('my_record_detail.html', record=record)

    except Exception as e:
        flash(f'기록 조회 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('record.my_records'))


@record_bp.route('/records/<record_id>/delete', methods=['POST'])
@login_required
def delete_my_record(record_id):
    """기록 삭제 (pending 상태만 가능)"""
    # Prevent duplicate submissions within 2 seconds
    last_submit_key = f"delete_record_{current_user.id}_{record_id}"
    last_submit_time = session.get(last_submit_key)
    current_time = datetime.now().timestamp()

    if last_submit_time and (current_time - last_submit_time) < 2:
        flash('요청이 너무 빠릅니다. 잠시 후 다시 시도해주세요', 'error')
        return redirect(url_for('my_record_detail', record_id=record_id))

    # Update last submit time
    session[last_submit_key] = current_time

    try:
        record = get_record(record_id)

        if not record:
            flash('기록을 찾을 수 없습니다', 'error')
            return redirect(url_for('record.my_records'))

        if str(record.get('user_id')) != str(current_user.id):
            flash('이 기록에 접근할 권한이 없습니다', 'error')
            return redirect(url_for('record.my_records'))

        if record.get('status') != 'pending':
            flash('대기 중인 기록만 삭제할 수 있습니다', 'warning')
            return redirect(url_for('record.my_record_detail', record_id=record_id))

        # 이미지 파일 삭제 (HuggingFace에서)
        image_url_or_path = record.get('evidence_image')
        if image_url_or_path:
            try:
                if image_url_or_path.startswith('data/img/'):
                    remote_file_path = image_url_or_path
                elif image_url_or_path.startswith('http'):
                    remote_file_path = image_url_or_path.split('/resolve/main/')[-1]
                else:
                    remote_file_path = None

                if remote_file_path:
                    delete_file(remote_file_path)
            except Exception as img_err:
                print(f"이미지 삭제 실패: {str(img_err)}")
                # 이미지 삭제 실패해도 계속 진행 (기록은 삭제)

        # 기록 삭제
        delete_record(record_id)
        flash('기록이 삭제되었습니다', 'success')
        return redirect(url_for('record.my_records'))

    except Exception as e:
        flash(f'기록 삭제 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('record.my_records'))


@record_bp.route('/image/<record_id>')
@login_required
def get_record_image(record_id):
    """
    기록의 증거 이미지를 제공합니다.
    HuggingFace Hub에서 이미지를 메모리에 로드하여 반환합니다.
    """
    try:
        record = get_record(record_id)

        if not record:
            flash('기록을 찾을 수 없습니다', 'error')
            return redirect(url_for('record.my_records'))

        if str(record.get('user_id')) != str(current_user.id):
            flash('이 기록에 접근할 권한이 없습니다', 'error')
            return redirect(url_for('record.my_records'))

        image_url_or_path = record.get('evidence_image')
        if not image_url_or_path:
            flash('이미지가 없습니다', 'error')
            return redirect(url_for('record.my_record_detail', record_id=record_id))

        if image_url_or_path.startswith('data/img/'):
            remote_file_path = image_url_or_path
        elif image_url_or_path.startswith('http'):
            remote_file_path = image_url_or_path.split('/resolve/main/')[-1]
        else:
            flash('지원하지 않는 이미지 형식입니다', 'error')
            return redirect(url_for('record.my_record_detail', record_id=record_id))

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
        print(f"이미지 제공 중 오류: {record_id}, {str(e)}")
        flash('이미지를 불러올 수 없습니다', 'error')
        return redirect(url_for('record.my_records'))
