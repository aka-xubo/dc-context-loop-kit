#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

BLOCK_RE = re.compile(
    r"<!-- DEEP_CREW_EVENT_START -->\s*```yaml\s*(.*?)\s*```\s*<!-- DEEP_CREW_EVENT_END -->",
    re.DOTALL,
)
EVENT_ID_RE = re.compile(r"^EVT-[A-Za-z0-9_-]+$")
EVENT_ID_TEXT_RE = re.compile(r"event_id：`(EVT-[A-Za-z0-9_-]+)`")
SUBJECT_ID_RE = re.compile(r"^(SPEC|IMP|ACC)-[A-Za-z0-9_-]+$")
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
    require("requirement_ref" in specification, "specification 缺少字段: requirement_ref")
    require(isinstance(specification["requirement_ref"], str) and REQ_ID_RE.fullmatch(specification["requirement_ref"]), "specification.requirement_ref 必须为 REQ-*")
    if "changes" in specification:
        validate_specification_delta(specification)
        return
    ensure_keys(specification, {"requirement_ref", "scenarios", "checks", "assertions", "open_questions"}, "specification")
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


def validate_delta_scenario(scenario: Any, label: str) -> str:
    require(isinstance(scenario, dict), f"{label} 必须是对象")
    for field in ("id", "title", "business_result", "given", "when", "then", "delivery_surfaces"):
        require(field in scenario, f"{label} 缺少字段: {field}")
    require(isinstance(scenario["id"], str) and SCN_ID_RE.fullmatch(scenario["id"]), f"{label}.id 必须为 SCN-*")
    nonempty(scenario["title"], f"{label}.title")
    nonempty(scenario["business_result"], f"{label}.business_result")
    string_list(scenario["given"], f"{label}.given")
    nonempty(scenario["when"], f"{label}.when")
    require(isinstance(scenario["then"], list) and scenario["then"], f"{label}.then 必须是非空数组")
    string_list(scenario["delivery_surfaces"], f"{label}.delivery_surfaces")
    then_ids = []
    for index, outcome in enumerate(scenario["then"]):
        require(isinstance(outcome, dict), f"{label}.then[{index}] 必须是对象")
        require(isinstance(outcome.get("id"), str) and THEN_ID_RE.fullmatch(outcome["id"]), f"{label}.then[{index}].id 必须为 THEN-*")
        nonempty(outcome.get("statement"), f"{label}.then[{index}].statement")
        then_ids.append(outcome["id"])
    require(len(then_ids) == len(set(then_ids)), f"{label} 的 THEN ID 不能重复")
    return scenario["id"]


def validate_delta_check(check: Any, label: str) -> str:
    require(isinstance(check, dict), f"{label} 必须是对象")
    for field in ("id", "scenario_ids", "verification_type", "responsibility", "required", "blocking"):
        require(field in check, f"{label} 缺少字段: {field}")
    require(isinstance(check["id"], str) and CHK_ID_RE.fullmatch(check["id"]), f"{label}.id 必须为 CHK-*")
    require(isinstance(check["scenario_ids"], list) and check["scenario_ids"], f"{label}.scenario_ids 必须是非空数组")
    for scenario_id in check["scenario_ids"]:
        require(isinstance(scenario_id, str) and SCN_ID_RE.fullmatch(scenario_id), f"{label}.scenario_ids 包含非法 SCN ID")
    require(check["verification_type"] in {"unit", "api", "ui", "e2e"}, f"{label}.verification_type 非法")
    nonempty(check["responsibility"], f"{label}.responsibility")
    require(isinstance(check["required"], bool), f"{label}.required 必须是布尔值")
    require(isinstance(check["blocking"], bool), f"{label}.blocking 必须是布尔值")
    return check["id"]


