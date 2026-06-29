from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_project_uses_civil_service_exam_dataset_name() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")

    assert 'st.title("국가공무원 채용시험 FAQ RAG")' in app


def test_project_uses_simple_source_structure() -> None:
    source_files = {path.name for path in (ROOT / "src").glob("*.py")}

    assert source_files == {"indexing.py", "retrieval.py", "generation.py", "config.py"}
    assert not (ROOT / "scripts").exists()
    assert not (ROOT / "pyproject.toml").exists()
    assert (ROOT / "requirements.txt").exists()
