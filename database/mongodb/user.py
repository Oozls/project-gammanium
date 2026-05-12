"""
MongoDB 사용자 관리 모듈
.env에서 DB_CONNECT를 받아서 사용자 정보를 조회, 생성, 수정, 삭제합니다.
"""

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError
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
    users_collection = db['users']
except ServerSelectionTimeoutError:
    raise ConnectionError("MongoDB 연결에 실패했습니다. DB_CONNECT를 확인해주세요.")


def _validate_credentials():
    """DB_CONNECT 검증"""
    if not DB_CONNECT:
        raise ValueError("DB_CONNECT가 .env에 정의되지 않았습니다.")


# ============================================================================
# 사용자 조회 함수들
# ============================================================================

def get_user(user_id: str) -> dict:
    """
    사용자 ID로 사용자 정보를 조회합니다.

    Args:
        user_id: 사용자 ObjectId (문자열)

    Returns:
        사용자 정보 딕셔너리, 없으면 None
    """
    _validate_credentials()

    try:
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        return user
    except Exception as e:
        print(f"사용자 조회 중 오류: {e}")
        return None


def get_user_by_username(username: str) -> dict:
    """
    사용자명으로 사용자 정보를 조회합니다.

    Args:
        username: 사용자명

    Returns:
        사용자 정보 딕셔너리, 없으면 None
    """
    _validate_credentials()

    try:
        user = users_collection.find_one({"username": username})
        return user
    except Exception as e:
        print(f"사용자 조회 중 오류: {e}")
        return None


def get_user_by_name(name: str) -> dict:
    """
    실명으로 사용자 정보를 조회합니다.

    Args:
        name: 사용자의 실명

    Returns:
        사용자 정보 딕셔너리, 없으면 None
    """
    _validate_credentials()

    try:
        user = users_collection.find_one({"name": name})
        return user
    except Exception as e:
        print(f"사용자 조회 중 오류: {e}")
        return None


def get_user_by_email(email: str) -> dict:
    """
    이메일로 사용자 정보를 조회합니다.

    Args:
        email: 사용자 이메일

    Returns:
        사용자 정보 딕셔너리, 없으면 None
    """
    _validate_credentials()

    try:
        user = users_collection.find_one({"email": email})
        return user
    except Exception as e:
        print(f"사용자 조회 중 오류: {e}")
        return None


def get_user_by_student_id(student_id: str) -> dict:
    """
    학번으로 사용자 정보를 조회합니다.

    Args:
        student_id: 학번

    Returns:
        사용자 정보 딕셔너리, 없으면 None
    """
    _validate_credentials()

    try:
        user = users_collection.find_one({"student_id": student_id})
        return user
    except Exception as e:
        print(f"사용자 조회 중 오류: {e}")
        return None


# ============================================================================
# 어드민 여부 조회
# ============================================================================

def is_admin(user_id: str) -> bool:
    """
    사용자가 어드민 권한을 가지고 있는지 확인합니다.

    Args:
        user_id: 사용자 ObjectId (문자열)

    Returns:
        어드민 여부 (True/False)
    """
    _validate_credentials()

    try:
        user = users_collection.find_one(
            {"_id": ObjectId(user_id)},
            {"is_admin": 1}
        )
        if not user:
            return False
        return user.get("is_admin", False)
    except Exception as e:
        print(f"어드민 여부 조회 중 오류: {e}")
        return False


# ============================================================================
# 사용자 등록
# ============================================================================