def validate_delta_assertion(assertion: Any, label: str) -> str:
    require(isinstance(assertion, dict), f"{label} 必须是对象")
    for field in ("id", "check_id", "outcome_refs", "assertion_type", "description"):
        require(field in assertion, f"{label} 缺少字段: {field}")
    require(isinstance(assertion["id"], str) and AST_ID_RE.fullmatch(assertion["id"]), f"{label}.id 必须为 AST-*")
    require(isinstance(assertion["check_id"], str) and CHK_ID_RE.fullmatch(assertion["check_id"]), f"{label}.check_id 必须为 CHK-*")
    require(isinstance(assertion["outcome_refs"], list) and assertion["outcome_refs"], f"{label}.outcome_refs 必须是非空数组")
    for outcome_ref in assertion["outcome_refs"]:
        require(isinstance(outcome_ref, str) and re.fullmatch(r"SCN-[A-Za-z0-9_-]+\.THEN-[A-Za-z0-9_-]+", outcome_ref), f"{label}.outcome_refs 包含非法结果引用")
    require(assertion["assertion_type"] in {"semantic", "predicate"}, f"{label}.assertion_type 非法")
    nonempty(assertion["description"], f"{label}.description")
    return assertion["id"]


def validate_specification_delta(specification: dict[str, Any]) -> None:
    ensure_keys(specification, {"requirement_ref", "base_spec_ref", "changes", "open_questions"}, "specification")
    for field in ("base_spec_ref", "changes", "open_questions"):
        require(field in specification, f"增量 specification 缺少字段: {field}")
    require(isinstance(specification["base_spec_ref"], str) and re.fullmatch(r"SPEC-[A-Za-z0-9_-]+", specification["base_spec_ref"]), "specification.base_spec_ref 必须为 SPEC-*")
    string_list(specification["open_questions"], "specification.open_questions")
    changes = specification["changes"]
    require(isinstance(changes, dict), "specification.changes 必须是对象")
    ensure_keys(changes, {"added", "modified", "removed"}, "specification.changes")
    for kind in ("added", "modified", "removed"):
        require(kind in changes, f"specification.changes 缺少字段: {kind}")
        require(isinstance(changes[kind], dict), f"specification.changes.{kind} 必须是对象")
        ensure_keys(changes[kind], {"scenarios", "checks", "assertions"}, f"specification.changes.{kind}")
        for object_type in ("scenarios", "checks", "assertions"):
            require(object_type in changes[kind], f"specification.changes.{kind} 缺少字段: {object_type}")
            require(isinstance(changes[kind][object_type], list), f"specification.changes.{kind}.{object_type} 必须是数组")

    validators = {
        "scenarios": validate_delta_scenario,
        "checks": validate_delta_check,
        "assertions": validate_delta_assertion,
    }
    ids_by_kind: dict[str, set[str]] = {"added": set(), "modified": set(), "removed": set()}
    for kind in ("added", "modified"):
        for object_type, validator in validators.items():
            for index, item in enumerate(changes[kind][object_type]):
                label = f"specification.changes.{kind}.{object_type}[{index}]"
                object_id = validator(item, label)
                require(object_id not in ids_by_kind[kind], f"增量 {kind} 中 ID 不能重复: {object_id}")
                ids_by_kind[kind].add(object_id)

    removed_patterns = {"scenarios": SCN_ID_RE, "checks": CHK_ID_RE, "assertions": AST_ID_RE}
    for object_type, pattern in removed_patterns.items():
        for index, object_id in enumerate(changes["removed"][object_type]):
            label = f"specification.changes.removed.{object_type}[{index}]"
            require(isinstance(object_id, str) and pattern.fullmatch(object_id), f"{label} 必须为合法 ID")
            require(object_id not in ids_by_kind["removed"], f"增量 removed 中 ID 不能重复: {object_id}")
            ids_by_kind["removed"].add(object_id)

    require(any(ids_by_kind.values()), "增量 specification 至少需要一项变化")
    require(not (ids_by_kind["added"] & ids_by_kind["modified"]), "同一 ID 不能同时新增和修改")
    require(not (ids_by_kind["added"] & ids_by_kind["removed"]), "同一 ID 不能同时新增和删除")
    require(not (ids_by_kind["modified"] & ids_by_kind["removed"]), "同一 ID 不能同时修改和删除")


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
        "SPEC": common_fields | {"subject_id", "specification"},
        "IMPLEMENTATION": common_fields | {"subject_id", "implementation", "impact"},
        "ACCEPTANCE": common_fields | {"subject_id", "acceptance", "impact"},
    }
    ensure_keys(event, node_fields[node], "event")
    subject_id = event.get("subject_id")
    if node == "REQ":
        validate_requirement(event.get("requirement"))
        subject_id = None
    elif node == "SPEC":
        subject_id = nonempty(subject_id, "event.subject_id")
        require(SUBJECT_ID_RE.fullmatch(subject_id) is not None, "subject_id 格式非法")
        require(subject_id.startswith("SPEC-"), f"{node} 节点不能使用 subject_id: {subject_id}")
        validate_specification(event.get("specification"))
    else:
        subject_id = nonempty(subject_id, "event.subject_id")
        require(SUBJECT_ID_RE.fullmatch(subject_id) is not None, "subject_id 格式非法")
        require(subject_id.startswith("IMP-") if node == "IMPLEMENTATION" else subject_id.startswith("ACC-"), f"{node} 节点不能使用 subject_id: {subject_id}")
    if node == "IMPLEMENTATION":
        implementation = event.get("implementation")
        require(isinstance(implementation, dict), "IMPLEMENTATION 缺少完成交付对象")
        require(implementation.get("status") == "READY", "IMPLEMENTATION status 必须为 READY")
        for field in ("requirement_ref", "spec_refs", "summary", "completed_items", "change_surface", "development_checks", "known_limits", "repository", "git_commit"):
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
        validate_repository(implementation["repository"], "implementation.repository")
        require(isinstance(implementation["git_commit"], str) and GIT_COMMIT_RE.fullmatch(implementation["git_commit"]), "implementation.git_commit 必须是完整 Git commit")
        review = implementation.get("completion_review")
        require(isinstance(review, dict), "IMPLEMENTATION 缺少 completion_review")
        if isinstance(review, dict):
            require(review.get("status") == "PASSED", "completion_review.status 必须为 PASSED")
            require(review.get("performed_after_self_test") is True, "completion_review.performed_after_self_test 必须为 true")
            for key in ("preflight", "program", "semantic"):
                require(isinstance(review.get(key), dict), f"completion_review.{key} 必须是对象")
            preflight = review.get("preflight", {})
            require(preflight.get("status") == "PASSED", "completion_review.preflight.status 必须为 PASSED")
            require(isinstance(preflight.get("report"), str) and preflight["report"].strip(), "completion_review.preflight.report 必须非空")
            program = review.get("program", {})
            require(program.get("status") == "PASSED", "completion_review.program.status 必须为 PASSED")
            require(isinstance(program.get("command"), str) and program["command"].strip(), "completion_review.program.command 必须非空")
            require(isinstance(program.get("report"), str) and program["report"].strip(), "completion_review.program.report 必须非空")
            require(program.get("findings") == [], "completion_review.program.findings 必须为空")
            semantic = review.get("semantic", {})
            require(semantic.get("status") == "PASSED", "completion_review.semantic.status 必须为 PASSED")
            require(isinstance(semantic.get("reviewed_assertions"), list) and semantic["reviewed_assertions"], "completion_review.semantic.reviewed_assertions 必须为非空数组")
            require(semantic.get("findings") == [], "completion_review.semantic.findings 必须为空")
            implementation_assertions = {value for value in implementation.get("spec_refs", []) if isinstance(value, str) and value.startswith("AST-")}
            require(implementation_assertions.issubset(set(semantic.get("reviewed_assertions", []))), "completion_review.semantic 必须覆盖 implementation.spec_refs 中的全部 AST")
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
        for field in ("requirement_ref", "spec_refs", "implementation_refs", "mode", "scope_refs", "req_completion_impact", "repository", "git_commit", "runs", "artifacts", "assertion_results", "reason"):
            require(field in acceptance, f"ACCEPTANCE 缺少字段: {field}")
        nonempty(acceptance["reason"], "acceptance.reason")
        validate_repository(acceptance["repository"], "acceptance.repository")
        require(isinstance(acceptance["git_commit"], str) and GIT_COMMIT_RE.fullmatch(acceptance["git_commit"]), "acceptance.git_commit 必须是完整 Git commit")
        require(isinstance(acceptance["spec_refs"], list), "acceptance.spec_refs 必须是数组")
        require(isinstance(acceptance["implementation_refs"], list), "acceptance.implementation_refs 必须是数组")
        for value in acceptance["spec_refs"]:
            require(isinstance(value, str) and re.fullmatch(r"(SCN|CHK|AST)-[A-Za-z0-9_-]+", value), f"acceptance.spec_refs 非法: {value}")
        for value in acceptance["implementation_refs"]:
            require(isinstance(value, str) and re.fullmatch(r"IMP-[A-Za-z0-9_-]+", value), f"acceptance.implementation_refs 非法: {value}")
        require(acceptance["mode"] in {"targeted", "full"}, "acceptance.mode 必须为 targeted 或 full")
        scope_refs = acceptance["scope_refs"]
        require(isinstance(scope_refs, dict), "acceptance.scope_refs 必须是对象")
        ensure_keys(scope_refs, {"scenarios", "checks", "assertions"}, "acceptance.scope_refs")
        for key, pattern in (("scenarios", SCN_ID_RE), ("checks", CHK_ID_RE), ("assertions", AST_ID_RE)):
            require(isinstance(scope_refs.get(key), list) and scope_refs[key], f"acceptance.scope_refs.{key} 必须是非空数组")
            for value in scope_refs[key]:
                require(isinstance(value, str) and pattern.fullmatch(value), f"acceptance.scope_refs.{key} 包含非法 ID: {value}")
        require(acceptance["req_completion_impact"] in {"NONE", "ELIGIBLE"}, "acceptance.req_completion_impact 必须为 NONE 或 ELIGIBLE")
        if acceptance["mode"] == "targeted":
            require(len(acceptance["implementation_refs"]) == 1, "targeted 验收必须且只能引用一个 IMP")
            require(acceptance["req_completion_impact"] == "NONE", "targeted 验收的 req_completion_impact 必须为 NONE")
        elif acceptance["status"] == "SATISFIED":
            require(acceptance["req_completion_impact"] == "ELIGIBLE", "full 验收 SATISFIED 时 req_completion_impact 必须为 ELIGIBLE")
        else:
            require(acceptance["req_completion_impact"] == "NONE", "未通过的 full 验收 req_completion_impact 必须为 NONE")
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


