#!/usr/bin/env python3
"""清理指定 Issue 的历史事件 YAML 遗留文件。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ISSUE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
EVENT_FILE_RE = re.compile(r"^(?:REQ|SPEC|IMP|ACC)-[A-Za-z0-9_-]+-事件\.yaml$")


class CleanupError(ValueError):
    pass


def worktree_root(value: str | Path) -> Path:
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise CleanupError(f"worktree_root 不存在或不是目录: {root}")
    return root


def issue_drafts_dir(root: Path, issue_key: str) -> Path:
    if not ISSUE_KEY_RE.fullmatch(issue_key):
        raise CleanupError("issue-key 格式非法")
    drafts = (root / ".local" / "dc-loop" / "drafts").resolve()
    if drafts.exists() and drafts.is_symlink():
        raise CleanupError(f"拒绝处理符号链接 drafts 目录: {drafts}")
    target = (drafts / issue_key).resolve()
    if target.parent != drafts:
        raise CleanupError("Issue 草案目录越出 drafts 根目录")
    return target


def cleanup_legacy_event_files(root: Path, issue_key: str) -> list[str]:
    target = issue_drafts_dir(root, issue_key)
    if not target.exists():
        return []
    if target.is_symlink() or not target.is_dir():
        raise CleanupError(f"Issue 草案路径不是普通目录: {target}")

    removed: list[str] = []
    for item in sorted(target.iterdir()):
        if item.is_symlink():
            raise CleanupError(f"拒绝处理符号链接遗留材料: {item}")
        if item.is_file() and EVENT_FILE_RE.fullmatch(item.name):
            item.unlink()
            removed.append(str(item))
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cleanup_legacy_drafts", help="清理指定 Issue 的历史事件 YAML")
    parser.add_argument("--worktree-root", required=True, type=Path)
    parser.add_argument("--issue-key", required=True)
    args = parser.parse_args()
    try:
        root = worktree_root(args.worktree_root)
        removed = cleanup_legacy_event_files(root, args.issue_key)
        print(json.dumps({"issue_key": args.issue_key, "removed": removed, "count": len(removed)}, ensure_ascii=False, indent=2))
        return 0
    except (CleanupError, OSError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
