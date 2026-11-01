"""CLI：`python -m radar`（跑一次，打印）或 `python -m radar serve`（起页面）。"""

from __future__ import annotations

import argparse
import asyncio
import json


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="radar")
    parser.add_argument("cmd", nargs="?", default="run", choices=["run", "serve"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "serve":
        from .config import load

        cfg = load()
        import uvicorn

        print(f"{cfg.name} · http://127.0.0.1:{cfg.port}")
        uvicorn.run(
            "radar.app:app", host="127.0.0.1", port=cfg.port,
            log_level="warning", access_log=False,
        )
        return

    from .config import load
    from .pipeline import collect

    items = asyncio.run(collect(load()))
    for it in items:
        print(f"[{it.source}] {it.title}")
        print(f"    {it.url}")
        print(f"    命中：{'、'.join(it.matched)} · {it.summary[:80]}\n")
    if args.json:
        print(json.dumps([it.to_dict() for it in items], ensure_ascii=False, indent=2))
    print(f"共 {len(items)} 条")


if __name__ == "__main__":
    main()
