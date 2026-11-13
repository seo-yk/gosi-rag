import csv
from pathlib import Path

from evaluation.scripts.evaluate_generation import GeneratedAnswerRow
from evaluation.scripts.generate_answers import output_fieldnames as generation_fields
from evaluation.scripts.judge_answers import (
    JudgeScores,
    build_prompt,
    format_groups,
    judge_answers,
    judge_one,
    parse_groups,
    parse_judge_json,
)


def item(required: str = "78 & 272|251", answer: str = "답") -> GeneratedAnswerRow:
    return GeneratedAnswerRow("52", "질문", "복수근거", "", required, "기준 답변", "", "", "gpt", "78|272",
                              "[FAQ 78]\n제목: A\n본문: B", answer, "retrieval: bge-m3")


class FakeJudge:
    model = "fake-judge"

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.prompts = []

    def complete(self, prompt, group_count=None):
        self.prompts.append(prompt)
        return self.outputs.pop(0)


def test_parse_groups_and_format_with_titles() -> None:
    groups = parse_groups("78 & 272|251")

    assert groups == [[78], [272, 251]]
    assert format_groups(groups, {78: "[신분증]", 272: "[응시표]"}) == (
        "Group 1: FAQ 78 [신분증]\nGroup 2: FAQ 272 [응시표] OR FAQ 251"
    )


def test_prompt_contains_all_inputs_without_placeholders() -> None:
    prompt = build_prompt(item(answer="생성 답변"), "Group 1: FAQ 78")

    for text in ("질문", "기준 답변", "Group 1: FAQ 78", "[FAQ 78]", "생성 답변"):
        assert text in prompt
    assert "<<" not in prompt


def test_verdict_requires_full_grounding_coverage_and_no_refusal() -> None:
    assert JudgeScores(2, 1, (1, 1), 0, "").verdict == "pass"
    assert JudgeScores(1, 1, (1, 1), 0, "").verdict == "fail"   # 근거 없는 세부 내용
    assert JudgeScores(2, 1, (1, 0), 0, "").verdict == "fail"   # 그룹 하나 누락
    assert JudgeScores(2, 1, (1, 0), 0, "").completeness == 0
    assert JudgeScores(2, 0, (1, 1), 1, "").verdict == "fail"   # 근거 있는데 회피


def test_parse_judge_json_validates_shape() -> None:
    ok = '설명 {"reason": "r", "groundedness": 2, "correctness": 1, "groups_covered": [1, 0], "unjustified_refusal": 0}'

    assert parse_judge_json(ok, 2) == JudgeScores(2, 1, (1, 0), 0, "r")
    assert parse_judge_json(ok, 1) is None                       # 그룹 수 불일치
    assert parse_judge_json(ok.replace('"groundedness": 2', '"groundedness": 5'), 2) is None
    assert parse_judge_json("JSON 아님", 2) is None


def test_judge_one_retries_then_gives_up() -> None:
    good = '{"reason": "", "groundedness": 2, "correctness": 1, "groups_covered": [1, 1], "unjustified_refusal": 0}'

    assert judge_one(FakeJudge(["x", good]), item(), {}).verdict == "pass"
    assert judge_one(FakeJudge(["x", "y", "z"]), item(), {}) is None


def test_judge_answers_skips_out_of_scope_and_resumes(tmp_path: Path) -> None:
    answers = tmp_path / "answers.csv"
    with answers.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=generation_fields())
        writer.writeheader()
        for qid, qtype in (("1", "일상표현"), ("2", "일상표현"), ("154", "범위 밖")):
            writer.writerow({k: "" for k in generation_fields()} | {"id": qid, "type": qtype, "required_faqs": "5", "answer": "a"})
    faq = tmp_path / "faq.csv"
    faq.write_text("연번,제목,본문\n5,제목,본문\n", encoding="utf-8")
    output = tmp_path / "judged.csv"
    good = '{"reason": "", "groundedness": 2, "correctness": 1, "groups_covered": [1], "unjustified_refusal": 0}'

    judge_answers(answers, output, FakeJudge([good]), faq_path=faq, only_ids={"1"})
    judge_answers(answers, output, FakeJudge([good]), faq_path=faq)  # 1은 건너뛰고 2만, 154(범위 밖)는 제외

    rows = list(csv.DictReader(output.open(encoding="utf-8-sig")))
    assert [r["id"] for r in rows] == ["1", "2"]
    assert rows[0]["verdict"] == "pass"
    assert rows[0]["judge_model"] == "fake-judge (rubric v2.1)"
