#!/usr/bin/env python3
"""Render a human-reviewable SPEC draft from one event and an optional base snapshot."""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Any

import prepare_event as event_tool


def cell(value: Any) -> str:
    return event_tool.display(value).replace("|", "\\|").replace("\n", " ")


def scenario_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return "无"
    rows = [
        "| SCN | 标题 | 业务结果 | Given | When | Then | 交付面 |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in items:
        given = "；".join(item.get("given", [])) or "无"
        then = "；".join(f"{outcome['id']} {outcome['statement']}" for outcome in item.get("then", [])) or "无"
        rows.append(
            f"| `{item['id']}` | {cell(item['title'])} | {cell(item['business_result'])} | "
            f"{cell(given)} | {cell(item['when'])} | {cell(then)} | "
            f"{cell(', '.join(item.get('delivery_surfaces', [])) or '无')} |"
        )
    return "\n".join(rows)


def check_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return "无"
    rows = [
        "| CHK | 场景 | 类型 | 验证责任 | 必需 | 阻断 |",
        "|---|---|---|---|---|---|",
    ]
    rows.extend(
        f"| `{item['id']}` | {cell(', '.join(item['scenario_ids']))} | {cell(item['verification_type'])} | "
        f"{cell(item['responsibility'])} | {'是' if item['required'] else '否'} | {'是' if item['blocking'] else '否'} |"
        for item in items
    )
    return "\n".join(rows)


def assertion_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return "无"
    rows = [
        "| AST | CHK | 结果引用 | 类型 | 断言描述 |",
        "|---|---|---|---|---|",
    ]
    rows.extend(
        f"| `{item['id']}` | {cell(item['check_id'])} | {cell(', '.join(item['outcome_refs']))} | "
        f"{cell(item['assertion_type'])} | {cell(item['description'])} |"
        for item in items
    )
    return "\n".join(rows)


def render_object_tables(specification: dict[str, Any], *, title: str) -> str:
    return f"""### {title}：SCN 表

{scenario_table(specification['scenarios'])}

### {title}：CHK 表

{check_table(specification['checks'])}

### {title}：AST 表

{assertion_table(specification['assertions'])}"""


def scenario_details(items: list[dict[str, Any]], *, heading: str) -> str:
    if not items:
        return f"### {heading}\n\n无"
    sections = [f"### {heading}（{len(items)} 个独立场景）"]
    for item in items:
        given = "；".join(item.get("given", [])) or "无"
        then = "；".join(f"`{outcome['id']}` {outcome['statement']}" for outcome in item.get("then", [])) or "无"
        sections.extend([
            "",
            f"#### `{item['id']}` {cell(item['title'])}",
            "",
            f"- 业务结果：{cell(item['business_result'])}",
            f"- Given：{cell(given)}",
            f"- When：{cell(item['when'])}",
            f"- Then：{cell(then)}",
            f"- 交付面：{cell(', '.join(item.get('delivery_surfaces', [])) or '无')}",
        ])
    return "\n".join(sections)


def merge(base: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    result = {
        "requirement_ref": base["requirement_ref"],
        "scenarios": copy.deepcopy(base["scenarios"]),
        "checks": copy.deepcopy(base["checks"]),
        "assertions": copy.deepcopy(base["assertions"]),
        "open_questions": copy.deepcopy(delta.get("open_questions", [])),
    }
    changes = delta["changes"]
    for object_type in ("scenarios", "checks", "assertions"):
        items = {item["id"]: item for item in result[object_type]}
        for object_id in changes["removed"][object_type]:
            items.pop(object_id, None)
        for item in changes["modified"][object_type]:
            items[item["id"]] = copy.deepcopy(item)
        for item in changes["added"][object_type]:
            items[item["id"]] = copy.deepcopy(item)
        result[object_type] = list(items.values())
    event_tool.validate_specification(result)
    return result


def load_spec(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    event = event_tool.parse_document(path.resolve())
    event_tool.validate(event)
    if event["node"] != "SPEC":
        raise event_tool.EventError("SPEC 草案事件的 node 必须为 SPEC")
    return event, event["specification"]


def render(event: dict[str, Any], specification: dict[str, Any], effective: dict[str, Any], base_ref: str | None) -> str:
    """Render the draft with the exact production SPEC comment renderer.

    ``effective`` and ``base_ref`` are still computed by ``main`` so an
    incremental draft is validated against its base snapshot before it is
    shown.  The draft itself must not have a second, drifting presentation
    template: the same event data must produce the same human-readable
    comment that will be published by ``prepare_event.py``.
    """
    del specification, base_ref
    return event_tool.render(event, effective)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成可供人类审查的 SPEC 草案")
    parser.add_argument("--event-file", required=True, type=Path)
    parser.add_argument("--base-spec-file", type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    try:
        event, specification = load_spec(args.event_file)
        if "changes" in specification:
            if not args.base_spec_file:
                raise event_tool.EventError("增量 SPEC 草案必须指定 --base-spec-file 才能生成合并视图")
            base_event, base_spec = load_spec(args.base_spec_file)
            if "changes" in base_spec:
                raise event_tool.EventError("--base-spec-file 必须是完整 SPEC 快照")
            if base_event["subject_id"] != specification["base_spec_ref"]:
                raise event_tool.EventError("基础 SPEC 文件的 subject_id 与 base_spec_ref 不一致")
            if base_spec["requirement_ref"] != specification["requirement_ref"]:
                raise event_tool.EventError("基础 SPEC 与增量 SPEC 的 requirement_ref 不一致")
            effective = merge(base_spec, specification)
        else:
            effective = copy.deepcopy(specification)
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        args.output_file.write_text(render(event, specification, effective, specification.get("base_spec_ref")), encoding="utf-8")
        print(str(args.output_file.resolve()))
        return 0
    except (event_tool.EventError, OSError, ValueError):
        print("SPEC 草案渲染失败", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
