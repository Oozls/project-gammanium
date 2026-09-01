"""
MongoDB 런닝 기록 관리 모듈
.env에서 DB_CONNECT를 받아서 기록 정보를 조회, 생성, 수정, 삭제합니다.
"""

from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from dotenv import load_dotenv
from os import getenv
from datetime import datetime
from bson import ObjectId

# .env 파일 로드
load_dotenv()

# 환경 변수 읽기
DB_CONNECT = getenv("DB_CONNECT")

# MongoDB 클라이언트 초기화
try:
    client = MongoClient(DB_CONNECT, serverSelectionTimeoutMS=5000)
    # 연결 테스트
    client.admin.command('ping')
    db = client['cwhs-runner']
    records_collection = db['records']
except ServerSelectionTimeoutError:
    raise ConnectionError("MongoDB 연결에 실패했습니다. DB_CONNECT를 확인해주세요.")


def _validate_credentials():
    """DB_CONNECT 검증"""
    if not DB_CONNECT:
        raise ValueError("DB_CONNECT가 .env에 정의되지 않았습니다.")


# ============================================================================
# 기록 조회 함수들
# ============================================================================

def get_record(record_id: str) -> dict:
    """
    기록 ID로 기록 정보를 조회합니다.

    Args:
        record_id: 기록 ObjectId (문자열)

    Returns:
        기록 정보 딕셔너리, 없으면 None
    """
    _validate_credentials()

    try:
        record = records_collection.find_one({"_id": ObjectId(record_id)})
        return record
    except Exception as e:
        print(f"기록 조회 중 오류: {e}")
        return None


def get_user_records(user_id: str, status: str = None) -> list:
    """
    사용자의 기록을 조회합니다.

    Args:
        user_id: 사용자 ObjectId (문자열)
        status: 필터할 상태 (pending, approved, rejected, None=모든 상태)

    Returns:
        기록 정보 리스트
    """
    _validate_credentials()

    try:
        query = {"user_id": ObjectId(user_id)}

        if status:
            query["status"] = status

        records = list(records_collection.find(query).sort("submitted_at", -1))
        return records

    except Exception as e:
        print(f"사용자 기록 조회 중 오류: {e}")
        return []


def get_all_records(status: str = None, skip: int = 0, limit: int = 10) -> list:
    """
    모든 기록을 조회합니다 (관리자용 페이지네이션).

    Args:
        status: 필터할 상태 (pending, approved, rejected, None=모든 상태)
        skip: 건너뛸 문서 수
        limit: 조회할 최대 문서 수

    Returns:
        기록 정보 리스트
    """
    _validate_credentials()

    try:
        query = {}

        if status:
            query["status"] = status

        records = list(
            records_collection.find(query)
            .sort("submitted_at", -1)
            .skip(skip)
            .limit(limit)
        )
        return records

    except Exception as e:
        print(f"기록 목록 조회 중 오류: {e}")
        return []


# ============================================================================
# 기록 생성
# ============================================================================

def create_record(user_id: str, record_data: dict) -> dict:
    """
    새로운 기록을 생성합니다.

    Args:
        user_id: 사용자 ObjectId (문자열)
        record_data: 기록 정보 딕셔너리
            - distance (float, 필수): 거리 (km)
            - date (str, 필수): 실행 날짜 (YYYY-MM-DD)
            - comment (str, 선택): 사용자 코멘트
            - evidence_image (str, 선택): 증거 이미지 경로

    Returns:
        생성된 기록 정보 (inserted_id 포함)

    Raises:
        ValueError: 필수 필드 누락
    """
    _validate_credentials()

    # 필수 필드 검증
    required_fields = ["distance", "date"]
    for field in required_fields:
        if field not in record_data or record_data[field] is None:
            raise ValueError(f"{field}는 필수 필드입니다.")

    # 기본값 설정
    record_doc = {
        "user_id": ObjectId(user_id),
        "distance": float(record_data["distance"]),
        "date": record_data["date"],  # YYYY-MM-DD format
        "comment": record_data.get("comment", ""),
        "evidence_image": record_data.get("evidence_image", ""),
        "status": "pending",  # 기본 상태: 검토 대기 중
        "admin_comment": "",
        "submitted_at": datetime.utcnow(),
        "reviewed_at": None,
        "updated_at": datetime.utcnow(),
    }

    try:
        result = records_collection.insert_one(record_doc)
        record_doc["_id"] = result.inserted_id
        return record_doc

    except Exception as e:
        print(f"기록 생성 중 오류: {e}")
        raise


# ============================================================================
# 기록 수정
# ============================================================================

