#!/usr/bin/env python3
"""Render the Markdown delivery index from REQ-first truth sources."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from validate_delivery_proof import Project, as_dict, load_project


DEFAULT_ROOT = Path("docs/交付证明")


class ReviewError(ValueError):
    pass


def delivery_stage(project: Project, requirement_id: str) -> str:
    requirement = as_dict(project.requirements[requirement_id].get("requirement"))
    if requirement.get("status") == "DRAFT":
        return "需求待确认"
    scenario_doc = project.scenarios.get(requirement_id)
    if scenario_doc is None:
        return "场景未开始"
    if as_dict(scenario_doc.get("acceptance_scenarios")).get("status") == "DRAFT":
        return "场景待确认"
    matrix_doc = project.matrices.get(requirement_id)
    if matrix_doc is None:
        return "矩阵未开始"
    if as_dict(matrix_doc.get("acceptance_matrix")).get("status") == "DRAFT":
        return "矩阵待确认"
    report = project.reports.get(requirement_id)
    if report is not None:
        status = as_dict(report.get("acceptance_report")).get("status")
        return "已验收" if status == "SATISFIED" else "未通过验收"
    plan = project.plans.get(requirement_id)
    if plan is None:
        return "开发未开始"
    plan_status = as_dict(plan.get("implementation_plan")).get("status")
    return {
        "PLANNED": "实现已规划",
        "IN_PROGRESS": "开发中",
        "READY": "待验证",
    }.get(str(plan_status), str(plan_status))


def current_rows(project: Project) -> list[dict[str, Any]]:
    rows = []
    for requirement_id in sorted(project.requirements):
        requirement = as_dict(project.requirements[requirement_id].get("requirement"))
        rows.append(
            {
                "id": requirement_id,
                "requirement": requirement,
                "stage": delivery_stage(project, requirement_id),
            }
        )
    return rows


def render_catalog_markdown(project: Project) -> str:
    lines = [
        "# 需求清单",
        "",
        "本文件由各 REQ 根目录当前定义自动派生，不保存独立版本或上线裁决。",
        "",
        "| REQ | Issue No | 需求状态 | 交付阶段 | 标题 |",
        "|---|---|---|---|---|",
    ]
    for row in current_rows(project):
        requirement = row["requirement"]
        lines.append(
            f"| [{row['id']}](./{row['id']}/需求.md) | {requirement.get('issue_no')} | "
            f"{requirement.get('status')} | {row['stage']} | {requirement.get('title')} |"
        )
    lines.append("")
    return "\n".join(lines)


def expected_outputs(root: Path) -> dict[Path, str]:
    project = load_project(root.resolve())
    if project.validation.errors:
        raise ReviewError("；".join(project.validation.errors))
    return {root / "需求清单.md": render_catalog_markdown(project)}


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
