#!/usr/bin/env python3
"""Render and check the human-readable implementation plan view."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml


BLOCK_RE = re.compile(r"```yaml\s*(.*?)\s*```", re.DOTALL)


class RenderError(Exception):
    pass


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_document(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        match = BLOCK_RE.search(raw)
        document = yaml.safe_load(match.group(1) if match else raw)
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise RenderError(f"无法读取 {path}: {error}") from error
    if not isinstance(document, dict):
        raise RenderError(f"文档根对象必须是对象: {path}")
    return document


def cell(value: Any) -> str:
    text = str(value).replace("\n", " ").replace("|", "\\|")
    return text or "无"


def bullets(items: list[Any], empty: str = "无") -> str:
    return "\n".join(f"- {cell(item)}" for item in items) if items else f"- {empty}"


def status_text(value: Any) -> str:
    return f"`{cell(value)}`"


def render(plan_document: dict[str, Any], matrix_document: dict[str, Any]) -> str:
    if plan_document.get("document_type") != "implementation_plan":
        raise RenderError("实现计划 document_type 必须为 implementation_plan")
    if matrix_document.get("document_type") != "acceptance_matrix":
        raise RenderError("验收矩阵 document_type 必须为 acceptance_matrix")
    plan = as_dict(plan_document.get("implementation_plan"))
    matrix = as_dict(matrix_document.get("acceptance_matrix"))
    requirement_id = as_dict(plan.get("requirement_ref")).get("requirement_id")
    matrix_requirement_id = as_dict(matrix_document.get("requirement_ref")).get("requirement_id")
    spec_ref = plan.get("spec_ref")
    if not requirement_id or requirement_id != matrix_requirement_id:
        raise RenderError("实现计划与验收矩阵的 REQ 引用不一致")
    if not isinstance(spec_ref, str) or not re.fullmatch(r"SPEC-[0-9]{3}", spec_ref):
        raise RenderError("实现计划缺少三位数字 spec_ref")
    if matrix.get("status") != "CONFIRMED":
        raise RenderError("只有 CONFIRMED 验收矩阵可以生成实现计划视图")

    assertions: dict[str, dict[str, Any]] = {}
    for check in as_list(matrix.get("checks")):
        check_item = as_dict(check)
        for assertion in as_list(check_item.get("assertions")):
            item = as_dict(assertion)
            if item.get("id"):
                assertions[str(item["id"])] = item

    slices = [as_dict(item) for item in as_list(plan.get("slices"))]
    referenced_assertions = {
        str(ref)
        for item in slices
        for ref in as_list(item.get("assertion_refs"))
    }
    missing_assertions = sorted(referenced_assertions - set(assertions))
    if missing_assertions:
        raise RenderError(f"实现计划引用了当前验收矩阵不存在的 AST: {', '.join(missing_assertions)}")
    behavior_count = sum(item.get("kind") == "behavior_slice" for item in slices)
    completed_count = sum(item.get("status") == "COMPLETED" for item in slices)
    blockers = as_list(plan.get("blockers"))
    review = as_dict(plan.get("completion_review"))
    surfaces = [as_dict(item) for item in as_list(plan.get("delivery_surfaces"))]
    ready_surfaces = sum(item.get("status") in {"COMPLETED", "NOT_REQUIRED"} for item in surfaces)
    readiness = as_dict(plan.get("readiness"))
    readiness_states = [
        as_dict(readiness.get(key)).get("status", "未声明")
        for key in ("configuration", "persistence", "application_start")
    ]
    objectives = [cell(item.get("objective")).rstrip("。； ") for item in slices]
    objective = "；".join(objectives) + ("。" if objectives else "")
    lines = [
        "# 实现计划",
        "",
        "## 执行摘要",
        "",
        f"- 状态：{status_text(plan.get('status'))}",
        f"- 当前 REQ：`{cell(requirement_id)}`",
        f"- 当前 SPEC：`{cell(spec_ref)}`",
        f"- 目标：{objective or '无'}",
        f"- 进度：{completed_count}/{len(slices)} 个切片完成，其中 {behavior_count} 个行为切片",
        f"- 阻塞：{'无' if not blockers else f'{len(blockers)} 项'}",
        f"- 就绪：{ready_surfaces}/{len(surfaces)} 个交付面完成；环境条件 {', '.join(map(str, readiness_states))}",
        f"- 完成复核：{status_text(review.get('status', 'PENDING'))}",
        "",
        "## 关键发现与决策",
        "",
        "### 盘点结论",
        "",
    ]
    findings = as_list(as_dict(plan.get("context_review")).get("findings"))
    if findings:
        lines.extend([
            "| 领域 | 已发现事实 | 对计划的影响 |",
            "|---|---|---|",
            *(f"| {cell(as_dict(item).get('area'))} | {cell(as_dict(item).get('observation'))} | {cell(as_dict(item).get('impact'))} |" for item in findings),
        ])
    else:
        lines.append("- 无")
    lines.extend(["", "### 实现决策", ""])
    decisions = as_list(as_dict(plan.get("context_review")).get("decisions"))
    if decisions:
        lines.extend([
            "| 决策 | 主题 | 结论 | 来源 | 影响切片 |",
            "|---|---|---|---|---|",
            *(f"| `{cell(as_dict(item).get('id'))}` | {cell(as_dict(item).get('topic'))} | {cell(as_dict(item).get('decision'))} | {cell(as_dict(item).get('source'))} | {cell(', '.join(map(str, as_list(as_dict(item).get('affected_slice_refs')))) or '无')} |" for item in decisions),
        ])
    else:
        lines.append("- 无")

    lines.extend(["", "## 实现切片", ""])
    for index, item in enumerate(slices, start=1):
        lines.extend([
            f"### {index}. `{cell(item.get('id'))}` {cell(item.get('title'))}",
            "",
            f"- 状态：{status_text(item.get('status'))}",
            f"- 类型：{status_text(item.get('kind'))}",
            f"- 目标：{cell(item.get('objective'))}",
            f"- 前置切片：{cell(', '.join(map(str, as_list(item.get('depends_on')))) or '无')}",
            f"- 检查责任：{cell(', '.join(map(str, as_list(item.get('check_refs')))) or '无')}",
            "- 行为覆盖：",
        ])
        assertion_refs = list(map(str, as_list(item.get("assertion_refs"))))
        if assertion_refs:
            for ref in assertion_refs:
                description = assertions[ref].get("description")
                lines.append(f"  - `{cell(ref)}`：{cell(description)}")
        else:
            lines.append("  - 无")
        production_refs = as_list(item.get("production_refs"))
        test_refs = as_list(item.get("test_refs"))
        lines.extend([
            "- 生产引用：",
            *([f"  - `{cell(ref)}`" for ref in production_refs] or ["  - 无"]),
            "- 测试引用：",
            *([f"  - `{cell(ref)}`" for ref in test_refs] or ["  - 无"]),
            "",
        ])

    strategy = as_dict(plan.get("test_strategy"))
    lines.extend([
        "## 测试策略",
        "",
        f"- 默认方式：{status_text(strategy.get('default'))}",
        "- 豁免：",
        bullets(as_list(strategy.get("exemptions"))),
        "",
        "## 阻塞与就绪",
        "",
        "### 当前阻塞",
        "",
        bullets(blockers),
        "",
        "### 就绪条件",
        "",
    ])
    for key, label in (("configuration", "配置"), ("persistence", "持久化"), ("application_start", "应用启动")):
        lines.append(f"- {label}：{status_text(as_dict(readiness.get(key)).get('status', '未声明'))}")
    journeys = as_list(readiness.get("external_journeys"))
    lines.append(f"- 外部旅程：{'无' if not journeys else f'{len(journeys)} 项'}")

    machine = yaml.safe_dump(plan_document, allow_unicode=True, sort_keys=False).rstrip()
    lines.extend([
        "",
        "## 机器计划",
        "",
        "<!-- DELIVERY_PROOF_YAML_START -->",
        "```yaml",
        machine,
        "```",
        "<!-- DELIVERY_PROOF_YAML_END -->",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-file", required=True, type=Path)
    parser.add_argument("--matrix-file", required=True, type=Path)
    parser.add_argument("--output-file", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        plan_document = load_document(args.plan_file)
        matrix_document = load_document(args.matrix_file)
        rendered = render(plan_document, matrix_document)
        target = args.output_file or args.plan_file
        if args.check:
            if args.output_file:
                raise RenderError("--check 不接受 --output-file")
            current = args.plan_file.read_text(encoding="utf-8")
            if current != rendered:
                raise RenderError("实现计划人类视图与机器计划或当前验收矩阵不一致")
            print(f"实现计划人类视图一致: {args.plan_file}")
            return 0
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        print(str(target.resolve()))
        return 0
    except (RenderError, OSError, UnicodeError) as error:
        print(f"实现计划渲染失败: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
