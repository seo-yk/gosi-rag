"""프로젝트 공통 환경 설정 로딩."""

import os

from dotenv import load_dotenv


def load_project_env() -> None:
    """환경 변수 파일 우선순위 로드"""
    env_file = os.environ.get("FAQ_ENV_FILE", "").strip()
    if env_file:
        load_dotenv(env_file, override=True)
        return
    # Default to loading the unified .env file, allowing local overrides via .env.local
    load_dotenv(".env", override=True)
    load_dotenv(".env.local", override=True)