def validate_repository(value: Any, label: str) -> None:
    require(isinstance(value, dict), f"{label} 必须是对象")
    ensure_keys(value, {"worktree_root", "git_toplevel"}, label)
    nonempty(value.get("worktree_root"), f"{label}.worktree_root")
    nonempty(value.get("git_toplevel"), f"{label}.git_toplevel")


def verify_git_binding(event: dict[str, Any]) -> None:
    if event["node"] == "IMPLEMENTATION":
        result = event["implementation"]
    elif event["node"] == "ACCEPTANCE":
        result = event["acceptance"]
    else:
        return
    repository = result["repository"]
    worktree = repository["worktree_root"]

    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", worktree, *args],
            check=False,
            capture_output=True,
            text=True,
        )
        require(completed.returncode == 0, f"Git 校验失败（{worktree}）：{completed.stderr.strip() or completed.stdout.strip()}")
        return completed.stdout.strip()

    top_level = git("rev-parse", "--show-toplevel")
    expected_top_level = str(Path(repository["git_toplevel"]).resolve())
    actual_top_level = str(Path(top_level).resolve())
    require(actual_top_level == expected_top_level, f"repository.git_toplevel 与 Git 实际根目录不一致: {top_level}")
    commit = result["git_commit"]
    require(len(commit) == 40, "Git 绑定校验要求 40 位完整 commit")
    git("cat-file", "-e", f"{commit}^{{commit}}")
    head = git("rev-parse", "HEAD")
    require(head == commit, f"事件 git_commit 与当前 HEAD 不一致: HEAD={head}")
    status = subprocess.run(
        ["git", "-C", worktree, "status", "--porcelain", "--untracked-files=no"],
        check=False,
        capture_output=True,
        text=True,
    )
    require(status.returncode == 0, f"无法读取 Git 工作区状态: {status.stderr.strip()}")
    require(not status.stdout.strip(), "目标 Git 仓库存在未提交的 tracked 修改")


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
        if match:
            try:
                data = yaml.safe_load(match.group(1))
                event = data.get("event", {}) if isinstance(data, dict) else {}
                if isinstance(event, dict) and isinstance(event.get("event_id"), str):
                    found.add(event["event_id"])
                    continue
            except yaml.YAMLError:
                pass
        text_match = EVENT_ID_TEXT_RE.search(str(item.get("content", "")))
        if text_match:
            found.add(text_match.group(1))
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
    review = implementation["completion_review"]
    semantic = review["semantic"]
    reviewed = ", ".join(semantic["reviewed_assertions"])
    actions = "\n".join(f"- {item['action']}：{item['owner']}" for item in impact["next_actions"]) or "- 待分析"
    return f"""[DP:IMPLEMENTATION] {event['subject_id']} 实现完成

## 交付摘要

{implementation['summary']}

## 绑定上下文

- 状态：{implementation['status']}
- 需求：{implementation['requirement_ref']}
- 规格：{', '.join(implementation['spec_refs']) or '无'}
- 实现工作树：{implementation['repository']['worktree_root']}
- Git 根目录：{implementation['repository']['git_toplevel']}
- Git commit：{implementation['git_commit']}

## 已完成内容

{completed}

{render_change_surface(implementation['change_surface'], '实际变更面')}

## 开发检查

| 命令 | 结果 | 摘要 |
|---|---|---|
{checks}

## 完成前复核

- 复核时机：自测之后、固定 commit 和发布 READY 之前
- 自测前覆盖预检：{review['preflight']['status']}（报告：{review['preflight']['report']}）
- 程序化完成复核：{review['program']['status']}（命令：`{review['program']['command']}`；报告：{review['program']['report']}）
- Agent 语义完成复核：{review['semantic']['status']}（已复核 AST：{reviewed}）

## 已知限制

{list_text(implementation['known_limits'])}

## 影响范围

- 受影响对象：{', '.join(impact['affected_ids']) if impact['affected_ids'] else '无'}

## 下一步

{actions}

{render_machine_block(event)}"""


