"""6단계 검색의 순수 로직 (D33).

**여기에는 DB 가 없다.** 두 순위를 RRF 로 합치고, 문서당 상한을 걸고, 최종 순서를 정하는
것까지가 이 모듈이다. SQL 은 `service.py` 에만 있다 (D19). `ingest.py` 와 같은 갈래이고
이유도 같다 — 검사가 싸다.

검색은 틀려도 예외를 던지지 않는다. 병합이 틀리면 결과가 조금 덜 맞을 뿐이고 응답은 200 이다.
그래서 규칙 하나하나가 검사로 잠겨야 한다.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- D33 이 못 박은 값 ------------------------------------------------------
# 정본은 adr/0001-v1-stack-decisions.md §D33 이다. 여기서 바꾸지 않는다.

RRF_K = 60
CANDIDATE_POOL = 60          # 팔마다 고정. top_k 에 비례시키지 않는다
PER_DOCUMENT_CAP = 2
TOP_K_DEFAULT = 8
TOP_K_MAX = 12
EXCERPT_MAX = 800
ELLIPSIS = "…"
SCORE_DIGITS = 6


@dataclass(frozen=True)
class Ranked:
    """한 팔이 돌려준 한 행. `rank` 는 그 팔의 완결된 정렬 위의 `rank()` 다."""

    key: tuple            # 최종 정렬 키. 문서는 (repo, path, chunk_idx), 이벤트는 (…, id)
    doc: object           # 문서당 상한을 셀 단위. 이벤트에서는 None
    rank: int
    row: dict


def rrf(*lists: list[Ranked]) -> dict:
    """순위만 합친다. 점수는 섞지 않는다.

    **없는 목록의 항은 더하지 않는다.** 벡터가 없는 청크는 "꼴찌"가 아니라 그 목록에 없다 —
    없는 것에 순위를 매기면 임베딩이 채워지지 않은 문서가 조직적으로 밀리거나 앞선다.

    덧셈 순서를 고정한다. 정하지 않으면 같은 입력이 마지막 자리에서 다른 값을 낼 수 있고
    그 차이가 동점 판정을 바꾼다 — **키워드 항을 먼저 더한다** (호출자가 그 순서로 넘긴다).
    """
    merged: dict = {}
    for ranked in lists:
        for item in ranked:
            slot = merged.get(item.key)
            if slot is None:
                slot = merged[item.key] = {"score": 0.0, "doc": item.doc, "row": item.row}
            slot["score"] += 1.0 / (RRF_K + item.rank)
    return merged


def cap_per_document(merged: dict) -> list[tuple]:
    """한 문서는 최대 두 행이다 (D33 §6).

    **상한은 `LIMIT` 앞에 적용한다.** 그래야 `top_k=8` 의 결과가 `top_k=12` 결과의 앞 여덟 줄이 된다.
    **버린 행을 다른 문서로 메우지 않는다** — 메우면 `top_k` 가 늘 가득 차 상한이 도는지 아무도 모른다.
    """
    seen: dict = {}
    kept: list[tuple] = []
    for key in sorted(merged, key=lambda k: (-merged[k]["score"], k)):
        doc = merged[key]["doc"]
        if doc is not None:
            n = seen.get(doc, 0)
            if n >= PER_DOCUMENT_CAP:
                continue
            seen[doc] = n + 1
        kept.append(key)
    return kept


def order_and_cut(merged: dict, top_k: int) -> list[dict]:
    """최종 정렬은 `score DESC` 다음에 키다 — 한 project 안의 총순서다.

    같은 입력에 같은 여덟 줄이 나온다. 순서가 실행마다 달라지면
    9단계의 `kb_query_logs` 가 무엇의 기록도 아니게 된다.
    """
    out: list[dict] = []
    for key in cap_per_document(merged)[:top_k]:
        slot = merged[key]
        row = dict(slot["row"])
        # 자릿수는 표시 안정성 때문이고, 정렬은 반올림 전 값으로 이미 끝났다.
        row["score"] = round(slot["score"], SCORE_DIGITS)
        out.append(row)
    return out


def clip_excerpt(text: str) -> str:
    """800자에서 자르고, 잘렸으면 말줄임표 한 글자를 붙인다 (D33 §8).

    붙이지 않으면 절단과 청크의 끝을 구분할 수 없다.
    **그 한 글자가 API 가 넣는 유일한 문자다** — 빈 결과에 문장을 넣지 않는 금지와 다르다.
    """
    if text is None:
        return ""
    if len(text) <= EXCERPT_MAX:
        return text
    return text[: EXCERPT_MAX - 1] + ELLIPSIS
