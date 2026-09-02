"""sillok CLI.

`migrate`(D17) · `serve`(D8·3단계) · `ingest`(D8·5단계) · `mcp`(D45·8단계) 넷이다.
Q6·Q7·Q10 이 D30–D32 로 닫히기 전까지 `ingest` 는 만들지 않았다 —
동작하지 않는 명령이 있으면 계약이 구현된 것처럼 보인다.

**CLI 는 SQL 을 갖지 않는다 (D19).** 여기서 하는 일은 인자를 읽고
sillok.migrations 의 러너나 sillok.service 의 함수를 부르는 것뿐이다.
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
    # D19 가 정한 인자만 둔다. 편의 플래그를 발명하지 않는다 —
    # --skip-migrate 는 D17("bind 전에 적용")을 끄는 스위치라 계약 밖이었다.
    serve.add_argument("--host", default=None, help="기본값: SILLOK_HOST")
    serve.add_argument("--port", type=int, default=None, help="기본값: SILLOK_PORT")

    ingest = sub.add_parser("ingest", help="D9 경로를 색인한다 (D8·D30–D32)")
    # D19 가 정한 인자만 둔다. --paths·--since·--commit-sha 를 만들지 않는다 —
    # 부분 목록에서는 삭제 판정이 성립하지 않는다 (D30).
    ingest.add_argument("--project", required=True, help="색인 대상 project (D5)")
    # SILLOK_WORKSPACE 와 **같은 나무**여야 한다 (D37). 다르면 거절한다 —
    # 저쪽을 색인해 두면 get_file 이 이 나무를 저쪽의 path 로 연다.
    ingest.add_argument("--workspace", default=None, help="기본값: SILLOK_WORKSPACE (달라선 안 된다)")

    # D45. 편의 플래그가 아니라 D6 이 요구한 두 전송 중 하나다.
    # serve 에 --stdio 를 붙이지 않는다 — 한 명령이 stdout 의 의미를 바꾸게 된다.
    sub.add_parser("mcp", help="MCP 도구를 stdio 로 연다 (D6·D45)")
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
    # stream 을 못 박는다. 기본값도 stderr 이지만, `mcp` 의 stdout 은 프로토콜 채널이라
    # 로그가 한 줄이라도 그리로 가면 클라이언트가 JSON-RPC 를 못 읽는다 (D45).
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
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
        try:
            applied = migrations.apply(cfg.database_url)
        except migrations.ConnectionFailed as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"마이그레이션 {len(applied)}건 실행", file=sys.stderr)

        uvicorn.run(create_app(cfg), host=host, port=port, log_level="info")
        return 0

    if args.command == "ingest":
        from . import service

        cfg = config.load()
        try:
            # D37: SILLOK_WORKSPACE 와 다른 나무는 거절한다. 거절은 CLI 에서 끝난다 —
            # VALIDATION 은 HTTP 표면의 코드이고(D21), 여기서는 종료 코드와 문구다.
            run = service.ingest(
                cfg.database_url,
                args.project,
                service.resolve_workspace(args.workspace, cfg.workspace),
                cfg.openai_api_key,
            )
        except service.IngestLocked as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except service.ValidationFailed as exc:
            print(str(exc), file=sys.stderr)
            return 1

        # 러너와 같은 어투다 — 아는 것보다 더 주장하지 않는다.
        print(
            f"run {run['run_id']} {run['status']}: "
            f"본 {run['files_seen']} · 바뀐 {run['files_changed']} · 지운 {run['files_deleted']} · "
            f"청크 {run['chunks_upserted']} · 임베딩 {run['chunks_embedded']} · "
            f"남은 벡터 {run['chunks_pending']}"
        )
        for item in run["skipped"]:
            print(f"  건너뜀 {item['path']} ({item['reason']})", file=sys.stderr)
        if run["status"] != "ok":
            print(run["error"] or run["status"], file=sys.stderr)
        # ok 에만 0 이다. partial·failed·락 거절은 1 이고, 셋의 구분은
        # 종료 코드가 아니라 stderr 문구와 run 행이 한다 (D32).
        return 0 if run["status"] == "ok" else 1

    if args.command == "mcp":
        import anyio

        from . import mcp_server

        cfg = config.load()

        # D17 과 같은 이유로 먼저 적용한다 — 스키마 없이 도구를 여는 것은 같은 상태다.
        # **보고는 stderr 로만 간다.** stdout 은 JSON-RPC 채널이다 (D45).
        try:
            applied = migrations.apply(cfg.database_url)
        except migrations.ConnectionFailed as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"마이그레이션 {len(applied)}건 실행", file=sys.stderr)

        anyio.run(mcp_server.build(cfg).run_stdio_async)
        return 0

    raise AssertionError(f"처리되지 않은 명령: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
