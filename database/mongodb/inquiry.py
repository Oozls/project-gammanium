"""
MongoDB 문의 메시지 관리 모듈
사용자당 하나의 문의 스레드를 유지합니다 (실시간 채팅이 아닌 게시판형 문의).
"""

from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from dotenv import load_dotenv
from os import getenv
from datetime import datetime
from bson import ObjectId

load_dotenv()

DB_CONNECT = getenv("DB_CONNECT")

try:
    client = MongoClient(DB_CONNECT, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db = client['cwhs-runner']
    inquiries_collection = db['inquiries']
except ServerSelectionTimeoutError:
    raise ConnectionError("MongoDB 연결에 실패했습니다. DB_CONNECT를 확인해주세요.")


def _validate_credentials():
    """DB_CONNECT 검증"""
    if not DB_CONNECT:
        raise ValueError("DB_CONNECT가 .env에 정의되지 않았습니다.")


def get_thread(user_id: str) -> dict:
    """
    사용자의 문의 스레드를 조회합니다.

    Args:
        user_id: 사용자 ObjectId (문자열)

    Returns:
        문의 스레드 딕셔너리, 없으면 None
    """
    _validate_credentials()

    try:
        return inquiries_collection.find_one({"user_id": ObjectId(user_id)})
    except Exception as e:
        print(f"문의 스레드 조회 중 오류: {e}")
        return None


def send_user_message(user_id: str, sender_name: str, text: str) -> dict:
    """
    사용자가 문의 메시지를 보냅니다. 스레드가 없으면 새로 생성합니다.

    Args:
        user_id: 사용자 ObjectId (문자열)
        sender_name: 보낸 사람 표시 이름
        text: 메시지 내용

    Returns:
        업데이트된 문의 스레드
    """
    _validate_credentials()

    message = {
        "sender": "user",
        "name": sender_name,
        "text": text,
        "created_at": datetime.utcnow(),
    }

    try:
        inquiries_collection.update_one(
            {"user_id": ObjectId(user_id)},
            {
                "$push": {"messages": message},
                "$set": {
                    "updated_at": datetime.utcnow(),
                    "unread_by_developer": True,
                    "unread_by_user": False,
                },
                "$setOnInsert": {
                    "user_id": ObjectId(user_id),
                    "created_at": datetime.utcnow(),
                },
            },
            upsert=True,
        )
        return get_thread(user_id)

    except Exception as e:
        print(f"문의 메시지 전송 중 오류: {e}")
        raise


def send_developer_reply(user_id: str, developer_name: str, text: str) -> dict:
    """
    개발자가 문의에 답장합니다.

    Args:
        user_id: 문의를 보낸 사용자 ObjectId (문자열)
        developer_name: 답장하는 개발자 표시 이름
        text: 답장 내용

    Returns:
        업데이트된 문의 스레드
    """
    _validate_credentials()

    message = {
        "sender": "developer",
        "name": developer_name,
        "text": text,
        "created_at": datetime.utcnow(),
    }

    try:
        inquiries_collection.update_one(
            {"user_id": ObjectId(user_id)},
            {
                "$push": {"messages": message},
                "$set": {
                    "updated_at": datetime.utcnow(),
                    "unread_by_user": True,
                    "unread_by_developer": False,
                },
            },
        )
        return get_thread(user_id)

    except Exception as e:
        print(f"문의 답장 전송 중 오류: {e}")
        raise


def get_all_threads(skip: int = 0, limit: int = 20) -> list:
    """
    모든 문의 스레드를 최신순으로 조회합니다 (개발자용).

    Args:
        skip: 건너뛸 문서 수
        limit: 조회할 최대 문서 수

    Returns:
        문의 스레드 리스트
    """
    _validate_credentials()

    try:
        return list(
            inquiries_collection.find()
            .sort("updated_at", -1)
            .skip(skip)
            .limit(limit)
        )
    except Exception as e:
        print(f"문의 목록 조회 중 오류: {e}")
        return []


def get_thread_count() -> int:
    """
    전체 문의 스레드 수를 조회합니다.

    Returns:
        문의 스레드 수
    """
    _validate_credentials()

    try:
        return inquiries_collection.count_documents({})
    except Exception as e:
        print(f"문의 수 조회 중 오류: {e}")
        return 0


def mark_read_by_developer(user_id: str) -> None:
    """개발자가 문의를 확인했음을 표시합니다."""
    _validate_credentials()

    try:
        inquiries_collection.update_one(
            {"user_id": ObjectId(user_id)},
            {"$set": {"unread_by_developer": False}},
        )
    except Exception as e:
        print(f"문의 읽음 처리 중 오류: {e}")


def mark_read_by_user(user_id: str) -> None:
    """사용자가 개발자 답장을 확인했음을 표시합니다."""
    _validate_credentials()

    try:
        inquiries_collection.update_one(
            {"user_id": ObjectId(user_id)},
            {"$set": {"unread_by_user": False}},
        )
    except Exception as e:
        print(f"문의 읽음 처리 중 오류: {e}")
