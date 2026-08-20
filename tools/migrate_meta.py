#!/usr/bin/env python3
"""把 chapter_meta v1 保守迁移为 v2；默认只预览，不覆盖原文件。"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:
    from tools.meta_schema import migrate_v1_to_v2, validate_chapter_meta
except ModuleNotFoundError:  # 直接执行 tools/migrate_meta.py
    from meta_schema import migrate_v1_to_v2, validate_chapter_meta


def atomic_json(path: Path, payload: object) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="chapter_meta v1 → v2 保守迁移")
    parser.add_argument("paths", nargs="+", help="一个或多个 .meta.json / chapter_meta.json")
    parser.add_argument("--write", action="store_true", help="写回文件；默认只输出预览")
    args = parser.parse_args()
    for raw in args.paths:
        path = Path(raw).resolve()
        original = json.loads(path.read_text(encoding="utf-8"))
        is_collection = isinstance(original, list)
        items = original if is_collection else [original]
        migrated = [migrate_v1_to_v2(item) for item in items]
        errors = [f"{item.get('chapter_id', '?')}: {error}" for item in migrated for error in validate_chapter_meta(item)]
        payload = migrated if is_collection else migrated[0]
        if args.write:
            backup = path.with_suffix(path.suffix + f".v1-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
            shutil.copy2(path, backup)
            atomic_json(path, payload)
            print(f"✓ 已迁移 {path}；备份 {backup}")
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        if errors:
            print("⚠ 迁移结果仍需核验，未自动建立结论—证据关系:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
