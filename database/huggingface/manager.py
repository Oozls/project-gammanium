from pathlib import Path
from dotenv import load_dotenv
from os import getenv
from io import BytesIO
import requests
from huggingface_hub import (
    HfApi,
    CommitOperationAdd,
    CommitOperationDelete,
    hf_hub_url,
)

load_dotenv()

HF_TOKEN = getenv("HF_TOKEN")
HF_REPO = getenv("HF_REPO")


api = HfApi()


def _validate_credentials():
    if not HF_TOKEN:
        raise ValueError("HF_TOKEN NOT DEFINED")
    if not HF_REPO:
        raise ValueError("HF_REPO NOT DEFINED")

def upload_file(local_file_path: str, remote_file_path: str, commit_message: str = None) -> str:
    _validate_credentials()

    local_path = Path(local_file_path)
    if not local_path.exists():
        raise FileNotFoundError(f"CANNOT FIND FILE IN {local_file_path}")

    if commit_message is None:
        commit_message = f"Upload {remote_file_path}"

    # HuggingFace에 파일 업로드
    api.upload_file(
        path_or_fileobj=local_file_path,
        path_in_repo=remote_file_path,
        repo_id=HF_REPO,
        token=HF_TOKEN,
        commit_message=commit_message,
        repo_type="dataset",
    )

    # CORS를 지원하는 CDN URL 생성
    # hf_hub_url은 HuggingFace CDN을 통한 파일 접근 URL을 반환합니다
    file_url = hf_hub_url(
        repo_id=HF_REPO,
        filename=remote_file_path,
        repo_type="dataset"
    )

    return file_url


def update_file(local_file_path: str, remote_file_path: str, commit_message: str = None) -> str:
    _validate_credentials()

    local_path = Path(local_file_path)
    if not local_path.exists():
        raise FileNotFoundError(f"CANNOT FIND FILE IN {local_file_path}")

    if commit_message is None:
        commit_message = f"Update {remote_file_path}"

    commit_info = api.upload_file(
        path_or_fileobj=local_file_path,
        path_in_repo=remote_file_path,
        repo_id=HF_REPO,
        token=HF_TOKEN,
        commit_message=commit_message,
        repo_type="dataset",
    )

    return commit_info


def delete_file(remote_file_path: str, commit_message: str = None):
    _validate_credentials()

    if commit_message is None:
        commit_message = f"Delete {remote_file_path}"

    operations = [CommitOperationDelete(path_in_repo=remote_file_path)]

    api.create_commit(
        repo_id=HF_REPO,
        operations=operations,
        commit_message=commit_message,
        token=HF_TOKEN,
        repo_type="dataset",
    )


# ----- FOLDERS ----- #


def create_folder(remote_folder_path: str, commit_message: str = None):
    _validate_credentials()

    if commit_message is None:
        commit_message = f"Create folder {remote_folder_path}"

    gitkeep_path = f"{remote_folder_path.rstrip('/')}/.gitkeep"

    api.upload_file(
        path_or_fileobj=b"",
        path_in_repo=gitkeep_path,
        repo_id=HF_REPO,
        token=HF_TOKEN,
        commit_message=commit_message,
        repo_type="dataset",
    )


def delete_folder(remote_folder_path: str, commit_message: str = None):
    """
    폴더와 그 안의 모든 파일을 삭제합니다.

    Args:
        remote_folder_path: 삭제할 폴더 경로 (e.g., "data/img/user_id/record_id")
        commit_message: 커밋 메시지
    """
    _validate_credentials()

    if commit_message is None:
        commit_message = f"Delete folder {remote_folder_path}"

    try:
        # 폴더 내의 모든 파일을 찾기
        tree_entries = api.list_repo_tree(
            repo_id=HF_REPO,
            token=HF_TOKEN,
            recursive=True,
            repo_type="dataset",
        )

        # 폴더 경로 정규화 (뒤의 / 제거)
        folder_path = remote_folder_path.rstrip('/')

        # 해당 폴더에 속한 모든 파일/폴더 찾기
        operations = []
        for item in tree_entries:
            if item.path.startswith(folder_path + '/') or item.path == folder_path:
                # blob_id가 None이면 폴더, 있으면 파일
                if item.blob_id:  # 파일인 경우
                    operations.append(CommitOperationDelete(path_in_repo=item.path))

        # 파일들이 있으면 한 번에 삭제
        if operations:
            api.create_commit(
                repo_id=HF_REPO,
                operations=operations,
                commit_message=commit_message,
                token=HF_TOKEN,
                repo_type="dataset",
            )
    except Exception as e:
        print(f"폴더 삭제 중 오류: {remote_folder_path}, {e}")
        raise


# ----- UTILITIES ----- #


def list_files(folder_path: str = "") -> list:
    _validate_credentials()

    try:
        files = []
        
        tree_entries = api.list_repo_tree(
            repo_id=HF_REPO,
            token=HF_TOKEN,
            recursive=True,
            repo_type="dataset",
        )

        for item in tree_entries:
            if folder_path == "" or item.path.startswith(folder_path):
                if not item.blob_id:
                    files.append(item.path)

        return files
    except Exception as e:
        print(f"AN ERROR OCCURED WHILE REQUESTING FILE LISTS :\n {e}")
        return []


def get_repo_info() -> dict:
    _validate_credentials()

    try:
        repo_info = api.repo_info(
            repo_id=HF_REPO,
            token=HF_TOKEN,
            repo_type="dataset",
        )
        return repo_info
    except Exception as e:
        print(f"AN ERROR OCCURED WHILE REQUESTING REPO INFO :\n {e}")
        return {}


def fetch_file_bytes(remote_file_path: str) -> bytes:
    """
    HuggingFace Hub의 파일을 메모리에 로드합니다 (디스크 저장 없음).
    BytesIO로 제공하거나 바이트로 직접 반환합니다.

    Args:
        remote_file_path: Hub에서의 파일 경로 (e.g., "data/img/user_id/record_id/image.jpg")

    Returns:
        파일의 바이트 데이터
    """
    _validate_credentials()

    try:
        url = hf_hub_url(
            repo_id=HF_REPO,
            filename=remote_file_path,
            repo_type="dataset"
        )

        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            timeout=(5, 30)
        )
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"ERROR FETCHING FILE {remote_file_path}: {e}")
        raise
