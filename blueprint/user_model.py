"""
Flask-Login을 위한 User 모델
"""

from flask_login import UserMixin
from database.mongodb import get_user


class User(UserMixin):
    """Flask-Login과 호환되는 User 클래스"""

    def __init__(self, user_id, username, email, is_admin=False, profile_image=''):
        self.id = user_id  # MongoDB ObjectId (문자열)
        self.username = username
        self.email = email
        self.is_admin = is_admin
        self.profile_image = profile_image

    def is_active(self):
        """사용자가 활성화되어 있는지 확인"""
        return True

    def is_authenticated(self):
        """사용자가 인증되었는지 확인"""
        return True

    def is_anonymous(self):
        """사용자가 익명인지 확인"""
        return False

    @classmethod
    def get_user_by_id(cls, user_id):
        """ID로 사용자 조회"""
        try:
            user_data = get_user(user_id)
            if user_data:
                return cls(
                    user_id=str(user_data['_id']),
                    username=user_data['username'],
                    email=user_data['email'],
                    is_admin=user_data.get('is_admin', False),
                    profile_image=user_data.get('profile_image', ''),
                )
        except Exception as e:
            print(f"사용자 로드 중 오류: {e}")
        return None