def render_acceptance(event: dict[str, Any]) -> str:
    acceptance = event["acceptance"]
    mode_label = "单次验收" if acceptance["mode"] == "targeted" else "全量验收"
    target = ", ".join(acceptance["implementation_refs"]) if acceptance["mode"] == "targeted" else "当前有效 SPEC"
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
    return f"""[DP:ACCEPTANCE] {event['subject_id']} · {mode_label} · {target} 验收结论

## 验收基线

- 需求：{acceptance['requirement_ref']}
- 规格：{', '.join(acceptance['spec_refs']) or '无'}
- 实现：{', '.join(acceptance['implementation_refs']) or '无'}
- 实现工作树：{acceptance['repository']['worktree_root']}
- Git 根目录：{acceptance['repository']['git_toplevel']}
- Git commit：{acceptance['git_commit'] or '无'}

## 验收范围

- 模式：`{acceptance['mode']}`（{mode_label}）
- 目标：{target}
- 场景：{', '.join(acceptance['scope_refs']['scenarios'])}
- 检查：{', '.join(acceptance['scope_refs']['checks'])}
- 断言：{', '.join(acceptance['scope_refs']['assertions'])}
- REQ 完成资格：{'可影响整个 REQ' if acceptance['req_completion_impact'] == 'ELIGIBLE' else '仅影响本次验收切片'}

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
    def markdown_cell(value: Any) -> str:
        return display(value).replace("|", "\\|").replace("\n", " ")

    def scenario_table(items: list[dict[str, Any]]) -> str:
        if not items:
            return "无"
        rows = ["| SCN | 标题 | 业务结果 | Given | When | Then | 交付面 |", "|---|---|---|---|---|---|---|"]
        for item in items:
            given = "；".join(item.get("given", [])) or "无"
            then = "；".join(f"{outcome['id']} {outcome['statement']}" for outcome in item.get("then", [])) or "无"
            rows.append(
                f"| `{item['id']}` | {markdown_cell(item['title'])} | {markdown_cell(item['business_result'])} | "
                f"{markdown_cell(given)} | {markdown_cell(item['when'])} | {markdown_cell(then)} | "
                f"{markdown_cell(', '.join(item.get('delivery_surfaces', [])) or '无')} |"
            )
        return "\n".join(rows)

    if "changes" in specification:
        changes = specification["changes"]
        def ids_or_none(items: list[Any]) -> str:
            return "、".join(item if isinstance(item, str) else item.get("id", "") for item in items) or "无"
        def objects_text(object_type: str, items: list[dict[str, Any]]) -> str:
            if not items:
                return "无"
            if object_type == "scenarios":
                return scenario_table(items)
            if object_type == "checks":
                return "\n".join(
                    f"| `{item['id']}` | {', '.join(item['scenario_ids'])} | {item['verification_type']} | {item['responsibility']} | "
                    f"{'是' if item['required'] else '否'} | {'是' if item['blocking'] else '否'} |"
                    for item in items
                )
            return "\n".join(
                f"| `{item['id']}` | {item['check_id']} | {', '.join(item['outcome_refs'])} | "
                f"{item['assertion_type']} | {item['description']} |"
                for item in items
            )

        added = changes["added"]
        modified = changes["modified"]
        removed = changes["removed"]
        return f"""[DP:SPEC] {event['subject_id']} 验收规格增量

