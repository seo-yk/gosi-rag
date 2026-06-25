import os

from src.config import load_project_env


def test_load_project_env_prefers_explicit_env_file(tmp_path, monkeypatch) -> None:
    explicit = tmp_path / ".env.explicit"
    explicit.write_text("FAQ_EMBEDDING_PROVIDER=local\n", encoding="utf-8")
    monkeypatch.delenv("FAQ_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.setenv("FAQ_ENV_FILE", str(explicit))

    load_project_env()

    assert os.environ["FAQ_EMBEDDING_PROVIDER"] == "local"
