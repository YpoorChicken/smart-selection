"""Docker 入口：等待 DB/Redis → init_db/seed → exec 主进程。"""

from __future__ import annotations

import os
import sys
import time


def _wait_dependencies() -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError

    from app.config import get_settings
    from app.utils.redis_client import ping_redis

    settings = get_settings()
    settings.validate_required()
    deadline = time.time() + int(os.getenv("BOOTSTRAP_WAIT_SECONDS", "60"))
    engine = create_engine(settings.build_database_url(), pool_pre_ping=True)

    print("[entrypoint] waiting for database...", flush=True)
    while True:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[entrypoint] database ready", flush=True)
            break
        except OperationalError as exc:
            if time.time() >= deadline:
                print(f"[entrypoint] database timeout: {exc}", file=sys.stderr, flush=True)
                sys.exit(1)
            time.sleep(2)

    print("[entrypoint] waiting for redis...", flush=True)
    while True:
        if ping_redis():
            print("[entrypoint] redis ready", flush=True)
            break
        if time.time() >= deadline:
            print("[entrypoint] redis timeout", file=sys.stderr, flush=True)
            sys.exit(1)
        time.sleep(2)

    # Alembic 迁移落地前：compose 用 create_all 保证可启动
    from app.database import init_db
    from app.services.bootstrap import seed_initial_data

    print("[entrypoint] init_db + seed...", flush=True)
    init_db()
    seed_initial_data()
    print("[entrypoint] bootstrap done", flush=True)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: docker_entrypoint.py <command> [args...]", file=sys.stderr)
        sys.exit(2)
    _wait_dependencies()
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
