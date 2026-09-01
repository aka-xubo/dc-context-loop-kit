#!/usr/bin/env python3
"""Create and clean project-local temporary workspaces for one operation."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class WorkspaceError(ValueError):
    pass


def _root(worktree_root: str | Path) -> Path:
    root = Path(worktree_root).expanduser().resolve()
    if not root.is_dir():
        raise WorkspaceError(f"repository.worktree_root 不存在或不是目录: {root}")
    return root


def _base(worktree_root: str | Path) -> Path:
    root = _root(worktree_root)
    candidate = root / ".local" / "dc-loop" / "tmp"
    candidate.mkdir(parents=True, exist_ok=True)
    base = candidate.resolve()
    if not base.is_relative_to(root):
        raise WorkspaceError(f"临时根目录解析后越出 repository.worktree_root: {base}")
    return base


def validate_operation_id(operation_id: str) -> str:
    if not isinstance(operation_id, str) or not OPERATION_ID_RE.fullmatch(operation_id):
        raise WorkspaceError("operation-id 只能包含字母、数字、点、下划线和短横线，且长度不超过 128")
    if operation_id in {".", ".."}:
        raise WorkspaceError("operation-id 不能是路径保留值")
    return operation_id


def operation_path(worktree_root: str | Path, operation_id: str) -> Path:
    base = _base(worktree_root)
    operation_id = validate_operation_id(operation_id)
    candidate = (base / operation_id).resolve()
    if candidate.parent != base:
        raise WorkspaceError("operation-id 导致临时路径越界")
    return candidate


def create_operation_workspace(worktree_root: str | Path, operation_id: str | None = None) -> Path:
    base = _base(worktree_root)
    if operation_id is None:
        operation_id = "op-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:12]
    path = operation_path(worktree_root, operation_id)
    try:
        path.mkdir(mode=0o700)
    except FileExistsError as error:
        raise WorkspaceError(f"operation-id 已存在，拒绝覆盖: {operation_id}") from error
    except OSError as error:
        raise WorkspaceError(f"无法创建临时操作目录: {path}: {error}") from error
    return path


def cleanup_operation_workspace(worktree_root: str | Path, operation_id: str) -> bool:
    base = _base(worktree_root)
    path = operation_path(worktree_root, operation_id)
    if path.exists() and path.is_symlink():
        raise WorkspaceError(f"拒绝清理符号链接操作目录: {path}")
    if path.exists() and not path.is_dir():
        raise WorkspaceError(f"操作路径不是目录: {path}")
    try:
        if path.exists():
            shutil.rmtree(path)
        remaining = [item for item in base.iterdir() if item.name not in {".DS_Store"}]
    except OSError as error:
        raise WorkspaceError(f"清理临时操作目录失败: {path}: {error}") from error
    if path.exists():
        raise WorkspaceError(f"清理后操作目录仍存在: {path}")
    return not remaining


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create", help="创建唯一操作目录")
    create.add_argument("--worktree-root", required=True, type=Path)
    create.add_argument("--operation-id")
    cleanup = subparsers.add_parser("cleanup", help="清理一个操作目录")
    cleanup.add_argument("--worktree-root", required=True, type=Path)
    cleanup.add_argument("--operation-id", required=True)
    cleanup.add_argument("--terminal-status", choices=["SUCCESS", "FAILED", "BLOCKED", "INTERRUPTED"], required=True)
    path_parser = subparsers.add_parser("path", help="输出操作目录路径但不创建")
    path_parser.add_argument("--worktree-root", required=True, type=Path)
    path_parser.add_argument("--operation-id", required=True)
    try:
        if args := parser.parse_args():
            if args.command == "create":
                path = create_operation_workspace(args.worktree_root, args.operation_id)
                print(json.dumps({"operation_id": path.name, "path": str(path)}, ensure_ascii=False))
            elif args.command == "path":
                print(json.dumps({"operation_id": validate_operation_id(args.operation_id), "path": str(operation_path(args.worktree_root, args.operation_id))}, ensure_ascii=False))
            else:
                empty = cleanup_operation_workspace(args.worktree_root, args.operation_id)
                print(json.dumps({"operation_id": args.operation_id, "terminal_status": args.terminal_status, "cleaned": True, "tmp_root_empty": empty}, ensure_ascii=False))
        return 0
    except (WorkspaceError, OSError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
