"""
Flask-Login을 사용한 런닝 기록 관련 라우트
"""

import os
import tempfile
import math
import logging
from io import BytesIO
from datetime import datetime, timedelta, timezone, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from database import upload_file, fetch_file_bytes, delete_file, delete_folder
from database.mongodb import (
    create_record,
    get_record,
    get_user_records,
    get_user_record_stats,
    get_bulk_user_record_stats,
    update_record,
    delete_record,
    get_leaderboard,
    get_class_leaderboard,
    get_user,
    get_all_users,
    get_user_count,
    get_users_by_ids,
)
from .pagination import build_page_numbers, build_user_search_query

logger = logging.getLogger(__name__)

record_bp = Blueprint('record', __name__)

USERS_PER_PAGE = 20


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
        run_date = request.form.get('date', '').strip()
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
        if not distance or not run_date:
            flash('거리와 날짜는 필수 입력 항목입니다', 'error')
            return render_template('submit.html')

        try:
            # 거리 값 검증
            distance_km = float(distance)
            if not math.isfinite(distance_km) or distance_km <= 0 or distance_km > 200:
                flash('거리는 0km 초과 200km 이하여야 합니다', 'error')
                return render_template('submit.html')

            # 날짜 검증
            try:
                parsed_date = datetime.strptime(run_date, '%Y-%m-%d').date()
            except ValueError:
                flash('날짜 형식이 올바르지 않습니다 (YYYY-MM-DD)', 'error')
                return render_template('submit.html')

            today = date.today()
            if parsed_date > today:
                flash('미래 날짜는 입력할 수 없습니다', 'error')
                return render_template('submit.html')
            if parsed_date < today - timedelta(days=365):
                flash('1년 이상 지난 날짜는 입력할 수 없습니다', 'error')
                return render_template('submit.html')

            # 코멘트 길이 검증
            if len(comment) > 500:
                flash('코멘트는 500자 이하여야 합니다', 'error')
                return render_template('submit.html')

            # 1단계: 기록을 일단 빈 증거이미지로 생성
            record_data = {
                'distance': distance_km,
                'date': run_date,
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
                    logger.exception('이미지 업로드 오류')
                    flash('기록은 저장되었으나 이미지 업로드에 실패했습니다', 'warning')

            flash('기록이 등록되었습니다. 관리자의 검토를 기다려주세요', 'success')
            return redirect(url_for('record.my_records'))

        except ValueError as e:
            logger.exception('입력 값 오류')
            flash('입력 오류가 발생했습니다', 'error')
            return render_template('submit.html')
        except Exception as e:
            logger.exception('기록 등록 오류')
            flash('기록 등록 중 오류가 발생했습니다', 'error')
            return render_template('submit.html')

    return render_template('submit.html')


@record_bp.route('/leaderboard')
def leaderboard():
    """리더보드 페이지"""
    try:
        # 페이지 번호 및 필터 설정
        page = request.args.get('page', 1, type=int)
        current_filter = request.args.get('filter', 'all')
        current_type = request.args.get('type', 'personal')
        items_per_page = 10

        # 날짜 범위 계산
        now = datetime.now(timezone.utc)
        start_date = None

        if current_filter == 'week':
            start_date = now - timedelta(days=7)
        elif current_filter == 'month':
            start_date = now - timedelta(days=30)
        # 'all'일 때는 start_date = None

        # 승인된 기록 기준 리더보드 조회 (사용자별 집계, 단일 쿼리)
        leaderboard_data = get_leaderboard(start_date=start_date)

        # 전체 페이지 수 계산
        total_count = len(leaderboard_data)
        total_pages = max(1, (total_count + items_per_page - 1) // items_per_page)

        # 유효한 페이지 범위 확인
        if page < 1 or page > total_pages:
            page = 1

        # 현재 페이지 + 포디움(상위 3명)에 필요한 항목만 추림
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_entries = leaderboard_data[start_idx:end_idx]
        top3_entries = leaderboard_data[:3]

        # 필요한 사용자만 일괄 조회 (N+1 방지)
        needed_ids = {str(e['_id']) for e in page_entries} | {str(e['_id']) for e in top3_entries}
        users_by_id = get_users_by_ids(list(needed_ids))

        def build_entry(entry, rank):
            return {
                'rank': rank,
                'user_id': entry['_id'],
                'user': users_by_id.get(str(entry['_id'])),
                'total_distance': entry['total_distance'],
                'count': entry['count'],
                'average_distance': entry['average_distance'],
            }

        leaderboard_page = [build_entry(e, start_idx + i + 1) for i, e in enumerate(page_entries)]
        leaderboard_top3 = [build_entry(e, i + 1) for i, e in enumerate(top3_entries)]

        # 전체 통계 (항상 전체 시간 기준으로 표시)
        from database.mongodb import get_global_stats
        global_stats = get_global_stats()

        # 반별 리더보드 조회
        class_leaderboard = get_class_leaderboard(start_date=start_date)

        return render_template(
            'leaderboard.html',
            leaderboard=leaderboard_page,
            leaderboard_all=leaderboard_top3,
            stats=global_stats,
            current_page=page,
            total_pages=total_pages,
            page_numbers=build_page_numbers(page, total_pages),
            current_filter=current_filter,
            current_type=current_type,
            class_leaderboard=class_leaderboard,
            total_participants=total_count,
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
            total_participants=0,
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
        logger.exception('사용자 기록 조회 오류')
        flash('기록 조회 중 오류가 발생했습니다', 'error')
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
        logger.exception('기록 상세 조회 오류')
        flash('기록 조회 중 오류가 발생했습니다', 'error')
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

        # HuggingFace에서 폴더와 파일 삭제
        image_url_or_path = record.get('evidence_image')
        folder_path = f"data/img/{str(record.get('user_id'))}/{record_id}"

        # 먼저 해당 기록의 폴더 전체 삭제 시도
        try:
            delete_folder(folder_path)
        except Exception as folder_err:
            print(f"폴더 삭제 실패: {folder_path}, {str(folder_err)}")
            # 폴더 삭제 실패 시 개별 파일 삭제 시도
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
                    print(f"개별 파일 삭제 실패: {str(img_err)}")
                    # 파일 삭제 실패해도 계속 진행 (기록은 삭제)

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


@record_bp.route('/image/public/<record_id>')
def get_public_record_image(record_id):
    """
    승인된 기록의 증거 이미지를 공개 제공합니다.
    누구나 접근 가능 (로그인 불필요)
    """
    try:
        record = get_record(record_id)

        if not record:
            return ('기록을 찾을 수 없습니다', 404)

        # 승인된 기록만 이미지 제공
        if record.get('status') != 'approved':
            return ('공개되지 않은 기록입니다', 403)

        image_url_or_path = record.get('evidence_image')
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
        print(f"공개 이미지 제공 중 오류: {record_id}, {str(e)}")
        return ('이미지를 불러올 수 없습니다', 500)


@record_bp.route('/leaderboard/users/<user_id>')
def public_user_records(user_id):
    """리더보드에서 특정 사용자의 승인된 기록 목록 (공개)"""
    try:
        # 사용자 존재 여부 확인
        user = get_user(user_id)
        if not user:
            flash('사용자를 찾을 수 없습니다', 'error')
            return redirect(url_for('record.leaderboard'))

        # 승인된 기록만 조회
        records = get_user_records(user_id, status='approved')

        # 통계 계산
        total_distance = sum(r.get('distance', 0) for r in records)
        stats = {
            'approved': len(records),
            'total_distance': total_distance,
        }

        return render_template(
            'leaderboard_user_records.html',
            user=user,
            records=records,
            stats=stats,
        )
    except Exception as e:
        print(f"사용자 기록 조회 중 오류: {str(e)}")
        flash(f'기록 조회 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('record.leaderboard'))


@record_bp.route('/leaderboard/users/<user_id>/records/<record_id>')
def public_record_detail(user_id, record_id):
    """리더보드에서 특정 기록 상세 (공개, approved만)"""
    try:
        record = get_record(record_id)

        if not record:
            flash('기록을 찾을 수 없습니다', 'error')
            return redirect(url_for('record.public_user_records', user_id=user_id))

        # 해당 사용자의 기록인지 확인
        if str(record.get('user_id')) != str(user_id):
            flash('잘못된 접근입니다', 'error')
            return redirect(url_for('record.public_user_records', user_id=user_id))

        # 승인된 기록만 공개
        if record.get('status') != 'approved':
            flash('공개되지 않은 기록입니다', 'error')
            return redirect(url_for('record.public_user_records', user_id=user_id))

        user = get_user(user_id)

        return render_template(
            'leaderboard_record_detail.html',
            record=record,
            user=user,
            user_id=user_id,
        )
    except Exception as e:
        print(f"공개 기록 상세 조회 중 오류: {str(e)}")
        flash(f'기록 조회 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('record.leaderboard'))


@record_bp.route('/user-search')
def user_search():
    """사용자 검색 페이지"""
    try:
        search_type = request.args.get('search_type', 'username')
        search_query = request.args.get('search_query', '').strip()
        page = request.args.get('page', 1, type=int)

        query = build_user_search_query(search_type, search_query)
        total_count = get_user_count(query)
        total_pages = max(1, (total_count + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
        page = max(1, min(page, total_pages))

        users = get_all_users(skip=(page - 1) * USERS_PER_PAGE, limit=USERS_PER_PAGE, query=query)

        # 각 사용자의 통계 추가 (일괄 조회로 N+1 방지)
        stats_by_user = get_bulk_user_record_stats([str(user['_id']) for user in users])
        for user in users:
            stats = stats_by_user.get(str(user['_id']), {})
            user['total_distance'] = stats.get('total_distance', 0)
            user['record_count'] = stats.get('approved', 0)

        return render_template(
            'user_search.html',
            users=users,
            search_type=search_type,
            search_query=search_query,
            current_page=page,
            total_pages=total_pages,
            page_numbers=build_page_numbers(page, total_pages),
            total_count=total_count,
        )

    except Exception as e:
        logger.exception('사용자 검색 오류')
        flash('사용자 검색 중 오류가 발생했습니다', 'error')
        return render_template(
            'user_search.html', users=[], search_type='username', search_query='',
            current_page=1, total_pages=1, page_numbers=[1], total_count=0,
        )