def update_record(record_id: str, update_data: dict) -> dict:
    """
    기록을 수정합니다 (사용자가 승인되기 전 수정용).

    Args:
        record_id: 기록 ObjectId (문자열)
        update_data: 수정할 정보 딕셔너리
            - distance, date, comment, evidence_image 등

    Returns:
        수정된 기록 정보, 없으면 None
    """
    _validate_credentials()

    try:
        # _id는 수정 불가
        if "_id" in update_data:
            del update_data["_id"]

        # 상태가 pending이 아니면 수정 불가
        record = records_collection.find_one({"_id": ObjectId(record_id)})
        if record and record.get("status") != "pending":
            raise ValueError("대기 중인 기록만 수정할 수 있습니다")

        # updated_at 자동 설정
        update_data["updated_at"] = datetime.utcnow()

        result = records_collection.find_one_and_update(
            {"_id": ObjectId(record_id)},
            {"$set": update_data},
            return_document=True
        )

        return result

    except Exception as e:
        print(f"기록 수정 중 오류: {e}")
        raise


def update_record_status(
    record_id: str,
    status: str,
    admin_comment: str = ""
) -> dict:
    """
    기록 상태를 변경합니다 (관리자용).

    Args:
        record_id: 기록 ObjectId (문자열)
        status: 새로운 상태 (approved, rejected)
        admin_comment: 관리자 코멘트

    Returns:
        수정된 기록 정보, 없으면 None
    """
    _validate_credentials()

    if status not in ["approved", "rejected"]:
        raise ValueError("status는 'approved' 또는 'rejected'여야 합니다")

    try:
        result = records_collection.find_one_and_update(
            {"_id": ObjectId(record_id)},
            {
                "$set": {
                    "status": status,
                    "admin_comment": admin_comment,
                    "reviewed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
            return_document=True
        )

        return result

    except Exception as e:
        print(f"기록 상태 변경 중 오류: {e}")
        raise


# ============================================================================
# 기록 삭제
# ============================================================================

def delete_record(record_id: str) -> bool:
    """
    기록을 삭제합니다.

    Args:
        record_id: 기록 ObjectId (문자열)

    Returns:
        성공 여부
    """
    _validate_credentials()

    try:
        result = records_collection.delete_one({"_id": ObjectId(record_id)})
        return result.deleted_count > 0

    except Exception as e:
        print(f"기록 삭제 중 오류: {e}")
        raise


# ============================================================================
# 통계 및 유틸리티 함수들
# ============================================================================

def get_record_count(user_id: str = None, status: str = None) -> int:
    """
    기록 수를 조회합니다.

    Args:
        user_id: 특정 사용자만 조회할 경우 (선택)
        status: 특정 상태만 조회할 경우 (선택)

    Returns:
        기록 수
    """
    _validate_credentials()

    try:
        query = {}

        if user_id:
            query["user_id"] = ObjectId(user_id)
        if status:
            query["status"] = status

        return records_collection.count_documents(query)

    except Exception as e:
        print(f"기록 수 조회 중 오류: {e}")
        return 0


def get_user_record_stats(user_id: str) -> dict:
    """
    사용자의 기록 통계를 조회합니다.

    Args:
        user_id: 사용자 ObjectId (문자열)

    Returns:
        통계 정보 딕셔너리 (total, pending, approved, rejected)
    """
    _validate_credentials()

    try:
        user_obj_id = ObjectId(user_id)

        total = records_collection.count_documents({"user_id": user_obj_id})
        pending = records_collection.count_documents({
            "user_id": user_obj_id,
            "status": "pending"
        })
        approved = records_collection.count_documents({
            "user_id": user_obj_id,
            "status": "approved"
        })
        rejected = records_collection.count_documents({
            "user_id": user_obj_id,
            "status": "rejected"
        })

        # 승인된 기록의 총 거리
        approved_records = list(records_collection.find({
            "user_id": user_obj_id,
            "status": "approved"
        }))
        total_distance = sum(r.get("distance", 0) for r in approved_records)

        return {
            "total": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "total_distance": total_distance,
        }

    except Exception as e:
        print(f"기록 통계 조회 중 오류: {e}")
        return {
            "total": 0,
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "total_distance": 0,
        }


def get_bulk_user_record_stats(user_ids: list) -> dict:
    """
    여러 사용자의 기록 통계를 한 번의 쿼리로 조회합니다 (N+1 방지).

    Args:
        user_ids: 사용자 ObjectId 문자열 리스트

    Returns:
        {user_id_str: {total, pending, approved, rejected, total_distance}}
    """
    _validate_credentials()

    default = lambda: {"total": 0, "pending": 0, "approved": 0, "rejected": 0, "total_distance": 0}
    result = {uid: default() for uid in user_ids}

    try:
        obj_ids = [ObjectId(uid) for uid in user_ids]

        pipeline = [
            {"$match": {"user_id": {"$in": obj_ids}}},
            {"$group": {
                "_id": {"user_id": "$user_id", "status": "$status"},
                "count": {"$sum": 1},
                "distance": {"$sum": "$distance"},
            }},
        ]

        for row in records_collection.aggregate(pipeline):
            uid = str(row["_id"]["user_id"])
            status = row["_id"]["status"]
            if uid not in result:
                continue
            result[uid]["total"] += row["count"]
            if status in ("pending", "approved", "rejected"):
                result[uid][status] = row["count"]
            if status == "approved":
                result[uid]["total_distance"] = row["distance"]

        return result

    except Exception as e:
        print(f"기록 통계 일괄 조회 중 오류: {e}")
        return result


def get_global_stats() -> dict:
    """
    전체 시스템 통계를 조회합니다 (관리자용).

    Returns:
        통계 정보 딕셔너리
    """
    _validate_credentials()

    try:
        total = records_collection.count_documents({})
        pending = records_collection.count_documents({"status": "pending"})
        approved = records_collection.count_documents({"status": "approved"})
        rejected = records_collection.count_documents({"status": "rejected"})

        # 승인된 기록의 총 거리
        approved_records = list(records_collection.find({"status": "approved"}))
        total_distance = sum(r.get("distance", 0) for r in approved_records)

        return {
            "total_records": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "total_distance": total_distance,
        }

    except Exception as e:
        print(f"전체 통계 조회 중 오류: {e}")
        return {
            "total_records": 0,
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "total_distance": 0,
        }


def get_leaderboard(limit: int = None, start_date=None, end_date=None) -> list:
    """
    리더보드를 조회합니다 (승인된 기록 기준으로 사용자별 순위).

    Args:
        limit: 조회할 최대 사용자 수 (None이면 모두)
        start_date: 시작 날짜 (datetime, 선택)
        end_date: 종료 날짜 (datetime, 선택)

    Returns:
        사용자별 통계 리스트 (거리 기준 내림차순 정렬)
        [{
            '_id': ObjectId(user_id),
            'total_distance': float,
            'count': int,
            'average_distance': float
        }, ...]
    """
    _validate_credentials()

    try:
        # 기본 match 조건: 승인된 기록만
        match_stage = {"status": "approved"}

        # 날짜 필터링 추가
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            match_stage["submitted_at"] = date_filter

        pipeline = [
            {"$match": match_stage},
            {"$group": {
                "_id": "$user_id",
                "total_distance": {"$sum": "$distance"},
                "count": {"$sum": 1},
            }},
            {"$addFields": {
                "average_distance": {"$divide": ["$total_distance", "$count"]}
            }},
            {"$sort": {"total_distance": -1}},
        ]

        if limit:
            pipeline.append({"$limit": limit})

        results = list(records_collection.aggregate(pipeline))
        return results

    except Exception as e:
        print(f"리더보드 조회 중 오류: {e}")
        return []


def get_class_leaderboard(start_date=None, end_date=None) -> dict:
    """
    반별 리더보드를 조회합니다 (학번 기준).

    학번 형식: [123]0[1-8](0[1-9]|[1-2][0-9]|3[0-9])
    - 1번째 자리: 학년 (1, 2, 3)
    - 3번째 자리: 반 (1-8)

    Returns:
        반별 통계 딕셔너리
        {
            "1-1": {"total_distance": float, "count": int},
            ...
            "3-8": {"total_distance": float, "count": int}
        }
    """
    _validate_credentials()

    try:
        from database.mongodb.user import get_user

        # 기본 match 조건: 승인된 기록만
        match_stage = {"status": "approved"}

        # 날짜 필터링 추가
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            match_stage["submitted_at"] = date_filter

        # 승인된 기록 조회
        records = list(records_collection.find(match_stage))

        # 반별 통계 계산
        class_stats = {}
        for grade in range(1, 4):
            for cls in range(1, 9):
                class_key = f"{grade}-{cls}"
                class_stats[class_key] = {"total_distance": 0, "count": 0, "participants": set()}

        # 각 기록에서 사용자의 학번을 조회하고 반별로 집계
        for record in records:
            try:
                user = get_user(str(record['user_id']))
                if user and user.get('student_id'):
                    student_id = user['student_id']
                    if len(student_id) >= 3:
                        grade = int(student_id[0])
                        cls = int(student_id[2])

                        if 1 <= grade <= 3 and 1 <= cls <= 8:
                            class_key = f"{grade}-{cls}"
                            class_stats[class_key]['total_distance'] += record['distance']
                            class_stats[class_key]['count'] += 1
                            class_stats[class_key]['participants'].add(str(record['user_id']))
            except (ValueError, KeyError, IndexError):
                continue

        # Set을 정수로 변환
        for class_key in class_stats:
            class_stats[class_key]['participants'] = len(class_stats[class_key]['participants'])

        return class_stats

    except Exception as e:
        print(f"반별 리더보드 조회 중 오류: {e}")
        return {}


if __name__ == "__main__":
    # 테스트 코드
    try:
        print("MongoDB 기록 모듈 초기화 중...")
        print(f"Database: {db.name}")

        # 전체 통계 확인
        stats = get_global_stats()
        print(f"\n전체 통계:")
        print(f"  총 기록: {stats['total_records']}건")
        print(f"  대기 중: {stats['pending']}건")
        print(f"  승인됨: {stats['approved']}건")
        print(f"  거절됨: {stats['rejected']}건")
        print(f"  총 거리: {stats['total_distance']:.1f}km")

    except Exception as e:
        print(f"오류 발생: {e}")
