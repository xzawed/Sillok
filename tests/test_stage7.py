"""7단계에서 DB 없이 판정되는 것 (D36 · D37 · D38 · D40 · D41).

요청 검증은 **DB 에 닿기 전에** 끝나야 한다. 그래야 죽은 DSN 으로도 같은 답이 나오고,
클라이언트 입력 문제가 `INTERNAL` 로 둔갑하지 않는다 (D21).
"""

from __future__ import annotations

import pytest

from sillok import service

DEAD_DSN = "postgresql://sillok:x@127.0.0.1:1/sillok"


# --- base_hash 의 와이어 형식 (D40) ------------------------------------------


def test_base_hash_accepts_only_the_documented_form():
    digest = "a" * 64
    assert service._require_base_hash(f"sha256:{digest}") == digest


def test_missing_base_hash_is_not_checked():
    """모르고 보낸 것과 알고 덮어쓰는 것은 다르다 (D38)."""
    assert service._require_base_hash(None) is None


@pytest.mark.parametrize(
    "bad",
    [
        "a" * 64,  # 접두사 없는 16진 — 관대하게 받지 않는다
        "sha256:" + "A" * 64,  # 대문자
        "sha256:" + "a" * 63,  # 짧다
        "sha1:" + "a" * 64,
        "sha256:",
        f" sha256:{'a' * 64}",
        123,
    ],
)
def test_other_base_hash_shapes_are_validation(bad):
    """접두사를 벗기거나 붙여 주면 "무엇이 같은 해시인가" 라는 두 번째 규칙이 생긴다 (D40)."""
    with pytest.raises(service.ValidationFailed):
        service._require_base_hash(bad)


# --- offset 과 path (D36) ----------------------------------------------------


@pytest.mark.parametrize("bad", [-1, "0", 1.0, True, None])
def test_offset_must_be_a_non_negative_integer(bad):
    with pytest.raises(service.ValidationFailed):
        service._require_offset(bad)


def test_offset_defaults_are_integers():
    assert service._require_offset(0) == 0
    assert service._require_offset(4000) == 4000


@pytest.mark.parametrize("path", ["", "docs/plan.md/", "docs//plan.md", "./docs/plan.md"])
def test_path_is_not_normalized(path):
    """정규화 대상이 아니라 **그냥 행이 없는 것**이다 (D36).

    여기서 다듬으면 허용 목록을 느슨하게 만드는 손잡이가 생긴다.
    """
    assert service._require_path(path) == path


# --- diff (D38 · D41) --------------------------------------------------------


def test_identical_body_makes_an_empty_diff():
    """바꿀 것이 없다는 답이지 오류가 아니다 — 오류로 만들면 모델이 같은 제안을 반복한다."""
    assert service._unified_diff("docs/a.md", "본문\n", "본문\n") == ""


def test_diff_names_both_sides():
    diff = service._unified_diff("docs/a.md", "옛 줄\n", "새 줄\n")
    assert diff.startswith("--- a/docs/a.md\n+++ b/docs/a.md\n")
    assert "-옛 줄" in diff and "+새 줄" in diff


def test_missing_file_diffs_from_dev_null():
    """행은 있는데 파일이 없으면 빈 내용이 아니라 **부재**다 (D41)."""
    diff = service._unified_diff("docs/a.md", None, "새 본문\n")
    assert diff.startswith("--- /dev/null\n+++ b/docs/a.md\n")
    assert "+새 본문" in diff


def test_trailing_newline_only_change_is_still_a_diff():
    """줄 끝만 달라도 다른 본문이다. 여기서 접으면 제안이 조용히 사라진다."""
    assert service._unified_diff("docs/a.md", "본문\n", "본문") != ""


# --- D37 workspace 거절 -------------------------------------------------------


def test_absent_workspace_falls_back_to_the_configured_one(tmp_path):
    for absent in (None, ""):
        assert service.resolve_workspace(absent, str(tmp_path)) == str(tmp_path)


def test_the_same_tree_spelled_differently_is_accepted(tmp_path, monkeypatch):
    """`.` 과 절대 경로가 같은 곳을 가리켜도 문자열은 다르다 (D37)."""
    monkeypatch.chdir(tmp_path)
    assert service.resolve_workspace(".", str(tmp_path)) == str(tmp_path)
    assert service.resolve_workspace(str(tmp_path), ".") == "."


def test_a_different_tree_is_refused(tmp_path):
    """저쪽 나무를 색인해 두면 `get_file` 이 **이 나무**를 저쪽의 path 로 연다 (D37)."""
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(service.ValidationFailed) as exc:
        service.resolve_workspace(str(other), str(tmp_path))
    assert "SILLOK_WORKSPACE" in str(exc.value)


def test_the_refusal_does_not_echo_the_configured_path(tmp_path):
    """거절 문구는 요청자가 이미 아는 값만 담는다 — 서버 쪽 경로를 흘리지 않는다."""
    configured = tmp_path / "server-side-secret-name"
    configured.mkdir()
    requested = tmp_path / "asked"
    requested.mkdir()
    with pytest.raises(service.ValidationFailed) as exc:
        service.resolve_workspace(str(requested), str(configured))
    assert "server-side-secret-name" not in str(exc.value)


def test_non_string_workspace_is_validation(tmp_path):
    with pytest.raises(service.ValidationFailed):
        service.resolve_workspace(7, str(tmp_path))


# --- 검증이 DB 보다 먼저다 ----------------------------------------------------


def test_get_file_validates_before_touching_the_db():
    """죽은 DSN 으로도 VALIDATION 이다. DB 를 먼저 만지면 이것이 INTERNAL 로 나간다."""
    with pytest.raises(service.ValidationFailed):
        service.get_file(DEAD_DSN, "sillok", "docs/plan.md", -1, ".")
    with pytest.raises(service.ValidationFailed):
        service.get_file(DEAD_DSN, "", "docs/plan.md", 0, ".")


def test_save_doc_validates_before_touching_the_db():
    with pytest.raises(service.ValidationFailed):
        service.save_doc(DEAD_DSN, {"project": "sillok", "path": "docs/plan.md"}, ".")
    with pytest.raises(service.ValidationFailed):
        service.save_doc(
            DEAD_DSN,
            {"project": "sillok", "path": "docs/plan.md", "body": "새 본문", "base_hash": "sha256:x"},
            ".",
        )


def test_get_event_validates_before_touching_the_db():
    with pytest.raises(service.ValidationFailed):
        service.get_event(DEAD_DSN, 1, "has/slash")


def test_event_response_leaves_out_derived_columns():
    """D39: `tsv` 는 생성 컬럼이고 `embedding` 은 v1 이 채우지 않는다 (D34)."""
    assert "tsv" not in service.EVENT_FIELDS
    assert "embedding" not in service.EVENT_FIELDS
    # 저장 계약의 필드는 하나도 빠지지 않는다 — 원문을 보라고 만든 표면이다.
    for field in service.REQUIRED_FIELDS:
        assert field in service.EVENT_FIELDS
    for field in ("root_cause", "resolution", "payload", "created_by", "id", "created_at"):
        assert field in service.EVENT_FIELDS
