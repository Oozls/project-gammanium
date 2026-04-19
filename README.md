# Gammanium Project

Gammanium은 코드 제출 및 레코드 관리를 위한 웹 애플리케이션입니다. 사용자들이 자신의 코드 실행 결과를 기록하고, 관리자가 이를 검토하고 관리할 수 있는 플랫폼입니다.

## 주요 기능

- **사용자 인증**: 회원가입, 로그인, 로그아웃 기능
- **레코드 관리**: 코드 실행 결과 및 성능 기록 제출 및 조회
- **관리자 패널**: 모든 레코드를 관리하고 상태를 업데이트할 수 있는 관리 대시보드
- **리더보드**: 사용자들 간의 성능 비교를 위한 리더보드
- **사용자 설정**: 개인정보 관리 및 계정 설정
- **HuggingFace 통합**: HuggingFace Hub를 통한 모델 및 데이터 관리

## 기술 스택

### 백엔드
- **Flask 3.1.3**: 경량 Python 웹 프레임워크
- **Flask-Login 0.6.3**: 사용자 인증 및 세션 관리
- **Flask-CORS 6.0.2**: 크로스 오리진 리소스 공유(CORS) 지원
- **MongoDB**: NoSQL 데이터베이스
- **Waitress 3.0.2**: WSGI 애플리케이션 서버

### 라이브러리
- **python-dotenv 1.2.2**: 환경 변수 관리
- **huggingface-hub 1.10.2**: HuggingFace 플랫폼 통합
- **requests 2.33.1**: HTTP 요청 라이브러리

### 프론트엔드
- HTML/Jinja2 템플릿
- CSS/JavaScript (static 폴더)

## 프로젝트 구조

```
project-gammanium/
├── app.py                  # 애플리케이션 진입점
├── pyproject.toml          # 프로젝트 메타데이터 및 의존성
├── .env                    # 환경 변수 (API 키, DB 연결 정보)
├── .gitignore              # Git 무시 파일 설정
│
├── blueprint/              # Flask 블루프린트 (라우팅 모듈)
│   ├── __init__.py         # Flask 앱 초기화 및 설정
│   ├── user.py             # 사용자 인증 라우트 (로그인, 회원가입, 로그아웃)
│   ├── user_model.py       # 사용자 데이터 모델
│   ├── record.py           # 레코드 관리 라우트
│   ├── admin.py            # 관리자 패널 라우트
│   └── settings.py         # 사용자 설정 라우트
│
├── database/               # 데이터베이스 모듈
│   ├── mongodb/            # MongoDB 관련 함수
│   │   ├── __init__.py
│   │   ├── user.py         # 사용자 DB 작업
│   │   └── record.py       # 레코드 DB 작업
│   ├── huggingface/        # HuggingFace 통합
│   │   └── manager.py      # HF 파일/모델 관리
│   └── __init__.py
│
├── templates/              # HTML 템플릿
│   ├── base.html           # 기본 레이아웃 템플릿
│   ├── index.html          # 메인 페이지
│   ├── login.html          # 로그인 페이지
│   ├── signup.html         # 회원가입 페이지
│   ├── my_records.html     # 사용자 레코드 목록
│   ├── my_record_detail.html  # 레코드 상세 정보
│   ├── leaderboard.html    # 리더보드 페이지
│   ├── admin_records.html  # 관리자 레코드 목록
│   ├── admin_record_detail.html # 관리자 레코드 상세
│   └── settings.html       # 사용자 설정 페이지
│
├── static/                 # 정적 파일 (CSS, JS, 이미지)
├── .venv/                  # Python 가상 환경
└── uv.lock                 # 의존성 잠금 파일
```

## 설치 및 실행

### 필수 요구사항
- Python 3.11 이상
- MongoDB 접속 가능한 환경
- HuggingFace API 토큰

### 설치 방법

1. 저장소 클론
```bash
git clone <repository-url>
cd project-gammanium
```

2. 가상 환경 생성 및 활성화
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

3. 의존성 설치
```bash
pip install -r requirements.txt
# 또는 uv를 사용하는 경우
uv sync
```

4. 환경 변수 설정
`.env` 파일을 생성하고 다음 정보를 입력하세요:
```
HF_TOKEN=<your_huggingface_token>
HF_REPO=<your_huggingface_repo>
DB_CONNECT=<your_mongodb_connection_string>
SECRET_KEY=<your_secret_key>
```

### 실행

```bash
python app.py
```

애플리케이션은 `http://0.0.0.0:8000`에서 실행됩니다.

## API 엔드포인트

### 사용자 관련
- `GET /login` - 로그인 페이지
- `POST /login` - 로그인 처리
- `GET /signup` - 회원가입 페이지
- `POST /signup` - 회원가입 처리
- `GET /logout` - 로그아웃

### 레코드 관련
- `GET /records` - 사용자 레코드 목록
- `GET /records/<id>` - 레코드 상세 정보
- `POST /records` - 새 레코드 제출

### 관리자
- `GET /admin/records` - 모든 레코드 조회
- `GET /admin/records/<id>` - 레코드 상세 정보 (관리자)
- `POST /admin/records/<id>/status` - 레코드 상태 업데이트

### 리더보드
- `GET /leaderboard` - 리더보드 조회

### 설정
- `GET /settings` - 사용자 설정 페이지
- `POST /settings` - 설정 업데이트

## 개발

### 코드 구조
- Flask 블루프린트를 사용하여 라우팅을 모듈화
- MongoDB를 통한 데이터 영속성
- Flask-Login을 통한 세션 기반 인증
- CORS 활성화로 크로스 도메인 요청 지원

### 템플릿
- Jinja2 템플릿 엔진 사용
- Bootstrap 등의 CSS 프레임워크 사용 (static 폴더 참고)

## 보안 주의사항

- `.env` 파일은 버전 관리 시스템에 포함되지 않습니다
- 프로덕션 배포 시 `SECRET_KEY`를 강력한 값으로 변경하세요
- MongoDB 연결 문자열은 안전하게 관리하세요
- CORS 설정을 필요한 도메인으로 제한하세요

## 라이선스

이 프로젝트는 개인 프로젝트입니다.

## 문의

문제나 제안사항이 있으시면 이슈를 등록해주세요.