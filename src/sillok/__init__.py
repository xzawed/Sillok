"""Sillok — 저장 위치를 강제하는 지식 원장.

계약은 코드가 아니라 문서에 있다. docs/plan.md 와 adr/0001-v1-stack-decisions.md 가
정본이고, 동작이 그것과 다르면 코드가 틀린 것으로 본다.
"""

from importlib.metadata import version as _metadata_version

__all__ = ["__version__"]

# 버전의 정본은 pyproject.toml 이다. 여기에 문자열을 박으면 사본이 되고,
# 사본은 한쪽만 올리는 순간 거짓이 된다 — 설치된 패키지 메타데이터에서 읽는다.
# 기본값을 두지 않는다: 메타데이터가 없으면 설치가 깨진 것이므로 시끄럽게 죽는 편이 낫다.
__version__ = _metadata_version("sillok")
