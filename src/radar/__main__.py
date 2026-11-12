"""CLI：run（抓取+打印）/ ingest（抓取+入库）/ serve（起页面）/ stats（看库）。"""

from __future__ import annotations

import argparse
import asyncio
import json


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="radar")
    parser.add_argument("cmd", nargs="?", default="run",
                        choices=["run", "ingest", "serve", "profile", "stats"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd in ("serve", "profile"):
        from .config import load

        cfg = load()
        import uvicorn

        if args.cmd == "profile":
            print(f"{cfg.name} · 画像 · http://127.0.0.1:{cfg.profile_port}")
            uvicorn.run(
                "radar.profile_app:app", host="127.0.0.1", port=cfg.profile_port,
                log_level="warning", access_log=False,
            )
            return

        print(f"{cfg.name} · http://127.0.0.1:{cfg.port}")
        uvicorn.run(
            "radar.app:app", host="127.0.0.1", port=cfg.port,
            log_level="warning", access_log=False,
        )
        return

    from .config import load
    from .pipeline import ingest, local_day
    from .storage import Store

    cfg = load()
    store = Store(cfg.db_path)

    if args.cmd == "stats":
        print(json.dumps(
            {"stats": store.stats(), "last_run": store.last_run()},
            ensure_ascii=False, indent=2,
        ))
        return

    info = asyncio.run(ingest(cfg, store))
    print(f"抓取 {info['fetched']} 条，入榜 {info['kept']} 条（{info['day']}）")

    rows = store.top_items(local_day(cfg))
    for row in rows:
        print(f"[{row['source']}] {row['title']}")
        print(f"    {row['url']}")
        print(f"    命中：{'、'.join(row['matched'])}\n")
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"共 {len(rows)} 条")


if __name__ == "__main__":
    main()
