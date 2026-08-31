"""sillok CLI.

지금은 `migrate`(D17)와 `serve`(D8·3단계)다. `ingest` 는 5단계에서 붙는다.
미리 만들지 않는다 — 동작하지 않는 명령이 있으면 계약이 구현된 것처럼 보인다.

**CLI 는 SQL 을 갖지 않는다 (D19).** 여기서 하는 일은 인자를 읽고
sillok.migrations 의 러너를 부르는 것뿐이다.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import config, migrations


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sillok",
        description="Sillok — 저장 위치를 강제하는 지식 원장",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    migrate = sub.add_parser(
        "migrate",
        help="마이그레이션을 적용하고 끝낸다 (D17)",
    )
    migrate.add_argument(
        "--migrations-dir",
        type=Path,
        default=None,
        help=f"기본값: {migrations.DEFAULT_MIGRATIONS_DIR}",
    )

    serve = sub.add_parser("serve", help="FastAPI 를 띄운다 (D6·D16)")
    serve.add_argument("--host", default=None, help="기본값: SILLOK_HOST")
    serve.add_argument("--port", type=int, default=None, help="기본값: SILLOK_PORT")
    serve.add_argument(
        "--skip-migrate",
        action="store_true",
        help="기동 시 마이그레이션을 건너뛴다. D17 이 기본을 정했으므로 진단용이다",
    )
    return parser


def _force_utf8_output() -> None:
    """출력 인코딩을 호스트 로케일에 맡기지 않는다.

    이 도구의 메시지는 한국어다. Windows 콘솔·파이프에서 sys.stdout.encoding 이
    cp949 로 잡히면 로그가 깨져 읽을 수 없다(실측으로 확인). 컨테이너 안은 UTF-8 이므로
    같은 명령이 환경에 따라 다르게 보이는 것을 막는다.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    _force_utf8_output()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _build_parser().parse_args(argv)

    if args.command == "migrate":
        cfg = config.load()
        try:
            applied = migrations.apply(cfg.database_url, args.migrations_dir)
        except migrations.ConnectionFailed as exc:
            # 스택 트레이스 대신 무엇을 어디로 시도했는지 보여준다.
            # 메시지는 러너가 이미 암호를 가려서 만든 것이다.
            print(str(exc), file=sys.stderr)
            return 1
        # "적용" 이 아니라 "실행" 이다. IF NOT EXISTS 라 대부분은 no-op 이고,
        # 러너는 무엇이 실제로 바뀌었는지 모른다. 아는 것보다 더 주장하지 않는다.
        print(f"실행 {len(applied)}건: " + ", ".join(m.name for m in applied))
        return 0

    if args.command == "serve":
        import uvicorn  # 기동 경로에서만 필요하다. migrate 를 무겁게 만들지 않는다.

        from .api import create_app

        cfg = config.load()
        host = args.host or cfg.host
        port = args.port or cfg.port

        # D17: bind 전에 마이그레이션을 적용한다. 여기서 실패하면 뜨지 않는 것이 맞다 —
        # 스키마가 없는 채로 포트를 열면 첫 요청까지 결함이 숨는다.
        if args.skip_migrate:
            print("마이그레이션 건너뜀 (--skip-migrate)", file=sys.stderr)
        else:
            try:
                applied = migrations.apply(cfg.database_url)
            except migrations.ConnectionFailed as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(f"마이그레이션 {len(applied)}건 실행", file=sys.stderr)

        uvicorn.run(create_app(cfg), host=host, port=port, log_level="info")
        return 0

    raise AssertionError(f"처리되지 않은 명령: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
