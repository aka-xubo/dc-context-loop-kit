#!/usr/bin/env python3
"""Validate the current REQ-first Delivery Proof documents."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from req_model import (
    ART_RE,
    AST_RE,
    CHK_RE,
    DEP_RE,
    REQ_RE,
    RUN_RE,
    SCN_RE,
    ModelError,
    discover_current_requirement_documents,
    extract_document,
    requirement_digest,
    scoped_document_digest,
)

RUN_PHASES = {
    "unit_verification",
    "app_start",
    "api_verification",
    "ui_verification",
    "regression",
    "cleanup",
}
VERIFICATION_TYPES = {"unit", "api", "ui", "e2e"}
ARTIFACT_TYPES = {"command_output", "api_exchange", "state_observation", "screenshot"}
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
PROVIDER_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
TEXT_LOCATOR_RE = re.compile(r"^(?:line|output|request|response|observed):([1-9][0-9]*)$")
ARTIFACT_EVIDENCE_STATUSES = {"PASSED", "FAILED", "BLOCKED"}
ASSERTION_TYPES = {"semantic", "predicate"}
IMPLEMENTATION_PLAN_STATUSES = {"PLANNED", "IN_PROGRESS", "READY"}
IMPLEMENTATION_SLICE_KINDS = {"behavior_slice", "engineering_slice", "readiness_slice"}
IMPLEMENTATION_SLICE_STATUSES = {"PLANNED", "IN_PROGRESS", "COMPLETED", "BLOCKED"}
TDD_EXEMPTION_KINDS = {"engineering_setup", "external_e2e", "visual_static", "no_stable_interface"}
IMPLEMENTATION_RISK_CATEGORIES = {"database_migration", "public_api", "auth_security", "data_compatibility", "irreversible_change", "acceptance_observation"}
PREDICATE_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "contains"}
EXPRESSION_OPERATIONS = {"add", "subtract", "multiply", "divide", "count"}
FACT_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")


@dataclass
class Validation:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def require(self, condition: bool, path: Path, message: str) -> None:
        if not condition:
            self.errors.append(f"{path}: {message}")

    def warn(self, condition: bool, path: Path, message: str) -> None:
        if not condition:
            self.warnings.append(f"{path}: {message}")


@dataclass
class Project:
    root: Path
    validation: Validation
    requirements: dict[str, dict[str, Any]] = field(default_factory=dict)
    requirement_paths: dict[str, Path] = field(default_factory=dict)
    scenarios: dict[str, dict[str, Any]] = field(default_factory=dict)
    scenario_paths: dict[str, Path] = field(default_factory=dict)
    matrices: dict[str, dict[str, Any]] = field(default_factory=dict)
    matrix_paths: dict[str, Path] = field(default_factory=dict)
    plans: dict[str, dict[str, Any]] = field(default_factory=dict)
    evidence: dict[str, dict[str, Any]] = field(default_factory=dict)
    reports: dict[str, dict[str, Any]] = field(default_factory=dict)


def is_nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_operand(operand: Any, path: Path, label: str, validation: Validation, depth: int = 0) -> None:
    item = as_dict(operand)
    validation.require(depth <= 8, path, f"{label} 表达式嵌套超过 8 层")
    if depth > 8:
        return
    variants = [key for key in ("fact", "value", "operation") if key in item]
    validation.require(len(variants) == 1, path, f"{label} 必须且只能使用 fact、value 或 operation")
    if len(variants) != 1:
        return
    variant = variants[0]
    if variant == "fact":
        validation.require(set(item) == {"fact"}, path, f"{label}.fact 包含未定义字段")
        validation.require(isinstance(item.get("fact"), str) and FACT_NAME_RE.fullmatch(item["fact"]) is not None, path, f"{label}.fact 格式非法")
        return
    if variant == "value":
        validation.require(set(item) == {"value"}, path, f"{label}.value 包含未定义字段")
        return
    validation.require(set(item) == {"operation", "operands"}, path, f"{label}.operation 必须包含且只包含 operation、operands")
    operation = item.get("operation")
    operands = as_list(item.get("operands"))
    validation.require(operation in EXPRESSION_OPERATIONS, path, f"{label}.operation 非法")
    validation.require(isinstance(item.get("operands"), list) and bool(operands), path, f"{label}.operands 必须是非空数组")
    if operation in {"subtract", "divide"}:
        validation.require(len(operands) == 2, path, f"{label}.{operation} 必须有两个操作数")
    if operation == "count":
        validation.require(len(operands) == 1, path, f"{label}.count 必须有一个操作数")
    for index, child in enumerate(operands):
        validate_operand(child, path, f"{label}.operands[{index}]", validation, depth + 1)


def validate_predicate(predicate: Any, path: Path, label: str, validation: Validation) -> None:
    item = as_dict(predicate)
    validation.require(set(item) <= {"operator", "left", "right", "unit"}, path, f"{label} 包含未定义字段")
    validation.require(set(item) >= {"operator", "left", "right"}, path, f"{label} 必须包含 operator、left、right")
    validation.require(item.get("operator") in PREDICATE_OPERATORS, path, f"{label}.operator 非法")
    if "unit" in item:
        validation.require(is_nonempty(item.get("unit")), path, f"{label}.unit 不能为空")
    validate_operand(item.get("left"), path, f"{label}.left", validation)
    validate_operand(item.get("right"), path, f"{label}.right", validation)


def evaluate_operand(operand: Any, observations: dict[str, Any]) -> Any:
    item = as_dict(operand)
    if "fact" in item:
        fact = str(item["fact"])
        if fact not in observations:
            raise ValueError(f"缺少事实值 {fact}")
        return observations[fact]
    if "value" in item:
        return item["value"]
    operation = item.get("operation")
    values = [evaluate_operand(child, observations) for child in as_list(item.get("operands"))]
    if operation == "count":
        if not isinstance(values[0], (list, dict, str)):
            raise ValueError("count 只支持数组、对象或字符串")
        return len(values[0])
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
        raise ValueError(f"{operation} 只支持数值")
    if operation == "add":
        return sum(values)
    if operation == "subtract":
        return values[0] - values[1]
    if operation == "multiply":
        result = 1
        for value in values:
            result *= value
        return result
    if operation == "divide":
        if values[1] == 0:
            raise ValueError("divide 的除数不能为 0")
        return values[0] / values[1]
    raise ValueError(f"未知表达式操作 {operation}")


def evaluate_predicate(predicate: Any, observations: dict[str, Any]) -> bool:
    item = as_dict(predicate)
    left = evaluate_operand(item.get("left"), observations)
    right = evaluate_operand(item.get("right"), observations)
    operator = item.get("operator")
    if operator == "eq": return left == right
    if operator == "ne": return left != right
    if operator == "gt": return left > right
    if operator == "gte": return left >= right
    if operator == "lt": return left < right
    if operator == "lte": return left <= right
    if operator == "in": return left in right
    if operator == "not_in": return left not in right
    if operator == "contains": return right in left
    raise ValueError(f"未知断言运算符 {operator}")


def is_full_git_commit(value: Any) -> bool:
    return isinstance(value, str) and GIT_COMMIT_RE.fullmatch(value) is not None


def git_commit_exists(start: Path, commit: Any) -> bool:
    if not is_full_git_commit(commit):
        return False
    cursor = start.resolve()
    for candidate in (cursor, *cursor.parents):
        if not (candidate / ".git").exists():
            continue
        try:
            result = subprocess.run(
                ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
                cwd=candidate,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError:
            return False
        return result.returncode == 0
    return False


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def validate_external_verification(value: Any, path: Path, label: str, validation: Validation) -> None:
    if value is None:
        return
    external = as_dict(value)
    validation.require(isinstance(value, dict), path, f"{label} 必须是 null 或对象")
    provider = external.get("provider")
    validation.require(is_nonempty(provider), path, f"{label}.provider 不能为空")
    validation.require(isinstance(provider, str) and PROVIDER_RE.fullmatch(provider) is not None, path, f"{label}.provider 必须是稳定的小写标识")
    validation.require(external.get("mode") in {"stub", "contract", "real_test_app"}, path, f"{label}.mode 非法")


def external_signature(value: Any) -> tuple[str, str] | None:
    external = as_dict(value)
    provider = external.get("provider")
    mode = external.get("mode")
    if not isinstance(provider, str) or not isinstance(mode, str):
        return None
    return provider, mode


def evidence_requirements(value: Any, path: Path, label: str, validation: Validation) -> list[str]:
    if value is None:
        return []
    requirements = as_dict(value)
    validation.require(isinstance(value, dict), path, f"{label} 必须是对象")
    required_types = requirements.get("required_artifact_types", [])
    validation.require(isinstance(required_types, list), path, f"{label}.required_artifact_types 必须是数组")
    validation.require(
        all(isinstance(item, str) and item in ARTIFACT_TYPES for item in as_list(required_types)),
        path,
        f"{label}.required_artifact_types 包含非法 ART 类型",
    )
    validation.require(
        len(required_types) == len(set(map(str, required_types))),
        path,
        f"{label}.required_artifact_types 不能重复",
    )
    return [str(item) for item in as_list(required_types)]


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def unique_ids(items: Iterable[Any], pattern: Any, path: Path, label: str, validation: Validation) -> set[str]:
    result: set[str] = set()
    for index, raw in enumerate(items):
        item_id = as_dict(raw).get("id")
        validation.require(
            isinstance(item_id, str) and pattern.fullmatch(item_id) is not None,
            path,
            f"{label}[{index}].id 格式非法",
        )
        if isinstance(item_id, str):
            validation.require(item_id not in result, path, f"{label} ID 重复: {item_id}")
            result.add(item_id)
    return result


def current_definition_digests(project: Project, requirement_id: str) -> dict[str, str]:
    requirement = project.requirements[requirement_id]
    scenarios = project.scenarios.get(requirement_id, {})
    matrix = project.matrices.get(requirement_id, {})
    return {
        "requirement": requirement_digest(as_dict(requirement.get("requirement"))),
        "scenarios": scoped_document_digest(scenarios, "acceptance_scenarios", "sha256") if scenarios else "",
        "matrix": scoped_document_digest(matrix, "acceptance_matrix", "sha256") if matrix else "",
    }


def confirmable_status(document: dict[str, Any], scope_key: str, path: Path, validation: Validation) -> None:
    scope = as_dict(document.get(scope_key))
    status = scope.get("status")
    confirmation = scope.get("confirmation")
    validation.require(status in {"DRAFT", "CONFIRMED"}, path, f"{scope_key}.status 只允许 DRAFT/CONFIRMED")
    if status == "DRAFT":
        validation.require(confirmation is None, path, f"{scope_key} 为 DRAFT 时 confirmation 必须为 null")
        return
    if confirmation is None:
        return
    validation.require(isinstance(confirmation, dict), path, f"{scope_key} 的 confirmation 必须为 null 或对象")
    if not isinstance(confirmation, dict):
        return
    validation.require(is_nonempty(confirmation.get("confirmed_by")), path, "confirmation.confirmed_by 不能为空")
    validation.require(is_nonempty(confirmation.get("confirmed_at")), path, "confirmation.confirmed_at 不能为空")
    expected = scoped_document_digest(document, scope_key, "sha256")
    validation.require(confirmation.get("content_digest") == expected, path, f"confirmation.content_digest 与当前内容不一致，应为 {expected}")


def resolve_root(target: Path) -> tuple[Path, str | None]:
    target = target.resolve()
    cursor = target.parent if target.is_file() else target
    if cursor.name.startswith("REQ-") and (cursor / "需求.md").is_file():
        return cursor.parent, cursor.name
    for candidate in (cursor, *cursor.parents):
        if any(candidate.glob("REQ-*/需求.md")):
            return candidate, None
    return cursor, None


def load(path: Path, expected_type: str, validation: Validation) -> dict[str, Any] | None:
    try:
        return extract_document(path, expected_type)
    except (ModelError, OSError) as error:
        validation.errors.append(str(error))
        return None


def load_project(root: Path) -> Project:
    validation = Validation()
    project = Project(root=root, validation=validation)
    discovered = discover_current_requirement_documents(root)
    validation.require(bool(discovered), root, "未发现 REQ-*/需求.md")
    for requirement_id, requirement_path in discovered.items():
        document = load(requirement_path, "requirement", validation)
        if document is None:
            continue
        project.requirements[requirement_id] = document
        project.requirement_paths[requirement_id] = requirement_path
        validate_requirement(project, requirement_id, document, requirement_path)
        req_root = requirement_path.parent
        for filename, expected_type, target, validator in (
            ("验收场景.md", "acceptance_scenarios", project.scenarios, validate_scenarios),
            ("验收矩阵.md", "acceptance_matrix", project.matrices, validate_matrix),
            ("实现计划.md", "implementation_plan", project.plans, validate_plan),
            ("测试证据.md", "test_evidence", project.evidence, validate_evidence),
            ("验收报告.md", "acceptance_report", project.reports, validate_report),
        ):
            path = req_root / filename
            if not path.exists():
                continue
            loaded = load(path, expected_type, validation)
            if loaded is None:
                continue
            target[requirement_id] = loaded
            if expected_type == "acceptance_scenarios":
                project.scenario_paths[requirement_id] = path
            elif expected_type == "acceptance_matrix":
                project.matrix_paths[requirement_id] = path
            validator(project, requirement_id, loaded, path)
    validate_dependencies(project)
    return project


def validate_requirement(project: Project, requirement_id: str, document: dict[str, Any], path: Path) -> None:
    v = project.validation
    requirement = as_dict(document.get("requirement"))
    allowed_keys = {"id", "status", "title", "statement", "business_value", "scope", "dependencies", "source_refs", "confirmation"}
    v.require(set(requirement) == allowed_keys, path, "requirement 包含缺失或未定义字段")
    v.require(REQ_RE.fullmatch(str(requirement.get("id", ""))) is not None, path, "requirement.id 格式非法")
    v.require(requirement.get("id") == requirement_id, path, "requirement.id 与目录不一致")
    v.require(requirement.get("status") in {"DRAFT", "CONFIRMED", "SATISFIED"}, path, "requirement.status 只允许 DRAFT/CONFIRMED/SATISFIED")
    for key in ("title", "statement", "business_value"):
        v.require(is_nonempty(requirement.get(key)), path, f"requirement.{key} 不能为空")
    scope = as_dict(requirement.get("scope"))
    v.require(isinstance(scope.get("included"), list), path, "requirement.scope.included 必须是数组")
    v.require(isinstance(scope.get("excluded"), list), path, "requirement.scope.excluded 必须是数组")
    v.require(isinstance(requirement.get("dependencies"), list), path, "requirement.dependencies 必须是数组")
    v.require(isinstance(requirement.get("source_refs"), list), path, "requirement.source_refs 必须是数组")
    status = requirement.get("status")
    confirmation = requirement.get("confirmation")
    if status == "DRAFT":
        v.require(confirmation is None, path, "DRAFT REQ 的 confirmation 必须为 null")
    else:
        v.require(isinstance(confirmation, dict), path, f"{status} REQ 必须有 confirmation")
        if isinstance(confirmation, dict):
            expected = requirement_digest(requirement)
            v.require(confirmation.get("content_digest") == expected, path, f"REQ 确认摘要不一致，应为 {expected}")


def validate_requirement_ref(document: dict[str, Any], requirement_id: str, path: Path, validation: Validation) -> None:
    ref = as_dict(document.get("requirement_ref"))
    validation.require(ref == {"requirement_id": requirement_id}, path, "requirement_ref 与所在 REQ 目录不一致")


def validate_scenarios(project: Project, requirement_id: str, document: dict[str, Any], path: Path) -> None:
    v = project.validation
    validate_requirement_ref(document, requirement_id, path, v)
    scope = as_dict(document.get("acceptance_scenarios"))
    confirmable_status(document, "acceptance_scenarios", path, v)
    v.require(set(scope) == {"status", "scenarios", "open_questions", "confirmation"}, path, "acceptance_scenarios 包含缺失或未定义字段")
    v.require(isinstance(scope.get("open_questions"), list), path, "acceptance_scenarios.open_questions 必须是数组")
    scenarios = as_list(scope.get("scenarios"))
    v.require(bool(scenarios), path, "场景集合不能为空")
    unique_ids(scenarios, SCN_RE, path, "scenarios", v)
    allowed_keys = {"id", "title", "business_result", "participants", "preconditions", "action", "expected_outcomes", "given", "when", "then", "protected_invariants", "delivery_surfaces", "ontology_refs", "source_refs"}
    for scenario in scenarios:
        item = as_dict(scenario)
        v.require(set(item) <= allowed_keys, path, f"{item.get('id')} 包含未定义字段")
        for key in ("title", "business_result"):
            v.require(is_nonempty(item.get(key)), path, f"{item.get('id')}.{key} 不能为空")
        gherkin_fields = {"given", "when", "then"} & set(item)
        if gherkin_fields:
            v.require(gherkin_fields == {"given", "when", "then"}, path, f"{item.get('id')} 的 Gherkin 字段必须同时包含 given、when、then")
            v.require(bool(as_list(item.get("given"))), path, f"{item.get('id')}.given 至少需要一个前置条件")
            v.require(is_nonempty(item.get("when")), path, f"{item.get('id')}.when 不能为空")
            outcomes = as_list(item.get("then"))
            v.require(bool(outcomes), path, f"{item.get('id')}.then 至少需要一个结果")
            unique_ids(outcomes, re.compile(r"^THEN-[A-Za-z0-9_-]+$"), path, f"{item.get('id')}.then", v)
            for outcome in outcomes:
                outcome_item = as_dict(outcome)
                v.require(set(outcome_item) <= {"id", "statement"}, path, f"{item.get('id')} 的 Then 包含未定义字段")
                v.require(is_nonempty(outcome_item.get("statement")), path, f"{item.get('id')}.{outcome_item.get('id')}.statement 不能为空")
        else:
            v.require(is_nonempty(item.get("action")), path, f"{item.get('id')}.action 不能为空")
            v.require(bool(as_list(item.get("expected_outcomes"))), path, f"{item.get('id')} 至少需要一个 expected_outcome")


def validate_matrix(project: Project, requirement_id: str, document: dict[str, Any], path: Path) -> None:
    v = project.validation
    validate_requirement_ref(document, requirement_id, path, v)
    scope = as_dict(document.get("acceptance_matrix"))
    confirmable_status(document, "acceptance_matrix", path, v)
    scenario_doc = project.scenarios.get(requirement_id)
    v.require(scenario_doc is not None, path, "验收矩阵缺少当前验收场景")
    scenarios = as_list(as_dict((scenario_doc or {}).get("acceptance_scenarios")).get("scenarios"))
    scenario_by_id = {str(item.get("id")): item for item in scenarios if isinstance(item, dict)}
    scenario_ids = set(scenario_by_id)
    gherkin_outcomes = {
        f"{scenario_id}.{as_dict(outcome).get('id')}"
        for scenario_id, scenario in scenario_by_id.items()
        for outcome in as_list(as_dict(scenario).get("then"))
        if as_dict(outcome).get("id")
    }
    covered_outcomes: set[str] = set()
    checks = as_list(scope.get("checks"))
    v.require(bool(checks), path, "验收矩阵至少需要一个 CHK")
    unique_ids(checks, CHK_RE, path, "checks", v)
    assertion_ids: set[str] = set()
    for check in checks:
        item = as_dict(check)
        v.require("delivery_surfaces" not in item, path, f"{item.get('id')} 不应重复定义 delivery_surfaces，请在 SCN 中定义")
        v.require(item.get("verification_type") in VERIFICATION_TYPES, path, f"{item.get('id')}.verification_type 非法")
        v.require(is_nonempty(item.get("responsibility")), path, f"{item.get('id')}.responsibility 不能为空")
        v.require(isinstance(item.get("required"), bool), path, f"{item.get('id')}.required 必须是布尔值")
        v.require(isinstance(item.get("blocking"), bool), path, f"{item.get('id')}.blocking 必须是布尔值")
        evidence_requirements(item.get("evidence_requirements"), path, f"{item.get('id')}.evidence_requirements", v)
        v.require(isinstance(item.get("dependency_ids"), list), path, f"{item.get('id')}.dependency_ids 必须是数组")
        dependency_refs = as_list(item.get("dependency_ids"))
        v.require(len(dependency_refs) == len(set(map(str, dependency_refs))), path, f"{item.get('id')}.dependency_ids 不能重复")
        refs = as_list(item.get("scenario_ids"))
        v.require(bool(refs), path, f"{item.get('id')} 至少引用一个 SCN")
        for ref in refs:
            v.require(ref in scenario_ids, path, f"{item.get('id')} 引用了不存在的 SCN: {ref}")
        current = unique_ids(as_list(item.get("assertions")), AST_RE, path, f"{item.get('id')}.assertions", v)
        v.require(bool(current), path, f"{item.get('id')} 至少需要一条 AST")
        for assertion in as_list(item.get("assertions")):
            assertion_item = as_dict(assertion)
            assertion_id = assertion_item.get("id")
            assertion_type = assertion_item.get("assertion_type", "semantic")
            v.require(set(assertion_item) <= {"id", "description", "assertion_type", "ontology_refs", "predicate", "outcome_refs"}, path, f"{assertion_id} 包含未定义字段")
            v.require(is_nonempty(assertion_item.get("description")), path, f"{assertion_id}.description 不能为空")
            v.require(assertion_type in ASSERTION_TYPES, path, f"{assertion_id}.assertion_type 非法")
            ontology_refs = assertion_item.get("ontology_refs", [])
            v.require(isinstance(ontology_refs, list), path, f"{assertion_id}.ontology_refs 必须是数组")
            v.require(all(is_nonempty(ref) for ref in as_list(ontology_refs)), path, f"{assertion_id}.ontology_refs 不能包含空引用")
            outcome_refs = assertion_item.get("outcome_refs", [])
            v.require(isinstance(outcome_refs, list), path, f"{assertion_id}.outcome_refs 必须是数组")
            if any(as_list(as_dict(scenario_by_id.get(str(ref))).get("then")) for ref in refs):
                v.require(bool(outcome_refs), path, f"{assertion_id} 必须用 outcome_refs 映射 SCN 的 Then 结果")
            for outcome_ref in outcome_refs:
                parts = str(outcome_ref).split(".", 1)
                v.require(len(parts) == 2 and parts[0] in scenario_by_id, path, f"{assertion_id}.outcome_refs 引用了不存在的 SCN: {outcome_ref}")
                if len(parts) == 2 and parts[0] in scenario_by_id:
                    v.require(parts[0] in refs, path, f"{assertion_id}.outcome_refs 必须属于当前 CHK 引用的 SCN: {outcome_ref}")
                    scenario_item = scenario_by_id[parts[0]]
                    then_ids = {str(as_dict(value).get("id")) for value in as_list(scenario_item.get("then"))}
                    if then_ids:
                        v.require(parts[1] in then_ids, path, f"{assertion_id}.outcome_refs 引用了不存在的 Then: {outcome_ref}")
                        if parts[1] in then_ids:
                            covered_outcomes.add(str(outcome_ref))
            if assertion_type == "predicate":
                v.require(isinstance(assertion_item.get("predicate"), dict), path, f"{assertion_id} 为 predicate 时必须定义 predicate")
                validate_predicate(assertion_item.get("predicate"), path, f"{assertion_id}.predicate", v)
            else:
                v.require("predicate" not in assertion_item, path, f"{assertion_id} 为 semantic 时不能定义 predicate")
        v.require(not (assertion_ids & current), path, f"AST ID 必须在矩阵内唯一: {', '.join(sorted(assertion_ids & current))}")
        assertion_ids.update(current)
        validate_external_verification(item.get("external_verification"), path, f"{item.get('id')}.external_verification", v)
    for outcome_ref in sorted(gherkin_outcomes - covered_outcomes):
        v.require(False, path, f"{outcome_ref} 未被任何 AST 的 outcome_refs 覆盖")


def validate_current_refs(project: Project, requirement_id: str, scope: dict[str, Any], path: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    v = project.validation
    ref = as_dict(scope.get("requirement_ref"))
    v.require(ref == {"requirement_id": requirement_id}, path, "requirement_ref 与所在 REQ 目录不一致")
    scenario = project.scenarios.get(requirement_id)
    matrix = project.matrices.get(requirement_id)
    v.require(scenario is not None, path, "缺少当前验收场景")
    v.require(matrix is not None, path, "缺少当前验收矩阵")
    return scenario, matrix


def matrix_ids(matrix: dict[str, Any] | None) -> tuple[set[str], set[str], list[dict[str, Any]]]:
    checks = as_list(as_dict((matrix or {}).get("acceptance_matrix")).get("checks"))
    check_ids = {str(as_dict(item).get("id")) for item in checks}
    assertion_ids = {str(as_dict(assertion).get("id")) for check in checks for assertion in as_list(as_dict(check).get("assertions"))}
    return check_ids, assertion_ids, [as_dict(item) for item in checks]


def matrix_assertions(matrix: dict[str, Any] | None) -> dict[str, set[str]]:
    checks = as_list(as_dict((matrix or {}).get("acceptance_matrix")).get("checks"))
    return {
        str(as_dict(check).get("id")): {
            str(as_dict(assertion).get("id"))
            for assertion in as_list(as_dict(check).get("assertions"))
        }
        for check in checks
    }


def matrix_assertion_definitions(matrix: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        str(as_dict(assertion).get("id")): as_dict(assertion)
        for check in as_list(as_dict((matrix or {}).get("acceptance_matrix")).get("checks"))
        for assertion in as_list(as_dict(check).get("assertions"))
    }


def predicate_result_passes(assertion: dict[str, Any], result: dict[str, Any]) -> bool:
    if assertion.get("assertion_type", "semantic") != "predicate":
        return result.get("status") == "PASSED"
    evaluation = as_dict(result.get("evaluation"))
    observations = evaluation.get("observations")
    if not isinstance(observations, dict):
        return False
    try:
        return evaluate_predicate(assertion.get("predicate"), observations) is True
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return False


def validate_plan(project: Project, requirement_id: str, document: dict[str, Any], path: Path) -> None:
    v = project.validation
    plan = as_dict(document.get("implementation_plan"))
    _, matrix = validate_current_refs(project, requirement_id, plan, path)
    status = plan.get("status")
    v.require(status in IMPLEMENTATION_PLAN_STATUSES, path, "实现计划状态只允许 PLANNED/IN_PROGRESS/READY")

    context = as_dict(plan.get("context_review"))
    v.require(context.get("status") == "COMPLETED", path, "制定实现计划前必须完成 context_review")
    context_keys = ("requirement_refs", "scenario_refs", "matrix_refs", "project_refs", "code_structure_refs")
    for key in context_keys:
        refs = context.get(key)
        v.require(isinstance(refs, list) and bool(refs), path, f"context_review.{key} 必须是非空数组")
        v.require(all(is_nonempty(ref) for ref in as_list(refs)), path, f"context_review.{key} 不能包含空引用")
    findings = context.get("findings")
    v.require(isinstance(findings, list) and bool(findings), path, "context_review.findings 至少需要一条盘点结论")
    for index, raw in enumerate(as_list(findings)):
        finding = as_dict(raw)
        v.require(set(finding) == {"area", "observation", "impact"}, path, f"context_review.findings[{index}] 必须且只能包含 area、observation、impact")
        for key in ("area", "observation", "impact"):
            v.require(is_nonempty(finding.get(key)), path, f"context_review.findings[{index}].{key} 不能为空")
    for key in ("assumptions", "open_questions", "decisions"):
        v.require(isinstance(context.get(key), list), path, f"context_review.{key} 必须是数组")
    contextual_slice_refs: list[tuple[str, Any]] = []
    for index, raw in enumerate(as_list(context.get("open_questions"))):
        question = as_dict(raw)
        required = {"id", "question", "impact", "affected_slice_refs"}
        v.require(set(question) == required, path, f"context_review.open_questions[{index}] 字段不完整")
        for key in ("id", "question", "impact"):
            v.require(is_nonempty(question.get(key)), path, f"context_review.open_questions[{index}].{key} 不能为空")
        v.require(isinstance(question.get("affected_slice_refs"), list), path, f"context_review.open_questions[{index}].affected_slice_refs 必须是数组")
        contextual_slice_refs.extend((f"context_review.open_questions[{index}]", ref) for ref in as_list(question.get("affected_slice_refs")))
    for index, raw in enumerate(as_list(context.get("decisions"))):
        decision = as_dict(raw)
        required = {"id", "topic", "decision", "source", "affected_slice_refs"}
        v.require(set(decision) == required, path, f"context_review.decisions[{index}] 字段不完整")
        for key in ("id", "topic", "decision", "source"):
            v.require(is_nonempty(decision.get(key)), path, f"context_review.decisions[{index}].{key} 不能为空")
        v.require(isinstance(decision.get("affected_slice_refs"), list), path, f"context_review.decisions[{index}].affected_slice_refs 必须是数组")
        contextual_slice_refs.extend((f"context_review.decisions[{index}]", ref) for ref in as_list(decision.get("affected_slice_refs")))
    if status in {"IN_PROGRESS", "READY"}:
        v.require(not as_list(context.get("open_questions")), path, f"{status} 实现计划不能遗留 open_questions")

    human_gate = plan.get("human_gate")
    if human_gate is not None:
        gate = as_dict(human_gate)
        required = {"required", "status", "risk_categories"}
        v.require(set(gate) >= required, path, "implementation_plan.human_gate 必须包含 required、status、risk_categories")
        v.require(isinstance(gate.get("required"), bool), path, "human_gate.required 必须是布尔值")
        gate_status = gate.get("status")
        v.require(gate_status in {"NOT_REQUIRED", "PENDING", "CONFIRMED"}, path, "human_gate.status 非法")
        categories = gate.get("risk_categories")
        v.require(isinstance(categories, list), path, "human_gate.risk_categories 必须是数组")
        v.require(all(category in IMPLEMENTATION_RISK_CATEGORIES for category in as_list(categories)), path, "human_gate.risk_categories 包含非法风险类别")
        if gate.get("required"):
            v.require(bool(as_list(categories)), path, "required 的 human_gate 必须至少声明一个风险类别")
            v.require(gate_status in {"PENDING", "CONFIRMED"}, path, "required 的 human_gate.status 必须为 PENDING 或 CONFIRMED")
            if status in {"IN_PROGRESS", "READY"}:
                v.require(gate_status == "CONFIRMED", path, f"{status} 实现计划必须先通过 human_gate")
            if gate_status == "CONFIRMED":
                v.require(is_nonempty(gate.get("confirmed_by")), path, "CONFIRMED human_gate 必须记录 confirmed_by")
                v.require(is_nonempty(gate.get("confirmed_at")), path, "CONFIRMED human_gate 必须记录 confirmed_at")
                v.require(bool(as_list(gate.get("decision_refs"))), path, "CONFIRMED human_gate 必须记录 decision_refs")
        else:
            v.require(gate_status == "NOT_REQUIRED", path, "不需要人工门禁时 human_gate.status 必须为 NOT_REQUIRED")

    strategy = as_dict(plan.get("test_strategy"))
    v.require(strategy.get("default") == "tdd", path, "test_strategy.default 必须为 tdd")
    v.require(isinstance(strategy.get("exemptions"), list), path, "test_strategy.exemptions 必须是数组")
    exemption_assertions: set[str] = set()
    exemption_slice_refs: list[tuple[str, Any]] = []
    for index, raw in enumerate(as_list(strategy.get("exemptions"))):
        exemption = as_dict(raw)
        required = {"id", "kind", "slice_refs", "assertion_refs", "reason", "alternative_check"}
        v.require(set(exemption) == required, path, f"test_strategy.exemptions[{index}] 字段不完整")
        v.require(is_nonempty(exemption.get("id")), path, f"test_strategy.exemptions[{index}].id 不能为空")
        v.require(exemption.get("kind") in TDD_EXEMPTION_KINDS, path, f"test_strategy.exemptions[{index}].kind 非法")
        v.require(isinstance(exemption.get("slice_refs"), list) and bool(as_list(exemption.get("slice_refs"))), path, f"test_strategy.exemptions[{index}].slice_refs 必须是非空数组")
        v.require(isinstance(exemption.get("assertion_refs"), list), path, f"test_strategy.exemptions[{index}].assertion_refs 必须是数组")
        v.require(is_nonempty(exemption.get("reason")), path, f"test_strategy.exemptions[{index}].reason 不能为空")
        v.require(is_nonempty(exemption.get("alternative_check")), path, f"test_strategy.exemptions[{index}].alternative_check 不能为空")
        exemption_assertions.update(str(ref) for ref in as_list(exemption.get("assertion_refs")))
        exemption_slice_refs.extend((f"test_strategy.exemptions[{index}]", ref) for ref in as_list(exemption.get("slice_refs")))

    v.require(isinstance(plan.get("blockers"), list), path, "implementation_plan.blockers 必须是数组")
    check_ids, assertion_ids, _ = matrix_ids(matrix)
    slices = as_list(plan.get("slices"))
    v.require(bool(slices), path, "实现计划至少需要一个切片")
    slice_ids: set[str] = set()
    covered_assertions: set[str] = set()
    for item in slices:
        slice_item = as_dict(item)
        slice_id = slice_item.get("id")
        v.require(is_nonempty(slice_id), path, "实现切片 id 不能为空")
        if isinstance(slice_id, str):
            v.require(slice_id not in slice_ids, path, f"实现切片 ID 重复: {slice_id}")
            slice_ids.add(slice_id)
        for key in ("title", "objective"):
            v.require(is_nonempty(slice_item.get(key)), path, f"{slice_id}.{key} 不能为空")
        kind = slice_item.get("kind")
        v.require(kind in IMPLEMENTATION_SLICE_KINDS, path, f"{slice_id}.kind 非法")
        v.require(slice_item.get("status") in IMPLEMENTATION_SLICE_STATUSES, path, f"{slice_id}.status 非法")
        for key in ("depends_on", "check_refs", "assertion_refs", "production_refs", "test_refs"):
            v.require(isinstance(slice_item.get(key), list), path, f"{slice_id}.{key} 必须是数组")
        check_refs = as_list(slice_item.get("check_refs"))
        assertion_refs = as_list(slice_item.get("assertion_refs"))
        if kind == "behavior_slice":
            v.require(bool(assertion_refs), path, f"{slice_id} 为 behavior_slice 时必须引用 AST")
        for ref in check_refs:
            v.require(ref in check_ids, path, f"实现切片引用不存在的 CHK: {ref}")
        for ref in assertion_refs:
            v.require(ref in assertion_ids, path, f"实现切片引用不存在的 AST: {ref}")
            covered_assertions.add(str(ref))
        if status == "READY":
            v.require(slice_item.get("status") == "COMPLETED", path, f"READY 实现计划包含未完成切片: {slice_id}")
            v.require(bool(as_list(slice_item.get("production_refs"))), path, f"READY 切片必须记录 production_refs: {slice_id}")
            if kind == "behavior_slice" and not set(map(str, assertion_refs)) <= exemption_assertions:
                v.require(bool(as_list(slice_item.get("test_refs"))), path, f"READY 行为切片必须记录 test_refs 或完整 TDD 豁免: {slice_id}")
    for item in slices:
        slice_item = as_dict(item)
        for ref in as_list(slice_item.get("depends_on")):
            v.require(ref in slice_ids, path, f"{slice_item.get('id')}.depends_on 引用了不存在的切片: {ref}")
            v.require(ref != slice_item.get("id"), path, f"{slice_item.get('id')} 不能依赖自身")
    for label, ref in [*contextual_slice_refs, *exemption_slice_refs]:
        v.require(ref in slice_ids, path, f"{label} 引用了不存在的切片: {ref}")
    for ref in exemption_assertions:
        v.require(ref in assertion_ids, path, f"test_strategy.exemptions 引用了不存在的 AST: {ref}")
    missing_assertions = assertion_ids - covered_assertions
    v.require(not missing_assertions, path, f"实现计划缺少 AST 覆盖: {', '.join(sorted(missing_assertions))}")
    if status == "READY":
        v.require(not as_list(plan.get("blockers")), path, "READY 实现计划不能存在 blockers")


def artifact_path(root: Path, location: str) -> Path:
    prefix = "docs/交付证明/"
    if location.startswith(prefix):
        return root / location[len(prefix):]
    path = Path(location)
    return path if path.is_absolute() else root / path


def validate_artifact_locator(
    artifact: dict[str, Any],
    result: dict[str, Any],
    root: Path,
    path: Path,
    validation: Validation,
) -> None:
    artifact_id = artifact.get("id")
    locator = result.get("evidence_locator")
    validation.require(is_nonempty(locator), path, f"{artifact_id}.{result.get('assertion_id')}.evidence_locator 不能为空")
    if not is_nonempty(locator):
        return
    artifact_type = artifact.get("type")
    if artifact_type == "screenshot":
        validation.require(locator == "screenshot", path, f"{artifact_id}.{result.get('assertion_id')}.screenshot 的 evidence_locator 必须为 screenshot")
        return
    match = TEXT_LOCATOR_RE.fullmatch(locator)
    validation.require(match is not None, path, f"{artifact_id}.{result.get('assertion_id')}.evidence_locator 必须使用 line/output/request/response/observed:<行号>")
    if match is None:
        return
    location = artifact.get("location")
    if not is_nonempty(location):
        return
    target = artifact_path(root, location)
    try:
        line_count = len(target.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeError) as error:
        validation.errors.append(f"{path}: {artifact_id} 无法读取文本证据以校验 evidence_locator: {error}")
        return
    line_number = int(match.group(1))
    validation.require(line_number <= line_count, path, f"{artifact_id}.{result.get('assertion_id')}.evidence_locator 指向第 {line_number} 行，但附件只有 {line_count} 行")



def artifact_assertion_results(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [as_dict(item) for item in as_list(artifact.get("assertion_results"))]


def artifact_types(artifact_refs: list[Any], artifacts_by_id: dict[str, dict[str, Any]]) -> set[str]:
    return {
        str(artifacts_by_id.get(str(ref), {}).get("type"))
        for ref in artifact_refs
        if artifacts_by_id.get(str(ref), {}).get("type")
    }


def validate_evidence(project: Project, requirement_id: str, document: dict[str, Any], path: Path) -> None:
    v = project.validation
    evidence = as_dict(document.get("test_evidence"))
    _, matrix = validate_current_refs(project, requirement_id, evidence, path)
    check_ids, assertion_ids, checks = matrix_ids(matrix)
    assertion_definitions = matrix_assertion_definitions(matrix)
    checks_by_id = {str(item.get("id")): item for item in checks}
    check_assertions = matrix_assertions(matrix)
    runs = as_list(evidence.get("runs"))
    artifacts = as_list(evidence.get("artifacts"))
    git_commit = evidence.get("git_commit")
    v.require("code_revision" not in evidence, path, "测试证据禁止 code_revision，使用顶层 git_commit")
    v.require("git_commit" in evidence, path, "测试证据必须包含顶层 git_commit")
    v.require(git_commit is None or is_full_git_commit(git_commit), path, "git_commit 必须是完整的 40 位或 64 位小写十六进制 Git commit ID")
    if runs:
        v.require(is_full_git_commit(git_commit), path, "存在 RUN 时必须绑定完整 git_commit")
        v.require(git_commit_exists(path.parent, git_commit), path, "存在 RUN 时 git_commit 必须是当前 Git 仓库中的真实提交")
    run_ids = unique_ids(runs, RUN_RE, path, "runs", v)
    runs_by_id = {str(as_dict(item).get("id")): as_dict(item) for item in runs}
    artifact_ids = unique_ids(artifacts, ART_RE, path, "artifacts", v)
    artifacts_by_id = {str(as_dict(item).get("id")): as_dict(item) for item in artifacts}
    definition_digests = as_dict(evidence.get("definition_digests"))
    expected_digests = current_definition_digests(project, requirement_id)
    v.require(definition_digests == expected_digests, path, "测试证据的定义摘要不是当前 REQ/场景/矩阵内容")
    for artifact in artifacts:
        item = as_dict(artifact)
        location = item.get("location")
        artifact_type = item.get("type")
        v.require(isinstance(artifact_type, str) and artifact_type in ARTIFACT_TYPES, path, f"{item.get('id')}.type 非法")
        v.require(is_nonempty(location), path, f"{item.get('id')}.location 不能为空")
        if is_nonempty(location):
            v.require(artifact_path(project.root, location).is_file(), path, f"证据附件不存在: {location}")
        assertion_results = artifact_assertion_results(item)
        v.require(isinstance(item.get("assertion_results", []), list), path, f"{item.get('id')}.assertion_results 必须是数组")
        result_ids: set[str] = set()
        for result in assertion_results:
            assertion_id = str(result.get("assertion_id"))
            result_ids.add(assertion_id)
            v.require(assertion_id in assertion_ids, path, f"{item.get('id')} 引用了不存在的 AST: {assertion_id}")
            v.require(is_nonempty(result.get("expected")), path, f"{item.get('id')}.{assertion_id}.expected 不能为空")
            v.require(is_nonempty(result.get("observed")), path, f"{item.get('id')}.{assertion_id}.observed 不能为空")
            v.require(result.get("status") in ARTIFACT_EVIDENCE_STATUSES, path, f"{item.get('id')}.{assertion_id}.status 非法")
            assertion = assertion_definitions.get(assertion_id, {})
            if assertion.get("assertion_type", "semantic") == "predicate" and result.get("status") != "BLOCKED":
                evaluation = as_dict(result.get("evaluation"))
                observations = evaluation.get("observations")
                v.require(isinstance(result.get("evaluation"), dict), path, f"{item.get('id')}.{assertion_id} 为 predicate 时必须记录 evaluation")
                v.require(isinstance(observations, dict), path, f"{item.get('id')}.{assertion_id}.evaluation.observations 必须是对象")
                if isinstance(observations, dict):
                    try:
                        predicate_passed = evaluate_predicate(assertion.get("predicate"), observations)
                    except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
                        v.require(False, path, f"{item.get('id')}.{assertion_id} 无法计算 predicate: {error}")
                    else:
                        expected_status = "PASSED" if predicate_passed else "FAILED"
                        v.require(result.get("status") == expected_status, path, f"{item.get('id')}.{assertion_id}.status 必须由 predicate 计算为 {expected_status}")
            validate_artifact_locator(item, result, project.root, path, v)
        v.require(len(result_ids) == len(assertion_results), path, f"{item.get('id')}.assertion_results 不能重复 AST")
        if artifact_type == "screenshot":
            capture = as_dict(item.get("capture"))
            v.require(isinstance(item.get("capture"), dict), path, f"{item.get('id')} 为 screenshot 时必须有 capture")
            for key in ("viewport", "route", "captured_at"):
                v.require(is_nonempty(capture.get(key)), path, f"{item.get('id')}.capture.{key} 不能为空")
            v.require(isinstance(capture.get("redacted"), bool), path, f"{item.get('id')}.capture.redacted 必须是布尔值")
    for run in runs:
        item = as_dict(run)
        v.require("code_revision" not in item, path, f"{item.get('id')} 禁止逐 RUN code_revision")
        v.require("git_commit" not in item, path, f"{item.get('id')} 禁止逐 RUN git_commit")
        v.require("expected_failure_observed" not in item, path, f"{item.get('id')} 禁止记录 TDD RED；RED/GREEN 不属于正式 RUN")
        v.require(item.get("phase") in RUN_PHASES, path, f"{item.get('id')}.phase 非法: {item.get('phase')}")
        result = item.get("result")
        v.require(result in {"PASSED", "FAILED", "BLOCKED"}, path, f"{item.get('id')}.result 非法: {result}")
        for key in ("command", "environment", "started_at"):
            v.require(is_nonempty(item.get(key)), path, f"{item.get('id')}.{key} 不能为空")
        v.require(isinstance(item.get("check_refs"), list), path, f"{item.get('id')}.check_refs 必须是数组")
        v.require(isinstance(item.get("assertion_refs"), list), path, f"{item.get('id')}.assertion_refs 必须是数组")
        v.require(isinstance(item.get("supporting_run_refs"), list), path, f"{item.get('id')}.supporting_run_refs 必须是数组")
        v.require(isinstance(item.get("artifact_refs"), list), path, f"{item.get('id')}.artifact_refs 必须是数组")
        check_refs = as_list(item.get("check_refs"))
        assertion_refs = as_list(item.get("assertion_refs"))
        supporting_run_refs = as_list(item.get("supporting_run_refs"))
        is_auxiliary = not check_refs and not assertion_refs
        v.require(
            is_auxiliary or (bool(check_refs) and bool(assertion_refs)),
            path,
            f"{item.get('id')} 必须同时声明正式 CHK/AST，或同时留空作为 REQ 级辅助 RUN",
        )
        v.require(len(check_refs) == len(set(map(str, check_refs))), path, f"{item.get('id')}.check_refs 不能重复")
        v.require(len(assertion_refs) == len(set(map(str, assertion_refs))), path, f"{item.get('id')}.assertion_refs 不能重复")
        v.require(len(supporting_run_refs) == len(set(map(str, supporting_run_refs))), path, f"{item.get('id')}.supporting_run_refs 不能重复")
        v.require(str(item.get("id")) not in {str(ref) for ref in supporting_run_refs}, path, f"{item.get('id')} 不能引用自身作为辅助 RUN")
        v.require("external_verification" in item, path, f"{item.get('id')}.external_verification 必须存在")
        validate_external_verification(item.get("external_verification"), path, f"{item.get('id')}.external_verification", v)
        for ref in check_refs:
            v.require(ref in check_ids, path, f"{item.get('id')} 引用了不存在的 CHK: {ref}")
        owned_assertions = {
            assertion_id
            for check_ref in as_list(item.get("check_refs"))
            for assertion_id in check_assertions.get(str(check_ref), set())
        }
        for ref in assertion_refs:
            v.require(ref in assertion_ids, path, f"{item.get('id')} 引用了不存在的 AST: {ref}")
            v.require(ref in owned_assertions, path, f"{item.get('id')} 的 AST {ref} 不属于其引用的 CHK")
        for check_ref in check_refs:
            expected_external = checks_by_id.get(str(check_ref), {}).get("external_verification")
            actual_external = item.get("external_verification")
            if expected_external is None:
                v.require(actual_external is None, path, f"{item.get('id')} 的 external_verification 必须与 {check_ref} 一致")
            else:
                v.require(external_signature(actual_external) == external_signature(expected_external), path, f"{item.get('id')} 的 external_verification 必须与 {check_ref} 一致")
        for ref in as_list(item.get("artifact_refs")):
            v.require(ref in artifact_ids, path, f"{item.get('id')} 引用了不存在的 ART: {ref}")
        referenced_artifacts = [artifacts_by_id.get(str(ref), {}) for ref in as_list(item.get("artifact_refs"))]
        referenced_assertion_ids = {
            str(result.get("assertion_id"))
            for artifact in referenced_artifacts
            for result in artifact_assertion_results(artifact)
        }
        for assertion_id in referenced_assertion_ids:
            v.require(assertion_id in assertion_refs, path, f"{item.get('id')} 的 ART 声明了未引用的 AST: {assertion_id}")
        if result == "PASSED":
            v.require(item.get("exit_code") == 0, path, f"{item.get('id')} 为 PASSED 时 exit_code 必须为 0")
            if not is_auxiliary:
                missing_evidence = {
                    str(assertion_id)
                    for assertion_id in assertion_refs
                    if not run_proves_assertion(
                        item,
                        str(assertion_id),
                        evidence,
                        assertion_definitions.get(str(assertion_id)),
                    )
                }
                v.require(
                    not missing_evidence,
                    path,
                    f"{item.get('id')} 的 ART 缺少 AST 级 PASSED 证据: {', '.join(sorted(missing_evidence))}",
                )
        run_digests = as_dict(item.get("definition_digests"))
        v.require(run_digests == definition_digests, path, f"{item.get('id')} 的定义摘要与当前证据不一致")
        if is_auxiliary:
            v.require(not supporting_run_refs, path, f"{item.get('id')} 是辅助 RUN，不能再引用辅助 RUN")
        else:
            for supporting_ref in supporting_run_refs:
                supporting = runs_by_id.get(str(supporting_ref))
                v.require(supporting is not None, path, f"{item.get('id')} 引用了不存在的辅助 RUN: {supporting_ref}")
                if supporting is None:
                    continue
                v.require(not as_list(supporting.get("check_refs")) and not as_list(supporting.get("assertion_refs")), path, f"{item.get('id')} 只能引用 REQ 级辅助 RUN: {supporting_ref}")
                v.require(supporting.get("result") == "PASSED", path, f"{item.get('id')} 的辅助 RUN 必须为 PASSED: {supporting_ref}")
                v.require(bool(as_list(supporting.get("artifact_refs"))), path, f"{item.get('id')} 的辅助 RUN 必须有 ART: {supporting_ref}")
                v.require(not as_list(supporting.get("supporting_run_refs")), path, f"辅助 RUN 不允许链式引用: {supporting_ref}")
                v.require(as_dict(supporting.get("definition_digests")) == definition_digests, path, f"{item.get('id')} 的辅助 RUN 定义摘要无效: {supporting_ref}")
    superseded = superseded_run_ids(evidence, checks_by_id)
    for run_id in sorted(superseded):
        v.require(False, path, f"{run_id} 已被后续完整 PASSED 证明替代，当前测试证据不得保留旧 RUN")
    regression = as_dict(evidence.get("regression"))
    for ref in as_list(regression.get("run_refs")):
        v.require(ref in run_ids, path, f"regression 引用了不存在的 RUN: {ref}")
    cleanup_ref = as_dict(evidence.get("test_data_cleanup")).get("run_ref")
    if cleanup_ref is not None:
        v.require(cleanup_ref in run_ids, path, f"test_data_cleanup 引用了不存在的 RUN: {cleanup_ref}")


def acceptance_eligible_runs(evidence_scope: dict[str, Any], target_digests: dict[str, str] | None = None) -> list[dict[str, Any]]:
    if not is_full_git_commit(evidence_scope.get("git_commit")):
        return []
    runs = [as_dict(item) for item in as_list(evidence_scope.get("runs"))]
    by_id = {str(item.get("id")): item for item in runs}

    def base_valid(run: dict[str, Any]) -> bool:
        return (
            run.get("result") == "PASSED"
            and as_list(run.get("artifact_refs"))
            and (target_digests is None or as_dict(run.get("definition_digests")) == target_digests)
        )

    def valid_support(ref: Any) -> bool:
        supporting = by_id.get(str(ref))
        return bool(
            supporting
            and base_valid(supporting)
            and not as_list(supporting.get("check_refs"))
            and not as_list(supporting.get("assertion_refs"))
            and not as_list(supporting.get("supporting_run_refs"))
        )

    return [
        run
        for run in runs
        if base_valid(run)
        and bool(as_list(run.get("check_refs")))
        and bool(as_list(run.get("assertion_refs")))
        and all(valid_support(ref) for ref in as_list(run.get("supporting_run_refs")))
    ]


def run_matches_check_evidence(
    run: dict[str, Any],
    check: dict[str, Any],
    evidence_scope: dict[str, Any],
    target_digests: dict[str, str] | None = None,
) -> bool:
    eligible_ids = {
        str(item.get("id"))
        for item in acceptance_eligible_runs(evidence_scope, target_digests)
    }
    if str(run.get("id")) not in eligible_ids:
        return False
    external = as_dict(check.get("external_verification"))
    run_external = as_dict(run.get("external_verification"))
    if external:
        if (
            run_external.get("provider") != external.get("provider")
            or run_external.get("mode") != external.get("mode")
        ):
            return False
    elif run.get("external_verification") is not None:
        return False
    artifacts_by_id = {
        str(as_dict(item).get("id")): as_dict(item)
        for item in as_list(as_dict(evidence_scope).get("artifacts"))
    }
    required_types = [
        str(item)
        for item in as_list(as_dict(check.get("evidence_requirements")).get("required_artifact_types"))
    ]
    return set(required_types) <= artifact_types(as_list(run.get("artifact_refs")), artifacts_by_id)


def run_proves_assertion(
    run: dict[str, Any],
    assertion_id: str,
    evidence_scope: dict[str, Any],
    assertion: dict[str, Any] | None = None,
) -> bool:
    if run.get("result") != "PASSED" or assertion_id not in {str(ref) for ref in as_list(run.get("assertion_refs"))}:
        return False
    artifacts_by_id = {
        str(as_dict(item).get("id")): as_dict(item)
        for item in as_list(as_dict(evidence_scope).get("artifacts"))
    }
    definition = assertion or {}
    return any(
        str(result.get("assertion_id")) == assertion_id
        and result.get("status") == "PASSED"
        and predicate_result_passes(definition, result)
        for ref in as_list(run.get("artifact_refs"))
        for result in artifact_assertion_results(artifacts_by_id.get(str(ref), {}))
    )


def check_proof_state(
    evidence_scope: dict[str, Any],
    check: dict[str, Any],
    target_digests: dict[str, str] | None = None,
) -> str | None:
    check_id = str(check.get("id"))
    assertion_definitions = {
        str(as_dict(assertion).get("id")): as_dict(assertion)
        for assertion in as_list(check.get("assertions"))
    }
    expected = {
        str(as_dict(assertion).get("id"))
        for assertion in as_list(check.get("assertions"))
    }
    matching = [
        run for run in acceptance_eligible_runs(evidence_scope, target_digests)
        if check_id in as_list(run.get("check_refs"))
        and run_matches_check_evidence(run, check, evidence_scope, target_digests)
    ]
    covered = {
        assertion_id
        for run in matching
        for assertion_id in expected
        if run_proves_assertion(run, assertion_id, evidence_scope, assertion_definitions.get(assertion_id))
    }
    if expected and expected <= covered:
        return "PASS"
    current_runs = [
        as_dict(run)
        for run in as_list(evidence_scope.get("runs"))
        if check_id in as_list(as_dict(run).get("check_refs"))
    ]
    if any(run.get("result") == "FAILED" for run in current_runs):
        return "FAIL"
    if any(run.get("result") == "BLOCKED" for run in current_runs):
        return "BLOCKED"
    return None


def scenario_proof_state(
    evidence_scope: dict[str, Any],
    checks: list[dict[str, Any]],
    scenario_id: str,
    target_digests: dict[str, str] | None = None,
) -> str | None:
    blocking_checks = [
        check for check in checks
        if scenario_id in {str(ref) for ref in as_list(check.get("scenario_ids"))}
        and check.get("required") is True
        and check.get("blocking") is True
    ]
    if not blocking_checks:
        return None
    states = [check_proof_state(evidence_scope, check, target_digests) for check in blocking_checks]
    if all(state == "PASS" for state in states):
        return "PASS"
    if "FAIL" in states:
        return "FAIL"
    if "BLOCKED" in states:
        return "BLOCKED"
    return None


def superseded_run_ids(evidence_scope: dict[str, Any], checks_by_id: dict[str, dict[str, Any]]) -> set[str]:
    runs = [as_dict(item) for item in as_list(evidence_scope.get("runs"))]
    superseded: set[str] = set()
    for index, run in enumerate(runs):
        if run.get("result") not in {"FAILED", "BLOCKED"}:
            continue
        check_refs = [str(ref) for ref in as_list(run.get("check_refs"))]
        if not check_refs:
            continue
        later_scope = {**evidence_scope, "runs": runs[index + 1:]}
        if all(
            check_ref in checks_by_id
            and check_proof_state(later_scope, checks_by_id[check_ref], as_dict(evidence_scope.get("definition_digests"))) == "PASS"
            for check_ref in check_refs
        ):
            superseded.add(str(run.get("id")))
    return superseded


def validate_report(project: Project, requirement_id: str, document: dict[str, Any], path: Path) -> None:
    v = project.validation
    report = as_dict(document.get("acceptance_report"))
    git_commit = report.get("git_commit")
    v.require("code_revision" not in report, path, "验收报告禁止 code_revision，使用 git_commit")
    v.require("git_commit" in report, path, "验收报告必须包含 git_commit")
    v.require(git_commit is None or is_full_git_commit(git_commit), path, "验收报告 git_commit 必须是完整的 40 位或 64 位小写十六进制 Git commit ID")
    scenario, matrix = validate_current_refs(project, requirement_id, report, path)
    v.require(report.get("status") in {"SATISFIED", "NOT_SATISFIED"}, path, "验收报告状态只允许 SATISFIED/NOT_SATISFIED")
    expected_scenarios = {
        str(as_dict(item).get("id"))
        for item in as_list(as_dict((scenario or {}).get("acceptance_scenarios")).get("scenarios"))
    }
    scenario_result_items = as_list(report.get("scenario_results"))
    v.require("scenario_results" in report, path, "验收报告必须包含 scenario_results")
    scenario_result_ids: list[str] = []
    for item in scenario_result_items:
        result = as_dict(item)
        scenario_ref = str(result.get("scenario_ref"))
        scenario_result_ids.append(scenario_ref)
        v.require(scenario_ref in expected_scenarios, path, f"验收报告引用不存在的场景: {scenario_ref}")
        v.require(result.get("status") == "PASS", path, f"{scenario_ref}.status 只允许 PASS；未通过场景不写入 scenario_results")
        v.require(is_nonempty(result.get("reason")), path, f"{scenario_ref}.reason 不能为空")
        run_refs = result.get("run_refs", [])
        v.require(isinstance(run_refs, list), path, f"{scenario_ref}.run_refs 必须是数组")
        if result.get("status") == "PASS":
            v.require(isinstance(run_refs, list) and bool(run_refs), path, f"{scenario_ref} 为 PASS 时必须关联至少一个 RUN")
    v.require(len(scenario_result_ids) == len(set(scenario_result_ids)), path, "验收报告不能重复裁决同一个 SCN")
    evidence_document = project.evidence.get(requirement_id)
    if evidence_document is None:
        v.require(report.get("status") != "SATISFIED", path, "SATISFIED 报告必须有测试证据")
        return
    evidence = as_dict(evidence_document.get("test_evidence"))
    expected_digests = current_definition_digests(project, requirement_id)
    v.require(as_dict(report.get("definition_digests")) == expected_digests, path, "验收报告的定义摘要不是当前内容")
    v.require(as_dict(evidence.get("definition_digests")) == expected_digests, path, "报告与测试证据的定义摘要不一致")
    v.require(evidence.get("git_commit") == git_commit, path, "报告与测试证据的 git_commit 不一致")
    _, _, checks = matrix_ids(matrix)
    runs_by_id = {
        str(as_dict(item).get("id")): as_dict(item)
        for item in as_list(evidence.get("runs"))
    }
    eligible_run_ids = {
        str(item.get("id"))
        for item in acceptance_eligible_runs(evidence, expected_digests)
    }
    derived_results = {
        scenario_ref: scenario_proof_state(evidence, checks, scenario_ref, expected_digests)
        for scenario_ref in expected_scenarios
    }
    for item in scenario_result_items:
        result = as_dict(item)
        scenario_ref = str(result.get("scenario_ref"))
        derived_status = derived_results.get(scenario_ref)
        v.require(
            derived_status == "PASS",
            path,
            f"{scenario_ref} 的阻断 CHK 尚未被完整 AST 证据覆盖，不得记录 PASS",
        )
        scenario_check_ids = {
            str(check.get("id"))
            for check in checks
            if scenario_ref in {str(ref) for ref in as_list(check.get("scenario_ids"))}
        }
        for ref in as_list(result.get("run_refs")):
            run = runs_by_id.get(str(ref))
            v.require(run is not None, path, f"{scenario_ref}.run_refs 引用了不存在的 RUN: {ref}")
            if run is not None:
                v.require(
                    bool(scenario_check_ids & {str(check_ref) for check_ref in as_list(run.get("check_refs"))}),
                    path,
                    f"{scenario_ref}.run_refs 引用了不属于该场景 CHK 的 RUN: {ref}",
                )
            v.require(str(ref) in eligible_run_ids, path, f"{scenario_ref}.run_refs 必须引用有效 PASSED 正式 RUN: {ref}")
    expected_report_status = "SATISFIED" if derived_results and all(
        status == "PASS" for status in derived_results.values()
    ) else "NOT_SATISFIED"
    v.require(report.get("status") == expected_report_status, path, f"验收报告状态必须由当前 SCN 派生为 {expected_report_status}")
    if report.get("status") != "SATISFIED":
        return
    requirement = as_dict(project.requirements[requirement_id].get("requirement"))
    v.require(requirement.get("status") == "SATISFIED", path, "SATISFIED 报告要求 REQ 状态为 SATISFIED")
    v.require(as_dict((scenario or {}).get("acceptance_scenarios")).get("status") == "CONFIRMED", path, "SATISFIED 报告必须引用已确认场景")
    v.require(as_dict((matrix or {}).get("acceptance_matrix")).get("status") == "CONFIRMED", path, "SATISFIED 报告必须引用已确认矩阵")
    v.require(is_full_git_commit(git_commit), path, "SATISFIED 报告必须明确完整 git_commit")
    v.require(git_commit_exists(path.parent, git_commit), path, "SATISFIED 报告的 git_commit 必须是当前 Git 仓库中的真实提交")
    results = {as_dict(item).get("scenario_ref"): as_dict(item).get("status") for item in as_list(report.get("scenario_results"))}
    v.require(set(results) == expected_scenarios, path, "SATISFIED 报告必须逐一裁决全部场景")
    v.require(all(results.get(item) == "PASS" for item in expected_scenarios), path, "SATISFIED 报告的全部场景必须 PASS")
    check_assertions = matrix_assertions(matrix)
    assertion_definitions = matrix_assertion_definitions(matrix)
    evidence_artifacts = {
        str(as_dict(item).get("id")): as_dict(item)
        for item in as_list(evidence.get("artifacts"))
    }
    passed_runs = acceptance_eligible_runs(evidence, expected_digests)
    for check in checks:
        if check.get("required") is not True or check.get("blocking") is not True:
            continue
        matching = [run for run in passed_runs if check.get("id") in as_list(run.get("check_refs"))]
        external = as_dict(check.get("external_verification"))
        if external:
            matching = [run for run in matching if as_dict(run.get("external_verification")).get("provider") == external.get("provider") and as_dict(run.get("external_verification")).get("mode") == external.get("mode")]
        else:
            matching = [run for run in matching if run.get("external_verification") is None]
        required_artifact_types = evidence_requirements(
            check.get("evidence_requirements"),
            path,
            f"{check.get('id')}.evidence_requirements",
            v,
        )
        if required_artifact_types:
            matching = [
                run
                for run in matching
                if set(required_artifact_types) <= artifact_types(as_list(run.get("artifact_refs")), evidence_artifacts)
            ]
        expected_assertions = check_assertions.get(str(check.get("id")), set())
        covered_assertions = {
            str(assertion_ref)
            for run in matching
            for assertion_ref in as_list(run.get("assertion_refs"))
            if str(assertion_ref) in expected_assertions
            and run_proves_assertion(run, str(assertion_ref), evidence, assertion_definitions.get(str(assertion_ref)))
        }
        missing_assertions = expected_assertions - covered_assertions
        v.require(
            not missing_assertions,
            path,
            f"SATISFIED 缺少 {check.get('id')} 的 AST 覆盖: {', '.join(sorted(missing_assertions))}",
        )


def validate_dependencies(project: Project) -> None:
    v = project.validation
    for requirement_id, document in project.requirements.items():
        path = project.requirement_paths[requirement_id]
        requirement = as_dict(document.get("requirement"))
        dependencies = as_list(requirement.get("dependencies"))
        dependency_ids = unique_ids(dependencies, DEP_RE, path, "dependencies", v)
        for dependency in dependencies:
            item = as_dict(dependency)
            allowed_keys = {"id", "description", "related_requirement_id"}
            v.require(set(item) == allowed_keys, path, f"{item.get('id')} 必须且只能包含 id、description、related_requirement_id")
            v.require(is_nonempty(item.get("description")), path, f"{item.get('id')}.description 不能为空")
            related = item.get("related_requirement_id")
            v.require(related is None or (isinstance(related, str) and REQ_RE.fullmatch(related) is not None), path, f"{item.get('id')}.related_requirement_id 格式非法")
            v.require(related != requirement_id, path, f"{item.get('id')} 不能关联当前 REQ 自身")

        matrix = project.matrices.get(requirement_id)
        if matrix is None:
            continue
        checks = as_list(as_dict(matrix.get("acceptance_matrix")).get("checks"))
        covered: set[str] = set()
        for check in checks:
            check_item = as_dict(check)
            refs = as_list(check_item.get("dependency_ids"))
            for ref in refs:
                v.require(ref in dependency_ids, project.matrix_paths[requirement_id], f"{check_item.get('id')} 引用了不存在的 DEP: {ref}")
            if check_item.get("required") is True and check_item.get("blocking") is True:
                covered.update(ref for ref in refs if isinstance(ref, str))
        missing = dependency_ids - covered
        v.require(not missing, project.matrix_paths[requirement_id], f"业务依赖缺少必需阻断 CHK: {', '.join(sorted(missing))}")


def application_ready(project: Project, requirement_id: str, validation: Validation) -> None:
    path = project.requirement_paths.get(requirement_id, project.root / requirement_id / "实现计划.md").parent / "实现计划.md"
    document = project.plans.get(requirement_id)
    validation.require(document is not None, path, "application-ready 门禁缺少实现计划")
    if document is None:
        return
    plan = as_dict(document.get("implementation_plan"))
    validation.require(plan.get("status") == "READY", path, "application-ready 要求实现计划状态为 READY")
    validation.require(not as_list(plan.get("blockers")), path, "application-ready 要求 blockers 为空")
    for surface in as_list(plan.get("delivery_surfaces")):
        validation.require(as_dict(surface).get("status") == "COMPLETED", path, f"交付面未完成: {as_dict(surface).get('surface')}")
    for item in as_list(plan.get("slices")):
        validation.require(as_dict(item).get("status") == "COMPLETED", path, f"实现切片未完成: {as_dict(item).get('id')}")
    readiness = as_dict(plan.get("readiness"))
    for key in ("configuration", "persistence", "application_start"):
        validation.require(as_dict(readiness.get(key)).get("status") in {"COMPLETED", "NOT_REQUIRED"}, path, f"readiness.{key} 未完成")
    for journey in as_list(readiness.get("external_journeys")):
        validation.require(as_dict(journey).get("status") == "COMPLETED", path, f"外部旅程未完成: {as_dict(journey).get('provider')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="+", type=Path, help="docs/交付证明、REQ 目录或派生需求清单")
    parser.add_argument("--gate", choices=["application-ready"], help="额外执行阶段门禁")
    args = parser.parse_args()
    roots: dict[Path, set[str]] = {}
    for target in args.targets:
        root, requirement_id = resolve_root(target)
        roots.setdefault(root, set())
        if requirement_id:
            roots[root].add(requirement_id)
    all_errors: list[str] = []
    all_warnings: list[str] = []
    total_requirements = 0
    total_runs = 0
    for root, selected in roots.items():
        project = load_project(root)
        total_requirements += len(project.requirements)
        total_runs += sum(len(as_list(as_dict(doc.get("test_evidence")).get("runs"))) for doc in project.evidence.values())
        if args.gate:
            if not selected:
                project.validation.errors.append(f"{root}: --gate application-ready 必须指定一个 REQ 目录")
            for requirement_id in selected:
                application_ready(project, requirement_id, project.validation)
        all_errors.extend(project.validation.errors)
        all_warnings.extend(project.validation.warnings)
    for warning in all_warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if all_errors:
        for error in all_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"INVALID: {len(all_errors)} 个错误，{len(all_warnings)} 个待审核提示", file=sys.stderr)
        return 1
    print(f"VALID: {total_requirements} 个 REQ，{total_runs} 个 RUN；{len(all_warnings)} 条待审核或历史提示")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
