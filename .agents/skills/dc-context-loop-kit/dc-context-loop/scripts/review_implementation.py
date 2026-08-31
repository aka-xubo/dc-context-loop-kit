#!/usr/bin/env python3
"""Run deterministic completion checks before publishing IMPLEMENTATION READY."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


class ReviewError(Exception):
    pass


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
        match = re.search(r"```yaml\s*(.*?)\s*```", text, re.DOTALL)
        value = yaml.safe_load(match.group(1) if match else text)
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise ReviewError(f"无法读取 YAML：{path}: {error}") from error
    if not isinstance(value, dict):
        raise ReviewError(f"YAML 根对象必须是对象：{path}")
    return value


def load_embedded_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```yaml\s*(.*?)\s*```", text, re.DOTALL)
    if not match:
        raise ReviewError(f"文件中没有 YAML 机器块：{path}")
    value = yaml.safe_load(match.group(1))
    if not isinstance(value, dict):
        raise ReviewError(f"YAML 机器块根对象必须是对象：{path}")
    return value


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ReviewError(f"Git 命令失败（{' '.join(args)}）：{result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def preflight(plan_file: Path, matrix_file: Path | None) -> tuple[bool, list[str]]:
    plan_doc = load_yaml(plan_file)
    plan = as_dict(plan_doc.get("implementation_plan"))
    errors: list[str] = []
    lines: list[str] = []

    def check(condition: bool, message: str) -> None:
        (lines if condition else errors).append(("PASSED: " if condition else "FAILED: ") + message)

    check(plan_doc.get("document_type") == "implementation_plan", "实现计划文档类型正确")
    check(plan.get("status") in {"PLANNED", "IN_PROGRESS"}, "覆盖预检发生在编码前阶段")
    check(not as_list(plan.get("blockers")), "计划没有 blocker")
    context = as_dict(plan.get("context_review"))
    check(not as_list(context.get("open_questions")), "计划没有未决问题")
    slices = [as_dict(item) for item in as_list(plan.get("slices"))]
    check(bool(slices), "实现计划包含切片")
    covered: set[str] = set()
    exemptions = {
        str(ref)
        for exemption in as_list(as_dict(plan.get("test_strategy")).get("exemptions"))
        for ref in as_list(as_dict(exemption).get("assertion_refs"))
    }
    for item in slices:
        slice_id = item.get("id")
        assertions = {str(ref) for ref in as_list(item.get("assertion_refs"))}
        covered.update(assertions)
        check(item.get("kind") in {"behavior_slice", "engineering_slice", "readiness_slice"}, f"切片 {slice_id} 类型合法")
        check(all(re.fullmatch(r"CHK-[A-Za-z0-9_-]+", str(ref)) for ref in as_list(item.get("check_refs"))), f"切片 {slice_id} 的 CHK 引用格式合法")
        check(all(re.fullmatch(r"AST-[A-Za-z0-9_-]+", str(ref)) for ref in assertions), f"切片 {slice_id} 的 AST 引用格式合法")
        if item.get("kind") == "behavior_slice":
            check(bool(as_list(item.get("production_refs"))), f"行为切片 {slice_id} 有生产引用")
            check(bool(as_list(item.get("test_refs"))) or (assertions and assertions <= exemptions), f"行为切片 {slice_id} 有测试引用或合法豁免")
    if matrix_file:
        matrix_doc = load_embedded_yaml(matrix_file)
        matrix = as_dict(matrix_doc.get("acceptance_matrix"))
        required_ast = {
            str(as_dict(assertion).get("id"))
            for check_item in as_list(matrix.get("checks"))
            if as_dict(check_item).get("required") is True
            for assertion in as_list(as_dict(check_item).get("assertions"))
        }
        check(required_ast <= covered, f"当前矩阵必需 AST 均有切片覆盖（缺失：{', '.join(sorted(required_ast - covered)) or '无'}）")
    else:
        check(False, "覆盖预检必须提供 --matrix-file 以核对当前矩阵必需 AST")
    return not errors, lines + errors


def review(plan_file: Path, event_file: Path, repository_override: Path | None) -> tuple[bool, list[str]]:
    plan_doc = load_yaml(plan_file)
    event_doc = load_yaml(event_file)
    plan = as_dict(plan_doc.get("implementation_plan"))
    event = as_dict(event_doc.get("event"))
    implementation = as_dict(event.get("implementation"))
    errors: list[str] = []
    checks: list[str] = []

    def check(condition: bool, message: str) -> None:
        (checks if condition else errors).append(("PASSED: " if condition else "FAILED: ") + message)

    check(plan_doc.get("document_type") == "implementation_plan", "实现计划文档类型正确")
    check(event_doc.get("document_type") == "deep_crew_delivery_event", "实现事件文档类型正确")
    check(event.get("node") == "IMPLEMENTATION", "事件节点为 IMPLEMENTATION")
    check(implementation.get("status") == "READY", "实现事件状态为 READY")

    plan_slices = {str(as_dict(item).get("id")): as_dict(item) for item in as_list(plan.get("slices"))}
    event_items = as_list(implementation.get("completed_items"))
    event_slice_ids = {str(as_dict(item).get("id")) for item in event_items}
    check(bool(event_items), "实现事件包含 completed_items")
    check(event_slice_ids <= set(plan_slices), "事件 completed_items 均能在实现计划中找到")

    plan_assertions: set[str] = set()
    for slice_item in plan_slices.values():
        kind = slice_item.get("kind")
        assertion_refs = {str(ref) for ref in as_list(slice_item.get("assertion_refs"))}
        plan_assertions.update(assertion_refs)
        if kind == "behavior_slice":
            has_exemption = assertion_refs and assertion_refs <= {
                str(ref)
                for exemption in as_list(as_dict(plan.get("test_strategy")).get("exemptions"))
                for ref in as_list(as_dict(exemption).get("assertion_refs"))
            }
            check(bool(as_list(slice_item.get("production_refs"))), f"行为切片 {slice_item.get('id')} 有生产引用")
            check(bool(as_list(slice_item.get("test_refs"))) or has_exemption, f"行为切片 {slice_item.get('id')} 有测试引用或合法豁免")
        check(slice_item.get("status") == "COMPLETED", f"切片 {slice_item.get('id')} 状态为 COMPLETED")

    event_assertions: set[str] = set()
    for item in event_items:
        event_assertions.update(str(ref) for ref in as_list(as_dict(item).get("assertion_refs")))
    check(event_assertions <= plan_assertions, "事件 assertion_refs 均属于实现计划")

    change_surface = as_dict(implementation.get("change_surface"))
    repository = as_dict(implementation.get("repository"))
    root = repository_override or Path(str(repository.get("worktree_root", "")))
    check(root.is_dir(), f"目标工作树存在：{root}")
    commit = implementation.get("git_commit")
    check(isinstance(commit, str) and len(commit) == 40 and all(char in "0123456789abcdef" for char in commit), "git_commit 是 40 位小写 SHA")

    changed_files: set[str] = set()
    if root.is_dir() and isinstance(commit, str):
        try:
            top = run_git(root, "rev-parse", "--show-toplevel")
            expected_top = str(Path(str(repository.get("git_toplevel", ""))).resolve())
            check(str(Path(top).resolve()) == expected_top, "Git 根目录与事件一致")
            check(run_git(root, "cat-file", "-e", f"{commit}^{{commit}}") == "", "绑定 commit 对象真实存在")
            check(run_git(root, "rev-parse", "HEAD") == commit, "绑定 commit 等于当前 HEAD")
            status = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"], check=False, capture_output=True, text=True)
            check(status.returncode == 0 and not status.stdout.strip(), "tracked 工作区干净")
            changed_files = set(
                run_git(
                    root,
                    "-c",
                    "core.quotePath=false",
                    "diff-tree",
                    "--no-commit-id",
                    "--name-only",
                    "-r",
                    commit,
                ).splitlines()
            )
        except ReviewError as error:
            errors.append(f"FAILED: {error}")

    file_fields = ("production_files", "test_files", "scripts")
    declared_files = {str(path) for field in file_fields for path in as_list(change_surface.get(field))}
    for path in sorted(declared_files):
        check(path in changed_files, f"变更面文件出现在 commit diff：{path}")
        check((root / path).is_file(), f"变更面文件在工作树存在：{path}")

    development_checks = as_list(implementation.get("development_checks"))
    check(bool(development_checks), "实现事件包含逐条 development_checks")
    for index, item in enumerate(development_checks, start=1):
        check(isinstance(as_dict(item).get("command"), str) and nonempty(as_dict(item).get("command")), f"开发检查 {index} 有命令")
        check(as_dict(item).get("status") == "PASSED", f"开发检查 {index} 状态为 PASSED")
        check(nonempty(as_dict(item).get("summary")) and as_dict(item).get("summary") not in {"全部通过", "测试通过"}, f"开发检查 {index} 有非汇总摘要")

    completion_review = as_dict(plan.get("completion_review"))
    check(completion_review.get("preflight", {}).get("status") == "PASSED", "计划记录自测前覆盖预检通过")
    check(completion_review.get("performed_after_self_test") is True, "计划记录复核发生在自测之后")
    program = as_dict(completion_review.get("program"))
    check(program.get("status") == "PASSED", "计划记录程序化完成复核通过")
    check(nonempty(program.get("report")), "计划记录程序化复核报告定位")
    semantic = as_dict(completion_review.get("semantic"))
    check(semantic.get("status") == "PASSED", "计划记录 Agent 语义完成复核通过")
    reviewed = {str(ref) for ref in as_list(semantic.get("reviewed_assertions"))}
    check(plan_assertions <= reviewed, "计划中的行为断言均已被语义复核记录")

    report = checks + errors
    return not errors, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-file", required=True, type=Path)
    parser.add_argument("--event-file", type=Path)
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--report-file", type=Path)
    parser.add_argument("--phase", choices=["preflight", "completion"], default="completion")
    parser.add_argument("--matrix-file", type=Path, help="自测前覆盖预检使用的验收矩阵 Markdown 文件")
    args = parser.parse_args()
    try:
        if args.phase == "preflight":
            passed, lines = preflight(args.plan_file, args.matrix_file)
        else:
            if args.event_file is None:
                raise ReviewError("completion 阶段必须提供 --event-file")
            passed, lines = review(args.plan_file, args.event_file, args.repository_root)
    except ReviewError as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1
    output = "\n".join(lines) + "\n"
    if args.report_file:
        args.report_file.parent.mkdir(parents=True, exist_ok=True)
        args.report_file.write_text(output, encoding="utf-8")
    print(output, end="")
    if passed:
        print("COMPLETION_REVIEW: PASSED")
        return 0
    print(f"COMPLETION_REVIEW: FAILED ({sum(line.startswith('FAILED:') for line in lines)} 个失败)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
