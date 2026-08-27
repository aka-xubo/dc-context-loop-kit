#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

BLOCK_RE = re.compile(
    r"<!-- DEEP_CREW_EVENT_START -->\s*```yaml\s*(.*?)\s*```\s*<!-- DEEP_CREW_EVENT_END -->",
    re.DOTALL,
)
EVENT_ID_RE = re.compile(r"^EVT-[A-Za-z0-9_-]+$")
SUBJECT_ID_RE = re.compile(r"^(IMP|ACC)-[A-Za-z0-9_-]+$")
REQ_ID_RE = re.compile(r"^REQ-[A-Za-z0-9_-]+$")
SCN_ID_RE = re.compile(r"^SCN-[A-Za-z0-9_-]+$")
CHK_ID_RE = re.compile(r"^CHK-[A-Za-z0-9_-]+$")
AST_ID_RE = re.compile(r"^AST-[A-Za-z0-9_-]+$")
THEN_ID_RE = re.compile(r"^THEN-[A-Za-z0-9_-]+$")
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
NODES = {"REQ", "SPEC", "IMPLEMENTATION", "ACCEPTANCE"}
IMPLEMENTATION_KINDS = {"behavior_slice", "engineering_slice", "readiness_slice"}
CHANGE_SURFACE_FIELDS = (
    "production_files", "test_files", "scripts", "new_interfaces", "changed_interfaces",
    "database_changes", "configuration_changes", "dependency_changes", "external_contract_changes",
)


class EventError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EventError(message)


def nonempty(value: Any, label: str) -> str:
    require(isinstance(value, str) and value.strip(), f"{label} 必须是非空字符串")
    return value.strip()


