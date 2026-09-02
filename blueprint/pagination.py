"""목록 페이지(사용자 관리, 기록 검토 등)에서 공용으로 쓰는 페이지네이션/검색 헬퍼"""

import re

USER_SEARCH_FIELD_MAP = {
    'username': 'username',
    'student_id': 'student_id',
    'email': 'email',
    'name': 'name',
}


def build_user_search_query(search_type: str, search_query: str) -> dict:
    """검색 유형/검색어로 사용자 컬렉션용 MongoDB 필터를 만듭니다."""
    if not search_query:
        return {}
    field = USER_SEARCH_FIELD_MAP.get(search_type, 'username')
    return {field: {'$regex': re.escape(search_query), '$options': 'i'}}


def build_page_numbers(page: int, total_pages: int) -> list:
    """현재 페이지 기준 앞뒤 2개씩 보여주고 나머지는 '...'으로 생략"""
    if total_pages <= 1:
        return [1] if total_pages == 1 else []

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

    return page_numbers
