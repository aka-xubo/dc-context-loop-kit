#!/usr/bin/env python3
"""Render the Markdown delivery index from REQ-first truth sources."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from req_model import ISSUE_NO_RE, REQ_RE, ModelError, discover_current_requirement_documents, extract_document


DEFAULT_ROOT = Path("docs/交付证明")


class ReviewError(ValueError):
    pass


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_document(path: Path, expected_type: str) -> dict[str, Any] | None:
    """Read stage metadata without applying project-wide delivery-proof validation."""
    if not path.exists():
        return None
    try:
        return extract_document(path, expected_type)
    except (ModelError, OSError, UnicodeError):
        return None


def delivery_stage(root: Path, requirement_id: str, requirement: dict[str, Any]) -> str:
    if requirement.get("status") == "DRAFT":
        return "需求待确认"
    req_root = root / requirement_id
    scenario_doc = _optional_document(req_root / "验收场景.md", "acceptance_scenarios")
    if scenario_doc is None:
        return "场景未开始"
    if as_dict(scenario_doc.get("acceptance_scenarios")).get("status") == "DRAFT":
        return "场景待确认"
    matrix_doc = _optional_document(req_root / "验收矩阵.md", "acceptance_matrix")
    if matrix_doc is None:
        return "矩阵未开始"
    if as_dict(matrix_doc.get("acceptance_matrix")).get("status") == "DRAFT":
        return "矩阵待确认"
    report = _optional_document(req_root / "验收报告.md", "acceptance_report")
    if report is not None:
        status = as_dict(report.get("acceptance_report")).get("status")
        return "已验收" if status == "SATISFIED" else "未通过验收"
    plan = _optional_document(req_root / "实现计划.md", "implementation_plan")
    if plan is None:
        return "开发未开始"
    plan_status = as_dict(plan.get("implementation_plan")).get("status")
    return {
        "PLANNED": "实现已规划",
        "IN_PROGRESS": "开发中",
        "READY": "待验证",
    }.get(str(plan_status), str(plan_status))


def load_catalog(root: Path) -> tuple[Path, dict[str, dict[str, Any]]]:
    requirements: dict[str, dict[str, Any]] = {}
    discovered = discover_current_requirement_documents(root)
    if not discovered:
        raise ReviewError(f"{root}: 未发现 REQ-*/需求.md")
    for requirement_id, path in discovered.items():
        try:
            document = extract_document(path, "requirement")
        except (ModelError, OSError, UnicodeError) as error:
            raise ReviewError(str(error)) from error
        requirement = as_dict(document.get("requirement"))
        if requirement.get("id") != requirement_id or REQ_RE.fullmatch(str(requirement.get("id", ""))) is None:
            raise ReviewError(f"{path}: requirement.id 与 REQ 目录不一致或格式非法")
        if not isinstance(requirement.get("issue_no"), str) or ISSUE_NO_RE.fullmatch(requirement["issue_no"]) is None:
            raise ReviewError(f"{path}: requirement.issue_no 缺失或格式非法")
        if requirement.get("status") not in {"DRAFT", "CONFIRMED", "SATISFIED"}:
            raise ReviewError(f"{path}: requirement.status 非法")
        if not isinstance(requirement.get("title"), str) or not requirement["title"].strip():
            raise ReviewError(f"{path}: requirement.title 不能为空")
        requirements[requirement_id] = requirement
    return root, requirements


def current_rows(root: Path, requirements: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for requirement_id in sorted(requirements):
        requirement = requirements[requirement_id]
        rows.append(
            {
                "id": requirement_id,
                "requirement": requirement,
                "stage": delivery_stage(root, requirement_id, requirement),
            }
        )
    return rows


def render_catalog_markdown(root: Path, requirements: dict[str, dict[str, Any]]) -> str:
    lines = [
        "# 需求清单",
        "",
        "本文件由各 REQ 根目录当前定义自动派生，不保存独立版本或上线裁决。",
        "",
        "| REQ | Issue No | 需求状态 | 交付阶段 | 标题 |",
        "|---|---|---|---|---|",
    ]
    for row in current_rows(root, requirements):
        requirement = row["requirement"]
        lines.append(
            f"| [{row['id']}](./{row['id']}/需求.md) | {requirement.get('issue_no')} | "
            f"{requirement.get('status')} | {row['stage']} | {requirement.get('title')} |"
        )
    lines.append("")
    return "\n".join(lines)


def expected_outputs(root: Path) -> dict[Path, str]:
    root, requirements = load_catalog(root.resolve())
    return {root / "需求清单.md": render_catalog_markdown(root, requirements)}


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def run(root: Path, check: bool) -> int:
    root = root.parent if root.is_file() else root
    outputs = expected_outputs(root)
    if check:
        stale = [
            path
            for path, content in outputs.items()
            if not path.exists() or path.read_text(encoding="utf-8") != content
        ]
        if stale:
            for path in stale:
                print(f"Markdown 需求清单不是最新派生视图: {path}", file=sys.stderr)
            return 1
        print(f"Markdown 需求清单与 REQ 真值源一致: {len(outputs)} 个文件")
        return 0
    for path, content in outputs.items():
        atomic_write(path, content)
    print(f"已生成 Markdown 需求清单: {len(outputs)} 个文件")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_ROOT, help="交付证明目录或需求清单路径")
    parser.add_argument("--check", action="store_true", help="只检查 Markdown 需求清单是否最新")
    args = parser.parse_args()
    try:
        return run(args.input, args.check)
    except (ReviewError, OSError, UnicodeError) as error:
        print(f"生成 Markdown 需求清单失败: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
