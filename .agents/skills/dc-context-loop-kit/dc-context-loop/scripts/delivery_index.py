#!/usr/bin/env python3
"""Build a local, Issue-backed delivery proof index from a complete comment export."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


EVENT_RE = re.compile(r"<!-- DEEP_CREW_EVENT_START -->\s*```yaml\s*(.*?)\s*```\s*<!-- DEEP_CREW_EVENT_END -->", re.DOTALL)
ID_RE = re.compile(r"^(REQ|SPEC|IMPLEMENTATION|ACCEPTANCE)$")
SUBJECT_RE = re.compile(r"^(SPEC|IMP|ACC)-[A-Za-z0-9_-]+$")
EVENT_ID_HINT_RE = re.compile(r"(?:^|[-_])(SPEC|IMP|ACC)-[A-Za-z0-9_-]+(?:$|[-_])")
ISSUE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class IndexError(ValueError):
    pass


def _comments(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        raw = value
    elif isinstance(value, dict):
        raw = value.get("comments") or value.get("data") or value.get("items") or []
        if isinstance(raw, dict):
            raw = raw.get("comments") or raw.get("items") or []
    else:
        raw = []
    return [item for item in raw if isinstance(item, dict)]


def load_comments(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IndexError(f"无法读取评论 JSON: {path}: {error}") from error
    return _comments(value)


def _event(comment: dict[str, Any]) -> dict[str, Any] | None:
    content = comment.get("content") or comment.get("body") or comment.get("text") or ""
    match = EVENT_RE.search(str(content))
    if not match:
        return None
    try:
        value = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    if not isinstance(value, dict) or value.get("document_type") != "deep_crew_delivery_event":
        return None
    event = value.get("event")
    if not isinstance(event, dict) or event.get("node") not in {"REQ", "SPEC", "IMPLEMENTATION", "ACCEPTANCE"}:
        return None
    return event


def _display_id(event: dict[str, Any]) -> str:
    subject = event.get("subject_id")
    if isinstance(subject, str) and SUBJECT_RE.fullmatch(subject):
        return subject
    event_id = str(event.get("event_id") or "")
    matches = EVENT_ID_HINT_RE.findall(event_id)
    if len(matches) == 1:
        match = re.search(r"(SPEC|IMP|ACC)-[A-Za-z0-9_-]+", event_id)
        if match:
            return match.group(0)
    return event_id or "未命名事件"


def collect_events(comments: list[dict[str, Any]], issue_url: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    seen_comments: set[str] = set()
    seen_events: set[str] = set()
    for position, comment in enumerate(comments):
        comment_id = str(comment.get("id") or comment.get("uuid") or "")
        if comment_id and comment_id in seen_comments:
            raise IndexError(f"完整 intake 包含重复评论 UUID: {comment_id}")
        if comment_id:
            seen_comments.add(comment_id)
        event = _event(comment)
        if event is None:
            continue
        node = str(event["node"])
        category = {"REQ": "REQ", "SPEC": "SPEC", "IMPLEMENTATION": "IMPLEMENTATION", "ACCEPTANCE": "ACCEPTANCE"}[node]
        event_id = str(event.get("event_id") or "")
        if not event_id:
            raise IndexError(f"交付事件缺少 event_id: comment {comment_id or position}")
        if event_id in seen_events:
            raise IndexError(f"完整 intake 包含重复 event_id: {event_id}")
        seen_events.add(event_id)
        records.append({
            "category": category,
            "display_id": _display_id(event),
            "event_id": event_id,
            "comment_id": comment_id or f"position-{position}",
            "created_at": str(comment.get("created_at") or event.get("created_at") or ""),
            "location": f"{issue_url}#comment-{comment_id}" if comment_id else issue_url,
        })
    records.sort(key=lambda item: (item["created_at"], item["comment_id"]))
    return records


def render_index(issue_key: str, issue_url: str, records: list[dict[str, str]], *, coverage: str, last_comment_id: str, synced_at: str) -> str:
    grouped = {category: [item for item in records if item["category"] == category] for category in ("REQ", "SPEC", "IMPLEMENTATION", "ACCEPTANCE")}
    lines = [
        f"# {issue_key} 交付证明索引",
        "",
        f"- Issue：{issue_key}",
        f"- Issue 地址：{issue_url}",
        "- 唯一事实源：Issue 完整评论时间线",
        f"- 覆盖状态：{coverage}",
        f"- 最后评论 ID：{last_comment_id or 'None'}",
        f"- 同步时间：{synced_at}",
        "",
        "本文件仅提供本地导航，不复制事件机器块、规格对象、代码差异、RUN/ART 或验收正文。",
    ]
    labels = {"REQ": "REQ", "SPEC": "SPEC", "IMPLEMENTATION": "IMPLEMENTATION", "ACCEPTANCE": "ACCEPTANCE"}
    for category in labels:
        items = grouped[category]
        lines.extend(["", f"## {labels[category]}（{len(items)}）", ""])
        if not items:
            lines.append("- 无")
            continue
        for item in items:
            lines.append(f"- {item['display_id']}：event `{item['event_id']}`；comment `{item['comment_id']}`；[原评论]({item['location']})")
    lines.append("")
    return "\n".join(lines)


def _absolute_path(root: Path, path: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = root / expanded
    return Path(os.path.abspath(expanded))


def _legacy_paths(worktree_root: Path, paths: list[Path], output_file: Path) -> list[tuple[Path, Path]]:
    root = worktree_root.expanduser().resolve()
    proof_root = (root / "docs" / "交付证明").resolve()
    output = _absolute_path(root, output_file)
    result: list[tuple[Path, Path]] = []
    for raw in paths:
        source = _absolute_path(root, raw)
        if not source.is_relative_to(proof_root):
            raise IndexError(f"旧交付路径必须位于 docs/交付证明 下: {raw}")
        if source == proof_root:
            raise IndexError("不能把 docs/交付证明 根目录作为旧交付路径")
        relative = source.relative_to(proof_root)
        cursor = proof_root
        for part in relative.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise IndexError(f"拒绝归档符号链接或其后代: {source}")
        if source == output or output.is_relative_to(source):
            raise IndexError(f"旧交付路径不能包含当前索引: {source}")
        for existing, _ in result:
            if source == existing or source.is_relative_to(existing) or existing.is_relative_to(source):
                raise IndexError(f"旧交付路径不能重复或相互嵌套: {source}")
        result.append((source, relative))
    return result


def archive_legacy_paths(worktree_root: Path, issue_key: str, paths: list[Path], output_file: Path, *, check: bool) -> None:
    if not ISSUE_KEY_RE.fullmatch(issue_key) or issue_key in {".", ".."}:
        raise IndexError(f"Issue key 不能用于归档目录: {issue_key}")
    pairs = _legacy_paths(worktree_root, paths, output_file)
    archive_base = (worktree_root.expanduser().resolve() / ".local" / "dc-loop" / "archive").resolve()
    archive_root = archive_base / issue_key
    moves: list[tuple[Path, Path]] = []
    for source, relative in pairs:
        if check:
            if source.exists():
                raise IndexError(f"旧交付路径仍存在: {source}")
            continue
        if not source.exists():
            continue
        destination = archive_root / relative
        if destination.exists():
            raise IndexError(f"归档目标已存在，拒绝覆盖: {destination}")
        moves.append((source, destination))
    for source, destination in moves:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))


def run(args: argparse.Namespace) -> int:
    if args.coverage != "FULL" and not args.check:
        raise IndexError("只有 coverage: FULL 的完整 intake 才能同步交付证明索引")
    comments = load_comments(args.comments_json)
    if args.legacy_path and args.worktree_root is None:
        raise IndexError("指定 --legacy-path 时必须提供 --worktree-root")
    if args.legacy_path:
        archive_legacy_paths(args.worktree_root, args.issue_key, args.legacy_path, args.output_file, check=args.check)
    records = collect_events(comments, args.issue_url)
    last_comment = max(comments, key=lambda item: str(item.get("created_at") or ""), default={})
    last_comment_id = args.last_comment_id or str(last_comment.get("id") or last_comment.get("uuid") or "")
    synced_at = args.synced_at or datetime.now(timezone.utc).isoformat()
    content = render_index(args.issue_key, args.issue_url, records, coverage=args.coverage, last_comment_id=last_comment_id, synced_at=synced_at)
    if args.check:
        if not args.output_file.is_file() or args.output_file.read_text(encoding="utf-8") != content:
            raise IndexError(f"本地交付证明索引与当前完整 intake 不一致: {args.output_file}")
        print(json.dumps({"checked": True, "events": len(records), "output_file": str(args.output_file.resolve())}, ensure_ascii=False))
        return 0
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    with args.output_file.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    print(json.dumps({"synced": True, "events": len(records), "output_file": str(args.output_file.resolve())}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-key", required=True)
    parser.add_argument("--issue-url", required=True)
    parser.add_argument("--comments-json", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    parser.add_argument("--coverage", choices=["FULL", "INCOMPLETE"], default="INCOMPLETE")
    parser.add_argument("--last-comment-id")
    parser.add_argument("--synced-at")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--worktree-root", type=Path)
    parser.add_argument("--legacy-path", action="append", type=Path, default=[])
    try:
        return run(parser.parse_args())
    except (IndexError, OSError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
