"""평가셋 v1.3(JSONL) 로더와 그룹 채점 함수

형식은 evaluation/evalset/README.md 참고.
- required_faqs: 바깥 목록은 AND(모든 그룹 필요), 안쪽 목록은 OR(그룹 안 FAQ 하나면 충분)
- supporting_faqs: 어떤 지표에도 쓰지 않는다
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

Groups = tuple[tuple[int, ...], ...]


@dataclass(frozen=True, slots=True)
class EvalQuestion:
    """본 평가셋 문항 한 건"""

    id: int
    question: str
    intent: str
    type: str
    required_faqs: Groups
    supporting_faqs: tuple[int, ...]
    reference_answer: str
    written_by: str = ""  # 본인 / Claude (편향 점검용)

    @property
    def is_single(self) -> bool:
        """필수 그룹이 1개인 문항(MRR 대상)"""
        return len(self.required_faqs) == 1


@dataclass(frozen=True, slots=True)
class OutOfScopeQuestion:
    """범위 밖 문항 한 건"""

    id: int
    question: str
    difficulty: str
    similar_faqs: tuple[int, ...]


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def read_evalset(path: Path) -> list[EvalQuestion]:
    """본 평가셋에서 status=keep 문항만 로드"""
    questions = []
    for row in _read_jsonl(path):
        if row["status"] != "keep":
            continue
        groups = tuple(tuple(int(faq_id) for faq_id in group) for group in row["required_faqs"])
        if not groups or any(not group for group in groups):
            raise ValueError(f"{row['id']}: 빈 필수 그룹")
        questions.append(
            EvalQuestion(
                id=int(row["id"]),
                question=row["question"].strip(),
                intent=row["intent"].strip(),
                type=row["type"],
                required_faqs=groups,
                supporting_faqs=tuple(row["supporting_faqs"]),
                reference_answer=row["reference_answer"].strip(),
                written_by=row.get("written_by", ""),
            )
        )
    if not questions:
        raise ValueError(f"평가할 문항이 없습니다: {path}")
    return questions


def read_out_of_scope(path: Path) -> list[OutOfScopeQuestion]:
    """범위 밖 문항에서 status=keep 문항만 로드"""
    return [
        OutOfScopeQuestion(
            id=int(row["id"]),
            question=row["question"].strip(),
            difficulty=row["difficulty"],
            similar_faqs=tuple(row["similar_faqs"]),
        )
        for row in _read_jsonl(path)
        if row["status"] == "keep"
    ]


def format_groups(groups: Groups) -> str:
    """필수 FAQ를 사람이 읽는 문자열로 표기. 예: [[78], [272, 251]] → '78 & 272|251'"""
    return " & ".join("|".join(str(faq_id) for faq_id in group) for group in groups)


def satisfied_groups(groups: Groups, retrieved_ids: Sequence[int], k: int) -> int:
    """Top-K 안에 FAQ가 1개 이상 들어온 그룹 수"""
    top_k = set(retrieved_ids[:k])
    return sum(1 for group in groups if top_k.intersection(group))


def is_hit(groups: Groups, retrieved_ids: Sequence[int], k: int) -> bool:
    """모든 그룹이 Top-K 안에서 충족되면 적중"""
    return satisfied_groups(groups, retrieved_ids, k) == len(groups)


def group_recall(groups: Groups, retrieved_ids: Sequence[int], k: int) -> float:
    """충족된 그룹 수 ÷ 전체 그룹 수"""
    return satisfied_groups(groups, retrieved_ids, k) / len(groups)


def reciprocal_rank(groups: Groups, retrieved_ids: Sequence[int]) -> float:
    """단일 그룹 문항의 역순위: 그룹 내 FAQ 중 가장 높은 순위의 역수. 없으면 0"""
    if len(groups) != 1:
        raise ValueError("MRR은 필수 그룹이 1개인 문항에만 계산합니다.")
    for rank, faq_id in enumerate(retrieved_ids, 1):
        if faq_id in groups[0]:
            return 1 / rank
    return 0.0
