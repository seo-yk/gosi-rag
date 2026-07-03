import os

from src.config import load_project_env


def test_load_project_env_prefers_explicit_env_file(tmp_path, monkeypatch) -> None:
    explicit = tmp_path / ".env.explicit"
    explicit.write_text("EMBEDDING_PROVIDER=local\n", encoding="utf-8")
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.setenv("ENV_FILE", str(explicit))

    load_project_env()

    assert os.environ["EMBEDDING_PROVIDER"] == "local"
