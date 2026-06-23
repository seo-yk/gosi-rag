import pytest

from app import Settings


def test_settings_reads_required_keys_and_defaults() -> None:
    settings = Settings.from_mapping(
        {
            "OPENAI_API_KEY": "openai-key",
            "GEMINI_API_KEY": "gemini-key",
        }
    )

    assert settings.embedding_provider == "openai"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.gemini_model == "gemini-3.5-flash"
    assert str(settings.index_path) == "index/row/openai/title_body.faiss"


def test_settings_allows_local_provider_without_openai_key() -> None:
    settings = Settings.from_mapping(
        {
            "GEMINI_API_KEY": "gemini-key",
            "FAQ_EMBEDDING_PROVIDER": "local",
        }
    )

    assert settings.embedding_provider == "local"
    assert settings.embedding_model == "intfloat/multilingual-e5-small"
    assert str(settings.index_path) == "index/row/local/title_body.faiss"


def test_settings_rejects_missing_api_keys() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        Settings.from_mapping({"OPENAI_API_KEY": "openai-key"})
