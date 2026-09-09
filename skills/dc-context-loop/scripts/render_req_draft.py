#!/usr/bin/env python3
"""从一个已校验的 REQ 事件生成独立的人类可读 Markdown 草案。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

import prepare_event as event_tool


def list_text(items: list[str]) -> str:
    if not items:
        return "- 无"
    return "\n".join(f"- {item}" for item in items)


def dependency_text(items: list[dict[str, Any]]) -> str:
    if not items:
        return "- 无"
    return "\n".join(
        f"- `{item['id']}` {item['description']}（关联 REQ：{item['related_requirement_id'] or '无'}）"
        for item in items
    )


def source_refs(event: dict[str, Any]) -> list[str]:
    references = event.get("references", {})
    if isinstance(references, dict):
        values = [str(value) for value in references.values() if isinstance(value, str) and value.strip()]
        if values:
            return values
    return []


def draft_document(event: dict[str, Any]) -> dict[str, Any]:
    requirement = event["requirement"]
    return {
        "document_type": "requirement",
        "requirement": {
            "id": requirement["id"],
            "status": "DRAFT",
            "issue_no": requirement["issue_no"],
            "title": requirement["title"],
            "statement": requirement["statement"],
            "business_outcomes": requirement["business_outcomes"],
            "scope": requirement["scope"],
            "constraints": requirement["constraints"],
            "dependencies": requirement["dependencies"],
            "open_questions": requirement["open_questions"],
            "release_notes": event["reason"],
            "source_refs": source_refs(event),
            "confirmation": None,
        },
    }


def render(event: dict[str, Any], document: dict[str, Any]) -> str:
    requirement = document["requirement"]
    title = requirement["title"]
    return f"""# {title}

## 当前说明

这是从结构化 REQ 事件 `{event['event_id']}` 自动生成的需求草案。确认信息由负责人确认流程写入；本文件当前状态为 `DRAFT`。

## 需求目标

{title}

## 需求陈述

{requirement['statement']}

## Issue No

`{requirement['issue_no']}`

## 业务结果

{list_text(requirement['business_outcomes'])}

## 范围

### 范围内

{list_text(requirement['scope']['included'])}

### 范围外

{list_text(requirement['scope']['excluded'])}

## 约束

{list_text(requirement['constraints'])}

## 依赖

{dependency_text(requirement['dependencies'])}

## 未决事项

{list_text(requirement['open_questions'])}

## 发布说明

{requirement['release_notes']}

<!-- DELIVERY_PROOF_YAML_START -->
```yaml
{yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=1000).rstrip()}
```
<!-- DELIVERY_PROOF_YAML_END -->
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="生成可供人类审查的 REQ Markdown 草案")
    parser.add_argument("--event-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    try:
        event = event_tool.parse_document(args.event_file.resolve())
        event_tool.validate(event)
        if event["node"] != "REQ":
            raise event_tool.EventError("REQ 草案事件的 node 必须为 REQ")
        if "issue_no" not in event["requirement"] or "dependencies" not in event["requirement"]:
            raise event_tool.EventError("REQ 草案事件必须使用统一 REQ 结构")
        document = draft_document(event)
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        args.output_file.write_bytes(render(event, document).encode("utf-8"))
        print(str(args.output_file.resolve()))
        return 0
    except (event_tool.EventError, OSError, UnicodeError, ValueError, yaml.YAMLError) as error:
        print(f"REQ 草案渲染失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
