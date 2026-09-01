"""6단계 검색의 순수 로직 (D33).

DB 가 필요 없다. 병합·문서당 상한·정렬은 SQL 을 모르는 자리에 있어야
이 검사들이 싸게 돈다 — `ingest.py` 와 같은 갈래다 (D19).
"""

from __future__ import annotations

from sillok import search


def r(key, doc, rank):
    return search.Ranked(key, doc, rank, {"k": key})


# --- RRF (D33 §2) -----------------------------------------------------------


def test_a_row_in_both_lists_scores_higher_than_one_in_either():
    both = r(("", "a", 0), "a", 1)
    only = r(("", "b", 0), "b", 1)
    merged = search.rrf([both, only], [both])
    assert merged[both.key]["score"] > merged[only.key]["score"]


def test_a_missing_list_contributes_nothing():
    """벡터가 없는 청크는 "꼴찌"가 아니라 그 목록에 없다.

    없는 것에 순위를 매기면 임베딩이 채워지지 않은 문서가 조직적으로 밀리거나 앞선다.
    """
    only_keyword = search.rrf([r(("", "a", 0), "a", 1)], [])
    assert only_keyword[("", "a", 0)]["score"] == 1.0 / (search.RRF_K + 1)


def test_one_list_is_a_monotone_restatement_of_its_rank():
    """키가 없으면(D2) 벡터 목록이 비고 순서는 키워드 순서와 같다. 분기를 만들지 않는다."""
    items = [r(("", chr(97 + i), 0), chr(97 + i), i + 1) for i in range(5)]
    merged = search.rrf(items, [])
    got = [k for k in search.cap_per_document(merged)]
    assert got == [i.key for i in items]


def test_ties_in_a_list_get_the_same_contribution():
    """`rank()` 는 동점을 동점으로 남긴다 — 정렬 타이브레이크가 점수로 새면 안 된다."""
    merged = search.rrf([r(("", "a", 0), "a", 3), r(("", "b", 0), "b", 3)], [])
    assert merged[("", "a", 0)]["score"] == merged[("", "b", 0)]["score"]


# --- 문서당 상한 (D33 §6) ----------------------------------------------------


def test_one_document_takes_at_most_two_rows():
    """상한이 없으면 가장 긴 문서가 칸을 다 가져간다. 결과는 가득 차 있어 정상으로 보인다."""
    merged = search.rrf([r(("", "big.md", i), "big.md", i + 1) for i in range(5)], [])
    assert len(search.cap_per_document(merged)) == 2


def test_the_cap_does_not_refill_from_other_documents():
    """메우면 `top_k` 가 늘 가득 차 상한이 도는지 아무도 모른다."""
    items = [r(("", "big.md", i), "big.md", i + 1) for i in range(5)]
    items.append(r(("", "small.md", 0), "small.md", 6))
    got = search.order_and_cut(search.rrf(items, []), 8)
    assert len(got) == 3  # big 둘 + small 하나. 여덟을 요청해도 셋이다


def test_the_cap_keeps_the_best_two_of_a_document():
    items = [r(("", "d.md", i), "d.md", 10 - i) for i in range(5)]
    kept = search.cap_per_document(search.rrf(items, []))
    assert [k[2] for k in kept] == [4, 3]  # rank 6, 7 이 가장 높다


# --- 순서 (D33 §7) ----------------------------------------------------------


def test_ties_are_broken_by_the_key_not_by_insertion_order():
    """최종 정렬이 총순서가 아니면 같은 질의가 실행마다 다른 행을 자른다."""
    items = [r(("", "z.md", 0), "z.md", 1), r(("", "a.md", 0), "a.md", 1)]
    assert search.cap_per_document(search.rrf(items, []))[0] == ("", "a.md", 0)
    # 넣는 순서를 뒤집어도 같다
    assert search.cap_per_document(search.rrf(list(reversed(items)), []))[0] == ("", "a.md", 0)


def test_top_k_8_is_the_first_eight_of_top_k_12():
    """상한은 `LIMIT` 앞에 적용한다. 그래야 `top_k` 가 길이만 바꾸고 내용을 바꾸지 않는다."""
    items = [r(("", f"d{i}.md", 0), f"d{i}.md", i + 1) for i in range(12)]
    merged = lambda: search.rrf(items, [])  # noqa: E731
    eight = [x["k"] for x in search.order_and_cut(merged(), 8)]
    twelve = [x["k"] for x in search.order_and_cut(merged(), 12)]
    assert twelve[:8] == eight


def test_score_is_the_rrf_value_not_a_normalized_one():
    """정규화하면 1위가 언제나 만점이라 아무것도 안 맞은 질의가 확신처럼 읽힌다."""
    got = search.order_and_cut(search.rrf([r(("", "a", 0), "a", 1)], []), 8)
    assert got[0]["score"] == round(1.0 / (search.RRF_K + 1), search.SCORE_DIGITS)
    assert got[0]["score"] != 1.0


# --- excerpt (D33 §8) -------------------------------------------------------


def test_short_excerpt_is_untouched():
    assert search.clip_excerpt("가나다") == "가나다"
    assert search.clip_excerpt("x" * search.EXCERPT_MAX) == "x" * search.EXCERPT_MAX


def test_long_excerpt_is_clipped_and_marked():
    """붙이지 않으면 절단과 청크의 끝을 구분할 수 없다."""
    got = search.clip_excerpt("x" * (search.EXCERPT_MAX + 50))
    assert len(got) == search.EXCERPT_MAX
    assert got.endswith(search.ELLIPSIS)
    assert got[:-1] == "x" * (search.EXCERPT_MAX - 1)


def test_the_ellipsis_is_exactly_one_character():
    """API 가 넣는 유일한 문자다. 빈 결과에 문장을 넣지 않는 금지와 다르다."""
    assert len(search.ELLIPSIS) == 1