## 关联需求

{specification['requirement_ref']}

## 基础 SPEC

{specification['base_spec_ref']}

## 发布说明

{event['reason']}

## 新增

### 场景

{scenario_table(added['scenarios'])}

### 检查责任

| CHK | 场景 | 类型 | 责任 | 必需 | 阻断 |
|---|---|---|---|---|---|
{objects_text('checks', added['checks'])}

### 原子断言

| AST | CHK | 结果引用 | 类型 | 描述 |
|---|---|---|---|---|
{objects_text('assertions', added['assertions'])}

## 修改

### 场景

{scenario_table(modified['scenarios'])}

### 检查责任

| CHK | 场景 | 类型 | 责任 | 必需 | 阻断 |
|---|---|---|---|---|---|
{objects_text('checks', modified['checks'])}

### 原子断言

| AST | CHK | 结果引用 | 类型 | 描述 |
|---|---|---|---|---|
{objects_text('assertions', modified['assertions'])}

## 删除

- 场景：{ids_or_none(removed['scenarios'])}
- 检查：{ids_or_none(removed['checks'])}
- 断言：{ids_or_none(removed['assertions'])}

## 未决事项

{list_text(specification['open_questions'])}

{render_machine_block(event)}"""
    scenarios = scenario_table(specification["scenarios"])
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
    return f"""[DP:SPEC] {event['subject_id']} 当前验收规格

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


