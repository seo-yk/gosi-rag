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
    assert settings.generation_provider == "gemini"
    assert settings.generation_model == "gemini-3.5-flash"
    assert str(settings.index_path) == "index/row/openai/title_body.faiss"


def test_settings_allows_local_provider_without_openai_key() -> None:
    settings = Settings.from_mapping(
        {
            "GEMINI_API_KEY": "gemini-key",
            "EMBEDDING_PROVIDER": "local",
        }
    )

    assert settings.embedding_provider == "local"
    assert settings.embedding_model == "intfloat/multilingual-e5-small"
    assert str(settings.index_path) == "index/row/local/title_body.faiss"


def test_settings_supports_ollama_generation_provider() -> None:
    settings = Settings.from_mapping(
        {
            "GEMINI_API_KEY": "gemini-key",
            "EMBEDDING_PROVIDER": "local",
            "GENERATION_PROVIDER": "ollama",
            "GENERATION_MODEL": "qwen2.5:3b",
        }
    )

    assert settings.generation_provider == "ollama"
    assert settings.generation_model == "qwen2.5:3b"


def test_settings_supports_openai_generation_provider() -> None:
    settings = Settings.from_mapping(
        {
            "OPENAI_API_KEY": "test-openai-key",
            "EMBEDDING_PROVIDER": "local",
            "GENERATION_PROVIDER": "openai",
            "GENERATION_MODEL": "gpt-5.4-mini",
        }
    )

    assert settings.generation_provider == "openai"
    assert settings.generation_model == "gpt-5.4-mini"


def test_settings_rejects_missing_api_keys() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        Settings.from_mapping({"OPENAI_API_KEY": "openai-key"})

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Settings.from_mapping(
            {
                "GEMINI_API_KEY": "gemini-key",
                "GENERATION_PROVIDER": "openai",
            }
        )
