import csv
from pathlib import Path

import pytest

from evaluation.scripts.build_retrieval_comparison import build, read_rows

SUBSETS = ["전체", "단일 그룹 전체", "유형: 원문유사", "작성: 본인"]


def write_summary(path: Path, model: str, sha: str = "abc") -> None:
    fields = ["eval_set", "source_csv", "source_sha256", "depth", "embedding_model", "chunking_mode",
              "embedding_mode", "subset", "questions", "hit_at_1", "hit_at_3", "hit_at_5",
              "group_recall_at_3", "mrr_single"]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for chunking, embedding in (("sentence", "title_body"), ("row", "title")):
            for subset in SUBSETS:
                writer.writerow({
                    "eval_set": "evalset_v1.3", "source_csv": "data/faq_v2.csv", "source_sha256": sha, "depth": 5,
                    "embedding_model": model, "chunking_mode": chunking, "embedding_mode": embedding,
                    "subset": subset, "questions": 148, "hit_at_1": 0.5, "hit_at_3": 0.75, "hit_at_5": 0.9,
                    "group_recall_at_3": 0.8, "mrr_single": 0.6,
                })


def test_build_orders_combinations_and_formats_percent(tmp_path: Path) -> None:
    write_summary(tmp_path / "a.csv", "model-a")
    write_summary(tmp_path / "b.csv", "model-b")

    table, markdown = build(read_rows([tmp_path / "a.csv", tmp_path / "b.csv"]))

    assert [(r["embedding_model"], r["chunking_mode"]) for r in table] == [
        ("model-a", "row"), ("model-a", "sentence"), ("model-b", "row"), ("model-b", "sentence"),
    ]
    assert "| model-a | row | title | 50.0% | 50.0% | 75.0% | 90.0% | 80.0% | 0.600 |" in markdown
    assert table[0]["hit_at_3 [유형: 원문유사]"] == "0.75"
    assert table[0]["hit_at_3 [유형: 조건형]"] == ""


def test_read_rows_rejects_mixed_source_data(tmp_path: Path) -> None:
    write_summary(tmp_path / "a.csv", "model-a", sha="abc")
    write_summary(tmp_path / "b.csv", "model-b", sha="xyz")

    with pytest.raises(SystemExit, match="source_sha256"):
        read_rows([tmp_path / "a.csv", tmp_path / "b.csv"])