def event_attachment_filename(event: dict[str, Any]) -> str:
    subject_id = event.get("subject_id") or event["requirement"]["id"]
    return f"{subject_id}-事件.yaml"


def render_machine_block(event: dict[str, Any]) -> str:
    filename = event_attachment_filename(event)
    return f"""## 机器事件附件

- event_id：`{event['event_id']}`
- YAML 附件：`{filename}`
- 解析方式：从 Issue comment 附件下载并解析该 YAML；评论正文不内嵌机器 YAML。"""


def ensure_output_not_legacy_drafts(output_dir: Path) -> None:
    """事件评论和附件不得写入长期 drafts 目录。"""
    resolved = output_dir.expanduser().resolve()
    parts = resolved.parts
    marker = (".local", "dc-loop", "drafts")
    for index in range(len(parts) - len(marker) + 1):
        if parts[index:index + len(marker)] == marker:
            raise EventError("事件输出目录不得位于 .local/dc-loop/drafts；请使用本次 operation workspace")


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
    parser.add_argument("--verify-git", action="store_true", help="验证事件仓库路径、commit、HEAD 和 tracked 工作区状态")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        event = parse_document(args.event_file.resolve())
        info = validate(event)
        if args.verify_git:
            verify_git_binding(event)
        duplicate = info["event_id"] in existing_event_ids(load_comments(args.comments_json))
        ensure_output_not_legacy_drafts(args.output_dir)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output = args.output_dir / f"{info['event_id']}.md"
        attachment = args.output_dir / event_attachment_filename(event)
        machine = yaml.safe_dump({"document_type": "deep_crew_delivery_event", "event": event}, allow_unicode=True, sort_keys=False)
        attachment.write_text(machine, encoding="utf-8")
        output.write_text(render(event), encoding="utf-8")
        print(json.dumps({"issue": args.issue, "event_id": info["event_id"], "duplicate": duplicate, "comment_file": str(output.resolve()), "attachment_file": str(attachment.resolve())}, ensure_ascii=False, indent=2))
        return 0
    except (EventError, OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
