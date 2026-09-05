#!/usr/bin/env python3
"""Shared helpers for the current REQ-first Delivery Proof model."""

from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

import yaml


START_MARKER = "<!-- DELIVERY_PROOF_YAML_START -->"
END_MARKER = "<!-- DELIVERY_PROOF_YAML_END -->"
REQ_RE = re.compile(r"^REQ-[A-Za-z0-9_-]+$")
ISSUE_NO_RE = re.compile(r"^[A-Z][A-Z0-9]*-[1-9][0-9]*$")
SCN_RE = re.compile(r"^SCN-[A-Za-z0-9_-]+$")
CHK_RE = re.compile(r"^CHK-[A-Za-z0-9_-]+$")
DEP_RE = re.compile(r"^DEP-[A-Za-z0-9_-]+$")
AST_RE = re.compile(r"^AST-[A-Za-z0-9_-]+$")
RUN_RE = re.compile(r"^RUN-[A-Za-z0-9_-]+$")
ART_RE = re.compile(r"^ART-[A-Za-z0-9_-]+$")


class ModelError(ValueError):
    pass


def read_utf8(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ModelError(f"{path}: 必须使用 UTF-8 无 BOM")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ModelError(f"{path}: 不是有效 UTF-8: {error}") from error


def extract_document(path: Path, expected_type: str | None = None) -> dict[str, Any]:
    text = read_utf8(path)
    if text.count(START_MARKER) != 1 or text.count(END_MARKER) != 1:
        raise ModelError(f"{path}: 必须且只能包含一组 Delivery Proof YAML 标识")
    start = text.index(START_MARKER) + len(START_MARKER)
    end = text.index(END_MARKER, start)
    block = text[start:end].strip().splitlines()
    if len(block) < 3 or block[0].strip() != "```yaml" or block[-1].strip() != "```":
        raise ModelError(f"{path}: 固定标识内必须是 yaml 代码块")
    try:
        data = yaml.safe_load("\n".join(block[1:-1]))
    except yaml.YAMLError as error:
        raise ModelError(f"{path}: YAML 解析失败: {error}") from error
    if not isinstance(data, dict):
        raise ModelError(f"{path}: YAML 根节点必须是对象")
    if expected_type is not None and data.get("document_type") != expected_type:
        raise ModelError(f"{path}: document_type 必须是 {expected_type}")
    return data


def yaml_text(data: dict[str, Any]) -> str:
    return yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        width=1000,
        default_flow_style=False,
    ).rstrip()


def markdown_document(title: str, summary: str, data: dict[str, Any]) -> str:
    return (
        f"# {title}\n\n"
        f"## 当前说明\n\n{summary}\n\n"
        f"{START_MARKER}\n```yaml\n{yaml_text(data)}\n```\n{END_MARKER}\n"
    )


def requirement_digest(requirement: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in requirement.items()
        if key not in {"confirmation", "issue_no"}
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def stable_digest(value: Any, prefix: str) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def scoped_document_digest(document: dict[str, Any], scope_key: str, prefix: str) -> str:
    """Digest the current definition without confirmation or history metadata."""
    scope = dict(document[scope_key])
    scope.pop("confirmation", None)
    payload = {
        key: value
        for key, value in document.items()
        if key != scope_key
    }
    payload[scope_key] = scope
    return stable_digest(payload, prefix)


def discover_current_requirement_documents(root: Path) -> dict[str, Path]:
    """Discover the single current requirement document for each REQ."""
    return {
        path.parent.name: path
        for path in sorted(root.glob("REQ-*/需求.md"))
        if path.parent.name.startswith("REQ-")
    }


def html_escape(value: Any) -> str:
    return html.escape(str(value), quote=True)