def ensure_keys(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    require(not unknown, f"{label} 存在未定义字段: {', '.join(unknown)}")


def parse_document(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"事件文件不存在: {path}")
    raw = path.read_text(encoding="utf-8")
    match = BLOCK_RE.search(raw)
    data = yaml.safe_load(match.group(1) if match else raw)
    require(isinstance(data, dict), "事件文档必须是对象")
    require(data.get("document_type") == "deep_crew_delivery_event", "document_type 非法")
    event = data.get("event")
    require(isinstance(event, dict), "event 必须是对象")
    return event


def string_list(value: Any, label: str, *, nonempty_items: bool = True) -> list[str]:
    require(isinstance(value, list), f"{label} 必须是数组")
    if nonempty_items:
        for index, item in enumerate(value):
            nonempty(item, f"{label}[{index}]")
    return value


def validate_requirement(requirement: Any) -> None:
    require(isinstance(requirement, dict), "REQ 缺少完整 requirement")
    for field in ("id", "title", "statement", "business_outcomes", "scope", "constraints", "open_questions"):
        require(field in requirement, f"requirement 缺少字段: {field}")
    require(isinstance(requirement["id"], str) and REQ_ID_RE.fullmatch(requirement["id"]), "requirement.id 必须为 REQ-*")
    nonempty(requirement["title"], "requirement.title")
    nonempty(requirement["statement"], "requirement.statement")
    outcomes = string_list(requirement["business_outcomes"], "requirement.business_outcomes")
    require(outcomes, "requirement.business_outcomes 必须是非空数组")
    scope = requirement["scope"]
    require(isinstance(scope, dict), "requirement.scope 必须是对象")
    string_list(scope.get("included"), "requirement.scope.included")
    string_list(scope.get("excluded"), "requirement.scope.excluded")
    string_list(requirement["constraints"], "requirement.constraints")
    string_list(requirement["open_questions"], "requirement.open_questions")


def validate_specification(specification: Any) -> None:
    require(isinstance(specification, dict), "SPEC 缺少完整 specification")
    for field in ("requirement_ref", "scenarios", "checks", "assertions", "open_questions"):
        require(field in specification, f"specification 缺少字段: {field}")
    require(isinstance(specification["requirement_ref"], str) and REQ_ID_RE.fullmatch(specification["requirement_ref"]), "specification.requirement_ref 必须为 REQ-*")
    scenarios = specification["scenarios"]
    checks = specification["checks"]
    assertions = specification["assertions"]
    require(isinstance(scenarios, list) and scenarios, "specification.scenarios 必须是非空数组")
    require(isinstance(checks, list) and checks, "specification.checks 必须是非空数组")
    require(isinstance(assertions, list) and assertions, "specification.assertions 必须是非空数组")
    string_list(specification["open_questions"], "specification.open_questions")

    scenario_ids = []
    outcome_refs = set()
    for index, scenario in enumerate(scenarios):
        require(isinstance(scenario, dict), f"scenarios[{index}] 必须是对象")
        for field in ("id", "title", "business_result", "given", "when", "then", "delivery_surfaces"):
            require(field in scenario, f"scenarios[{index}] 缺少字段: {field}")
        require(isinstance(scenario["id"], str) and SCN_ID_RE.fullmatch(scenario["id"]), f"scenarios[{index}].id 必须为 SCN-*")
        nonempty(scenario["title"], f"scenarios[{index}].title")
        nonempty(scenario["business_result"], f"scenarios[{index}].business_result")
        string_list(scenario["given"], f"scenarios[{index}].given")
        nonempty(scenario["when"], f"scenarios[{index}].when")
        require(isinstance(scenario["then"], list) and scenario["then"], f"scenarios[{index}].then 必须是非空数组")
        string_list(scenario["delivery_surfaces"], f"scenarios[{index}].delivery_surfaces")
        then_ids = []
        for then_index, outcome in enumerate(scenario["then"]):
            require(isinstance(outcome, dict), f"scenarios[{index}].then[{then_index}] 必须是对象")
            require(isinstance(outcome.get("id"), str) and THEN_ID_RE.fullmatch(outcome["id"]), f"scenarios[{index}].then[{then_index}].id 必须为 THEN-*")
            nonempty(outcome.get("statement"), f"scenarios[{index}].then[{then_index}].statement")
            then_ids.append(outcome["id"])
            outcome_refs.add(f"{scenario['id']}.{outcome['id']}")
        require(len(then_ids) == len(set(then_ids)), f"scenarios[{index}] 的 THEN ID 不能重复")
        scenario_ids.append(scenario["id"])
    require(len(scenario_ids) == len(set(scenario_ids)), "specification.scenarios ID 不能重复")

    check_ids = []
    for index, check in enumerate(checks):
        require(isinstance(check, dict), f"checks[{index}] 必须是对象")
        for field in ("id", "scenario_ids", "verification_type", "responsibility", "required", "blocking"):
            require(field in check, f"checks[{index}] 缺少字段: {field}")
        require(isinstance(check["id"], str) and CHK_ID_RE.fullmatch(check["id"]), f"checks[{index}].id 必须为 CHK-*")
        require(isinstance(check["scenario_ids"], list) and check["scenario_ids"], f"checks[{index}].scenario_ids 必须是非空数组")
        require(set(check["scenario_ids"]).issubset(set(scenario_ids)), f"checks[{index}] 引用了当前 SPEC 中不存在的 SCN")
        require(check["verification_type"] in {"unit", "api", "ui", "e2e"}, f"checks[{index}].verification_type 非法")
        nonempty(check["responsibility"], f"checks[{index}].responsibility")
        require(isinstance(check["required"], bool), f"checks[{index}].required 必须是布尔值")
        require(isinstance(check["blocking"], bool), f"checks[{index}].blocking 必须是布尔值")
        check_ids.append(check["id"])
    require(len(check_ids) == len(set(check_ids)), "specification.checks ID 不能重复")

    assertion_ids = []
    for index, assertion in enumerate(assertions):
        require(isinstance(assertion, dict), f"assertions[{index}] 必须是对象")
        for field in ("id", "check_id", "outcome_refs", "assertion_type", "description"):
            require(field in assertion, f"assertions[{index}] 缺少字段: {field}")
        require(isinstance(assertion["id"], str) and AST_ID_RE.fullmatch(assertion["id"]), f"assertions[{index}].id 必须为 AST-*")
        require(assertion["check_id"] in check_ids, f"assertions[{index}] 引用了当前 SPEC 中不存在的 CHK")
        require(isinstance(assertion["outcome_refs"], list) and assertion["outcome_refs"], f"assertions[{index}].outcome_refs 必须是非空数组")
        require(set(assertion["outcome_refs"]).issubset(outcome_refs), f"assertions[{index}] 引用了当前 SPEC 中不存在的结果")
        require(assertion["assertion_type"] in {"semantic", "predicate"}, f"assertions[{index}].assertion_type 非法")
        nonempty(assertion["description"], f"assertions[{index}].description")
        assertion_ids.append(assertion["id"])
    require(len(assertion_ids) == len(set(assertion_ids)), "specification.assertions ID 不能重复")


def validate(event: dict[str, Any]) -> dict[str, Any]:
    event_id = nonempty(event.get("event_id"), "event.event_id")
    require(EVENT_ID_RE.fullmatch(event_id) is not None, "event_id 格式必须为 EVT-*")
    nonempty(event.get("created_at"), "event.created_at")
    nonempty(event.get("author"), "event.author")
    node = nonempty(event.get("node"), "event.node")
    require(node in NODES, f"node 非法: {node}")
    nonempty(event.get("reason"), "event.reason")
    common_fields = {"event_id", "created_at", "author", "node", "reason", "references"}
    node_fields = {
        "REQ": common_fields | {"requirement"},
        "SPEC": common_fields | {"specification"},
        "IMPLEMENTATION": common_fields | {"subject_id", "implementation", "impact"},
        "ACCEPTANCE": common_fields | {"subject_id", "acceptance", "impact"},
    }
    ensure_keys(event, node_fields[node], "event")
    subject_id = event.get("subject_id")
    if node in {"REQ", "SPEC"}:
        if node == "REQ":
            validate_requirement(event.get("requirement"))
        else:
            validate_specification(event.get("specification"))
        subject_id = None
    else:
        subject_id = nonempty(subject_id, "event.subject_id")
        require(SUBJECT_ID_RE.fullmatch(subject_id) is not None, "subject_id 格式非法")
        require(subject_id.startswith("IMP-") if node == "IMPLEMENTATION" else subject_id.startswith("ACC-"), f"{node} 节点不能使用 subject_id: {subject_id}")
    if node == "IMPLEMENTATION":
        implementation = event.get("implementation")
        require(isinstance(implementation, dict), "IMPLEMENTATION 缺少完成交付对象")
        require(implementation.get("status") == "READY", "IMPLEMENTATION status 必须为 READY")
        for field in ("requirement_ref", "spec_refs", "summary", "completed_items", "change_surface", "development_checks", "known_limits", "git_commit"):
            require(field in implementation, f"IMPLEMENTATION 缺少字段: {field}")
        require(isinstance(implementation["requirement_ref"], str) and implementation["requirement_ref"].startswith("REQ-"), "implementation.requirement_ref 必须为 REQ-*")
        nonempty(implementation["summary"], "implementation.summary")
        require(isinstance(implementation["completed_items"], list) and implementation["completed_items"], "implementation.completed_items 必须是非空数组")
        require(isinstance(implementation["spec_refs"], list), "implementation.spec_refs 必须是数组")
        for value in implementation["spec_refs"]:
            require(isinstance(value, str) and value.split("-", 1)[0] in {"SCN", "CHK", "AST"}, f"implementation.spec_refs 非法: {value}")
        require(isinstance(implementation["development_checks"], list) and implementation["development_checks"], "implementation.development_checks 必须是非空数组")
        require(isinstance(implementation["known_limits"], list), "implementation.known_limits 必须是数组")
        for value in implementation["known_limits"]:
            nonempty(value, "implementation.known_limits[]")
        require(isinstance(implementation["git_commit"], str) and GIT_COMMIT_RE.fullmatch(implementation["git_commit"]), "implementation.git_commit 必须是完整 Git commit")
        slice_ids = []
        for index, item in enumerate(implementation["completed_items"]):
            require(isinstance(item, dict), f"implementation.completed_items[{index}] 必须是对象")
            for field in ("id", "title", "kind", "objective", "check_refs", "assertion_refs"):
                require(field in item, f"completed_items[{index}] 缺少字段: {field}")
            require(isinstance(item["id"], str) and re.fullmatch(r"SLICE-[A-Za-z0-9_-]+", item["id"]), f"completed_items[{index}].id 必须为 SLICE-*")
            nonempty(item["title"], f"completed_items[{index}].title")
            nonempty(item["objective"], f"completed_items[{index}].objective")
            require(item["kind"] in IMPLEMENTATION_KINDS, f"completed_items[{index}].kind 非法")
            require(isinstance(item["check_refs"], list), f"completed_items[{index}].check_refs 必须是数组")
            require(isinstance(item["assertion_refs"], list), f"completed_items[{index}].assertion_refs 必须是数组")
            slice_ids.append(item["id"])
        require(len(slice_ids) == len(set(slice_ids)), "implementation.completed_items ID 不能重复")
        surface = implementation["change_surface"]
        require(isinstance(surface, dict), "implementation.change_surface 必须是对象")
        for field in CHANGE_SURFACE_FIELDS:
            require(isinstance(surface.get(field), list), f"implementation.change_surface.{field} 必须是数组")
            for value in surface[field]:
                nonempty(value, f"implementation.change_surface.{field}[]")
        for index, check in enumerate(implementation["development_checks"]):
            require(isinstance(check, dict), f"development_checks[{index}] 必须是对象")
            require(isinstance(check.get("command"), str) and check["command"].strip(), f"development_checks[{index}].command 必须非空")
            require(check.get("status") in {"PASSED", "SKIPPED"}, f"development_checks[{index}].status 非法")
            nonempty(check.get("summary"), f"development_checks[{index}].summary")
    if node == "ACCEPTANCE":
        require(subject_id and subject_id.split("-", 1)[0] == "ACC", "ACCEPTANCE 必须使用 ACC-* subject_id")
        acceptance = event.get("acceptance")
        require(isinstance(acceptance, dict), "ACCEPTANCE 缺少完整 acceptance 结论对象")
        require(acceptance.get("status") in {"SATISFIED", "NOT_SATISFIED", "BLOCKED", "INCOMPLETE"}, "acceptance.status 非法")
        for field in ("requirement_ref", "spec_refs", "implementation_refs", "git_commit", "runs", "artifacts", "assertion_results", "reason"):
            require(field in acceptance, f"ACCEPTANCE 缺少字段: {field}")
        nonempty(acceptance["reason"], "acceptance.reason")
        require(isinstance(acceptance["git_commit"], str) and GIT_COMMIT_RE.fullmatch(acceptance["git_commit"]), "acceptance.git_commit 必须是完整 Git commit")
        require(isinstance(acceptance["spec_refs"], list), "acceptance.spec_refs 必须是数组")
        require(isinstance(acceptance["implementation_refs"], list), "acceptance.implementation_refs 必须是数组")
        require(isinstance(acceptance["runs"], list), "acceptance.runs 必须是数组")
        require(isinstance(acceptance["artifacts"], list), "acceptance.artifacts 必须是数组")
        require(isinstance(acceptance["assertion_results"], list), "acceptance.assertion_results 必须是数组")
        run_ids = [run.get("id") for run in acceptance["runs"] if isinstance(run, dict)]
        artifact_ids = [artifact.get("id") for artifact in acceptance["artifacts"] if isinstance(artifact, dict)]
        require(len(run_ids) == len(acceptance["runs"]) and len(set(run_ids)) == len(run_ids), "acceptance.runs ID 缺失或重复")
        require(len(artifact_ids) == len(acceptance["artifacts"]) and len(set(artifact_ids)) == len(artifact_ids), "acceptance.artifacts ID 缺失或重复")
        assertion_statuses = []
        for result in acceptance["assertion_results"]:
            require(isinstance(result, dict), "acceptance.assertion_results 项必须是对象")
            for field in ("assertion_id", "expected", "observed", "status", "artifact_refs"):
                require(field in result, f"断言结果缺少字段: {field}")
            require(result["status"] in {"PASSED", "FAILED", "BLOCKED"}, f"断言结果状态非法: {result['status']}")
            require(isinstance(result["artifact_refs"], list), "断言结果 artifact_refs 必须是数组")
            require(set(result["artifact_refs"]).issubset(set(artifact_ids)), f"断言结果引用了不存在的 ART: {result['assertion_id']}")
            assertion_statuses.append(result["status"])
        if acceptance["status"] == "SATISFIED":
            require(assertion_statuses and all(status == "PASSED" for status in assertion_statuses), "SATISFIED 要求所有断言均为 PASSED")
        if acceptance["status"] == "NOT_SATISFIED":
            require("FAILED" in assertion_statuses, "NOT_SATISFIED 至少需要一个 FAILED 断言")
        if acceptance["status"] == "BLOCKED":
            require("BLOCKED" in assertion_statuses, "BLOCKED 至少需要一个 BLOCKED 断言")
    if node in {"IMPLEMENTATION", "ACCEPTANCE"}:
        impact = event.get("impact")
        require(isinstance(impact, dict), "event.impact 必须是对象")
        for key in ("affected_ids", "next_actions"):
            require(isinstance(impact.get(key), list), f"impact.{key} 必须是数组")
        for index, action in enumerate(impact["next_actions"]):
            require(isinstance(action, dict), f"next_actions[{index}] 必须是对象")
            nonempty(action.get("action"), f"next_actions[{index}].action")
            nonempty(action.get("owner"), f"next_actions[{index}].owner")
    return {"event_id": event_id, "node": node, "subject_id": subject_id}


def load_comments(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    require(path.is_file(), f"评论 JSON 不存在: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("comments", data.get("data", [])) if isinstance(data, dict) else data
    require(isinstance(items, list), "评论 JSON 必须是数组或包含 comments/data 数组")
    return [item for item in items if isinstance(item, dict)]


def existing_event_ids(comments: list[dict[str, Any]]) -> set[str]:
    found: set[str] = set()
    for item in comments:
        match = BLOCK_RE.search(str(item.get("content", "")))
        if not match:
            continue
        try:
            data = yaml.safe_load(match.group(1))
            event = data.get("event", {}) if isinstance(data, dict) else {}
            if isinstance(event, dict) and isinstance(event.get("event_id"), str):
                found.add(event["event_id"])
        except yaml.YAMLError:
            continue
    return found


def display(value: Any) -> str:
    if value is None:
        return "无"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def list_text(value: Any) -> str:
    if value is None:
        return "未填写"
    if isinstance(value, list):
        return "\n".join(f"- {display(item)}" for item in value) if value else "- 无"
    return display(value)


def render_change_surface(value: Any, heading: str) -> str:
    if not isinstance(value, dict):
        return f"### {heading}\n\n{display(value)}"
    sections = []
    for field in CHANGE_SURFACE_FIELDS:
        items = value.get(field, [])
        sections.append(f"#### {field}\n\n{list_text(items)}")
    return f"### {heading}\n\n" + "\n\n".join(sections)


def render_implementation(event: dict[str, Any]) -> str:
    implementation = event["implementation"]
    impact = event["impact"]
    completed = "\n".join(
        f"### {item['id']} {item['title']}\n\n"
        f"- 类型：{item['kind']}\n"
        f"- 目标：{item['objective']}\n"
        f"- CHK：{', '.join(item['check_refs']) or '无'}\n"
        f"- AST：{', '.join(item['assertion_refs']) or '无'}"
        for item in implementation["completed_items"]
    )
    checks = "\n".join(
        f"| `{check['command']}` | {check['status']} | {check.get('summary', '无')} |"
        for check in implementation["development_checks"]
    )
    actions = "\n".join(f"- {item['action']}：{item['owner']}" for item in impact["next_actions"]) or "- 待分析"
    return f"""[DP:IMPLEMENTATION] {event['subject_id']} 实现完成

## 交付摘要

{implementation['summary']}

## 绑定上下文

- 状态：{implementation['status']}
- 需求：{implementation['requirement_ref']}
- 规格：{', '.join(implementation['spec_refs']) or '无'}
- Git commit：{implementation['git_commit']}

## 已完成内容

{completed}

{render_change_surface(implementation['change_surface'], '实际变更面')}

## 开发检查

| 命令 | 结果 | 摘要 |
|---|---|---|
{checks}

## 已知限制

{list_text(implementation['known_limits'])}

## 影响范围

- 受影响对象：{', '.join(impact['affected_ids']) if impact['affected_ids'] else '无'}

## 下一步

{actions}

{render_machine_block(event)}"""


def render_acceptance(event: dict[str, Any]) -> str:
    acceptance = event["acceptance"]
    rows = "\n".join(
        f"| `{item['assertion_id']}` | {display(item['expected'])} | {display(item['observed'])} | {item['status']} | {', '.join(item.get('artifact_refs', [])) or '无'} |"
        for item in acceptance["assertion_results"]
    ) or "| - | - | - | - | - |"
    runs = "\n".join(
        f"- `{run['id']}`：{run['phase']}：{run['status']}（CHK：{', '.join(run.get('check_refs', [])) or '无'}；AST：{', '.join(run.get('assertion_refs', [])) or '无'}）"
        for run in acceptance["runs"]
    ) or "- 无"
    artifacts = "\n".join(
        f"- `{artifact['id']}`：{artifact['type']}，{artifact['location']}"
        for artifact in acceptance["artifacts"]
    ) or "- 无"
    return f"""[DP:ACCEPTANCE] {event['subject_id']} 验收结论

## 验收基线

- 需求：{acceptance['requirement_ref']}
- 规格：{', '.join(acceptance['spec_refs']) or '无'}
- 实现：{', '.join(acceptance['implementation_refs']) or '无'}
- Git commit：{acceptance['git_commit'] or '无'}

## 本地执行

{runs}

## 证据

{artifacts}

## 逐断言结果

| 断言 | 预期 | 实际观察 | 结果 | 证据 |
|---|---|---|---|---|
{rows}

## 最终结论

- 结论：**{acceptance['status']}**
- 裁决原因：{acceptance['reason']}

## 下一步

{'; '.join(item['action'] + '：' + item['owner'] for item in event['impact']['next_actions']) or '等待总协调器根据结论路由下一步'}

{render_machine_block(event)}"""


def render_spec(event: dict[str, Any]) -> str:
    specification = event["specification"]
    scenarios = "\n\n".join(
        f"### {scenario['id']} {scenario['title']}\n\n"
        f"- 业务结果：{scenario['business_result']}\n"
        f"- Given：{'；'.join(scenario['given']) or '无'}\n"
        f"- When：{scenario['when']}\n"
        f"- Then：{'；'.join(outcome['id'] + ' ' + outcome['statement'] for outcome in scenario['then'])}\n"
        f"- 交付面：{', '.join(scenario['delivery_surfaces']) or '无'}"
        for scenario in specification["scenarios"]
    )
    checks = "\n".join(
        f"| `{check['id']}` | {', '.join(check['scenario_ids'])} | {check['verification_type']} | {check['responsibility']} | "
        f"{'是' if check['required'] else '否'} | {'是' if check['blocking'] else '否'} |"
        for check in specification["checks"]
    )
    assertions = "\n".join(
        f"| `{assertion['id']}` | {assertion['check_id']} | {', '.join(assertion['outcome_refs'])} | "
        f"{assertion['assertion_type']} | {assertion['description']} |"
        for assertion in specification["assertions"]
    )
    return f"""[DP:SPEC] 当前验收规格

## 关联需求

{specification['requirement_ref']}

## 发布说明

{event['reason']}

## 验收场景

{scenarios}

## 检查责任

| CHK | 场景 | 类型 | 责任 | 必需 | 阻断 |
|---|---|---|---|---|---|
{checks}

## 原子断言

| AST | CHK | 结果引用 | 类型 | 描述 |
|---|---|---|---|---|
{assertions}

## 未决事项

{list_text(specification['open_questions'])}

{render_machine_block(event)}"""


def render_machine_block(event: dict[str, Any]) -> str:
    machine = yaml.safe_dump({"document_type": "deep_crew_delivery_event", "event": event}, allow_unicode=True, sort_keys=False).strip()
    return f"""<!-- DEEP_CREW_EVENT_START -->
```yaml
{machine}
```
<!-- DEEP_CREW_EVENT_END -->"""


def render_req(event: dict[str, Any]) -> str:
    requirement = event["requirement"]
    return f"""[DP:REQ] {requirement['id']} 当前需求

## 需求目标

{requirement['title']}

## 需求陈述

{requirement['statement']}

## 业务结果

{list_text(requirement['business_outcomes'])}

## 范围

### 范围内

{list_text(requirement['scope']['included'])}

### 范围外

{list_text(requirement['scope']['excluded'])}

## 约束与依赖

{list_text(requirement['constraints'])}

## 未决事项

{list_text(requirement['open_questions'])}

## 发布说明

{event['reason']}

{render_machine_block(event)}"""


def render(event: dict[str, Any]) -> str:
    if event["node"] == "REQ":
        return render_req(event)
    if event["node"] == "SPEC":
        return render_spec(event)
    if event["node"] == "IMPLEMENTATION":
        return render_implementation(event)
    if event["node"] == "ACCEPTANCE":
        return render_acceptance(event)
    raise EventError(f"无法渲染节点: {event['node']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="校验并准备 Deep Crew 交付事件评论")
    parser.add_argument("--event-file", required=True, type=Path)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--comments-json", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        event = parse_document(args.event_file.resolve())
        info = validate(event)
        duplicate = info["event_id"] in existing_event_ids(load_comments(args.comments_json))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output = args.output_dir / f"{info['event_id']}.md"
        output.write_text(render(event), encoding="utf-8")
        print(json.dumps({"issue": args.issue, "event_id": info["event_id"], "duplicate": duplicate, "comment_file": str(output.resolve())}, ensure_ascii=False, indent=2))
        return 0
    except (EventError, OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