def create_user(user_data: dict) -> dict:
    """
    새로운 사용자를 등록합니다.

    Args:
        user_data: 사용자 정보 딕셔너리
            - name (str, 필수): 실명
            - username (str, 필수): 사용자명 (닉네임)
            - email (str, 필수): 이메일
            - password (str, 필수): 비밀번호 (해시된 형태)
            - role (str, 필수): 역할 ('student' 또는 'teacher')
            - student_id (str, 선택): 학번
            - is_admin (bool, 선택): 어드민 여부 (기본값: False)
            - profile_image (str, 선택): 프로필 이미지 URL

    Returns:
        생성된 사용자 정보 (inserted_id 포함)

    Raises:
        ValueError: 필수 필드 누락
        DuplicateKeyError: 중복된 username 또는 email
    """
    _validate_credentials()

    # 필수 필드 검증
    required_fields = ["name", "username", "email", "password"]
    for field in required_fields:
        if field not in user_data or not user_data[field]:
            raise ValueError(f"{field} is required.")

    # 기본값 설정
    user_doc = {
        "username": user_data["username"],
        "email": user_data["email"],
        "password": user_data["password"],
        "student_id": user_data.get("student_id"),
        "role": user_data.get("role"),
        "is_admin": user_data.get("is_admin", False),
        "name": user_data.get("name", ""),
        "profile_image": user_data.get("profile_image", ""),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    try:
        # 중복 확인
        if users_collection.find_one({"name": user_data["name"]}):
            raise ValueError(f"이미 존재하는 이름입니다: {user_data['name']}")
        if users_collection.find_one({"username": user_data["username"]}):
            raise ValueError(f"이미 존재하는 username입니다: {user_data['username']}")
        if users_collection.find_one({"email": user_data["email"]}):
            raise ValueError(f"이미 존재하는 email입니다: {user_data['email']}")

        result = users_collection.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id
        return user_doc

    except DuplicateKeyError as e:
        print(f"사용자 등록 중 중복 오류: {e}")
        raise
    except Exception as e:
        print(f"사용자 등록 중 오류: {e}")
        raise


# ============================================================================
# 사용자 정보 수정
# ============================================================================

def update_user(user_id: str, update_data: dict) -> dict:
    """
    사용자 정보를 수정합니다.

    Args:
        user_id: 사용자 ObjectId (문자열)
        update_data: 수정할 정보 딕셔너리
            - email, name, profile_image, student_id, role 등

    Returns:
        수정된 사용자 정보, 없으면 None
    """
    _validate_credentials()

    try:
        # _id, password, is_admin은 수정 불가
        for blocked in ("_id", "password", "is_admin"):
            update_data.pop(blocked, None)

        # updated_at 자동 설정
        update_data["updated_at"] = datetime.utcnow()

        # 중복 확인 (email 수정 시)
        if "email" in update_data:
            existing_user = users_collection.find_one({
                "email": update_data["email"],
                "_id": {"$ne": ObjectId(user_id)}
            })
            if existing_user:
                raise ValueError(f"이미 존재하는 email입니다: {update_data['email']}")

        # 중복 확인 (username 수정 시)
        if "username" in update_data:
            existing_user = users_collection.find_one({
                "username": update_data["username"],
                "_id": {"$ne": ObjectId(user_id)}
            })
            if existing_user:
                raise ValueError(f"이미 존재하는 username입니다: {update_data['username']}")

        result = users_collection.find_one_and_update(
            {"_id": ObjectId(user_id)},
            {"$set": update_data},
            return_document=True
        )

        return result

    except Exception as e:
        print(f"사용자 정보 수정 중 오류: {e}")
        raise


def change_password(user_id: str, new_password: str) -> bool:
    """
    사용자 비밀번호를 변경합니다.

    Args:
        user_id: 사용자 ObjectId (문자열)
        new_password: 새로운 비밀번호 (해시된 형태)

    Returns:
        성공 여부
    """
    _validate_credentials()

    try:
        result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "password": new_password,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0

    except Exception as e:
        print(f"비밀번호 변경 중 오류: {e}")
        raise


# ============================================================================
# 사용자 삭제
# ============================================================================

def delete_user(user_id: str) -> bool:
    """
    사용자를 삭제합니다.

    Args:
        user_id: 사용자 ObjectId (문자열)

    Returns:
        성공 여부
    """
    _validate_credentials()

    try:
        result = users_collection.delete_one({"_id": ObjectId(user_id)})
        return result.deleted_count > 0

    except Exception as e:
        print(f"사용자 삭제 중 오류: {e}")
        raise


# ============================================================================
# 유틸리티 함수들
# ============================================================================

def get_all_users(skip: int = 0, limit: int = 10) -> list:
    """
    모든 사용자를 조회합니다 (페이지네이션).

    Args:
        skip: 건너뛸 문서 수
        limit: 조회할 최대 문서 수

    Returns:
        사용자 정보 리스트
    """
    _validate_credentials()

    try:
        users = list(users_collection.find().skip(skip).limit(limit))
        return users

    except Exception as e:
        print(f"사용자 목록 조회 중 오류: {e}")
        return []


def get_user_count() -> int:
    """
    전체 사용자 수를 조회합니다.

    Returns:
        사용자 수
    """
    _validate_credentials()

    try:
        return users_collection.count_documents({})

    except Exception as e:
        print(f"사용자 수 조회 중 오류: {e}")
        return 0


def get_admin_count() -> int:
    """
    어드민 사용자 수를 조회합니다.

    Returns:
        어드민 사용자 수
    """
    _validate_credentials()

    try:
        return users_collection.count_documents({"is_admin": True})

    except Exception as e:
        print(f"어드민 수 조회 중 오류: {e}")
        return 0


if __name__ == "__main__":
    # 테스트 코드
    try:
        print("MongoDB 사용자 모듈 초기화 중...")
        print(f"Database: {db.name}")

        # 사용자 수 확인
        user_count = get_user_count()
        admin_count = get_admin_count()
        print(f"\n전체 사용자: {user_count}명")
        print(f"어드민 사용자: {admin_count}명")

    except Exception as e:
        print(f"오류 발생: {e}")
