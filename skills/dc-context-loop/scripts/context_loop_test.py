#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml

from req_model import requirement_digest

SCRIPT_DIR = Path(__file__).resolve().parent
PROOF_SCRIPT_DIR = SCRIPT_DIR
KIT_ROOT = SCRIPT_DIR.parent.parent
LEGACY_RESOURCE_DIR_NAME = "dc-" + "proof-resources"
INTERNALIZED_RESOURCES = {
    "contracts/failure-types.yaml": "dc-context-loop/contracts/failure-types.yaml",
    "templates/需求清单.md": "dc-context-loop/templates/需求清单.md",
    "scripts/req_model.py": "dc-context-loop/scripts/req_model.py",
    "scripts/validate_delivery_proof.py": "dc-context-loop/scripts/validate_delivery_proof.py",
    "scripts/render_delivery_review.py": "dc-context-loop/scripts/render_delivery_review.py",
    "references/workflow-contract.md": "dc-context-loop/references/workflow-contract.md",
    "references/glossary.md": "dc-context-loop/references/glossary.md",
    "contracts/requirement.schema.yaml": "dc-requirement-slicing/contracts/requirement.schema.yaml",
    "templates/需求.md": "dc-requirement-slicing/templates/需求.md",
    "references/requirement-discovery.md": "dc-requirement-slicing/references/requirement-discovery.md",
    "contracts/acceptance-scenario.schema.yaml": "dc-acceptance-design/contracts/acceptance-scenario.schema.yaml",
    "contracts/acceptance-matrix.schema.yaml": "dc-acceptance-design/contracts/acceptance-matrix.schema.yaml",
    "templates/验收场景.md": "dc-acceptance-design/templates/验收场景.md",
    "templates/验收矩阵.md": "dc-acceptance-design/templates/验收矩阵.md",
    "contracts/implementation-plan.schema.yaml": "dc-implementation-execution/contracts/implementation-plan.schema.yaml",
    "templates/实现计划.md": "dc-implementation-execution/templates/实现计划.md",
    "references/implementation-planning.md": "dc-implementation-execution/references/implementation-planning.md",
    "references/tdd-rules.md": "dc-implementation-execution/references/tdd-rules.md",
    "references/testing-public-behavior.md": "dc-implementation-execution/references/testing-public-behavior.md",
    "references/mocking-boundaries.md": "dc-implementation-execution/references/mocking-boundaries.md",
    "references/test-data-policy.md": "dc-implementation-execution/references/test-data-policy.md",
    "contracts/test-evidence.schema.yaml": "dc-acceptance-verification/contracts/test-evidence.schema.yaml",
    "templates/测试证据.md": "dc-acceptance-verification/templates/测试证据.md",
    "references/evidence-recording.md": "dc-acceptance-verification/references/evidence-recording.md",
    "contracts/acceptance-report.schema.yaml": "dc-acceptance-closure/contracts/acceptance-report.schema.yaml",
    "templates/验收报告.md": "dc-acceptance-closure/templates/验收报告.md",
}


def require_operation_temp_environment() -> Path:
    raw_workspace = os.environ.get("DC_LOOP_OPERATION_WORKSPACE")
    if not raw_workspace:
        raise RuntimeError("必须通过 operation_workspace.py exec 运行测试")
    workspace = Path(raw_workspace).expanduser().resolve()
    if not workspace.is_dir() or workspace.parent.name != "tmp" or workspace.parent.parent.name != "dc-loop" or workspace.parent.parent.parent.name != ".local":
        raise RuntimeError(f"DC_LOOP_OPERATION_WORKSPACE 不是项目内操作目录: {workspace}")
    for key in ("TMPDIR", "TMP", "TEMP", "PYTHONPYCACHEPREFIX"):
        value = os.environ.get(key)
        if not value or not Path(value).expanduser().resolve().is_relative_to(workspace):
            raise RuntimeError(f"{key} 必须位于操作目录内")
    tempfile.tempdir = os.environ["TMPDIR"]
    return workspace


def requirement_event(event_id: str, *, requirement_id: str = "REQ-001", statement: str = "用户能够理解登录失败原因") -> dict:
    return {
        "document_type": "deep_crew_delivery_event",
        "event": {
            "event_id": event_id,
            "created_at": "2026-08-26T10:00:00+09:00",
            "author": "tester",
            "node": "REQ",
            "reason": "整理当前完整需求",
            "references": {"issue": "http://example/issues/1"},
            "requirement": {
                "id": requirement_id,
                "title": "登录失败反馈",
                "statement": statement,
                "business_outcomes": ["用户能够判断下一步操作"],
                "scope": {"included": ["Web 登录"], "excluded": ["账号注册"]},
                "constraints": ["继续使用现有认证服务"],
                "open_questions": [],
            },
        },
    }


def canonical_requirement_event(event_id: str, **kwargs: Any) -> dict:
    event = requirement_event(event_id, **kwargs)
    requirement = event["event"]["requirement"]
    requirement["issue_no"] = "HTW-1"
    requirement["dependencies"] = []
    return event


def requirement_document(*, requirement_id: str = "REQ-001", issue_no: object = "HTW-1") -> dict:
    return {
        "document_type": "requirement",
        "requirement": {
            "id": requirement_id,
            "status": "DRAFT",
            "issue_no": issue_no,
            "title": "登录失败反馈",
            "statement": "用户能够理解登录失败原因",
            "business_outcomes": ["用户能够判断下一步操作"],
            "scope": {"included": ["Web 登录"], "excluded": ["账号注册"]},
            "constraints": ["继续使用现有认证服务"],
            "dependencies": [],
            "open_questions": [],
            "release_notes": "整理当前完整需求",
            "source_refs": ["http://example/issues/1"],
            "confirmation": None,
        },
    }


def write_requirement(path: Path, document: dict) -> None:
    machine = yaml.safe_dump(document, allow_unicode=True, sort_keys=False).rstrip()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# 测试需求\n\n<!-- DELIVERY_PROOF_YAML_START -->\n```yaml\n{machine}\n```\n<!-- DELIVERY_PROOF_YAML_END -->\n",
        encoding="utf-8",
    )


def comment(comment_id: str, created_at: str, document: dict) -> dict:
    machine = yaml.safe_dump(document, allow_unicode=True, sort_keys=False).strip()
    return {
        "id": comment_id,
        "created_at": created_at,
        "content": f"<!-- DEEP_CREW_EVENT_START -->\n```yaml\n{machine}\n```\n<!-- DEEP_CREW_EVENT_END -->",
    }


def specification_event(event_id: str, *, scenario_id: str = "SCN-001", title: str = "登录失败") -> dict:
    return {
        "document_type": "deep_crew_delivery_event",
        "event": {
            "event_id": event_id,
            "created_at": "2026-08-26T10:00:00+09:00",
            "author": "tester",
            "node": "SPEC",
            "reason": "整理当前完整验收规格",
            "subject_id": "SPEC-001",
            "specification": {
                "requirement_ref": "REQ-001",
                "scenarios": [{
                    "id": scenario_id,
                    "title": title,
                    "business_result": "用户理解登录失败原因",
                    "given": ["用户已打开登录入口"],
                    "when": "用户提交错误密码",
                    "then": [{"id": "THEN-001", "statement": "系统拒绝登录"}],
                    "delivery_surfaces": ["web"],
                }],
                "checks": [{
                    "id": "CHK-001",
                    "scenario_ids": [scenario_id],
                    "verification_type": "api",
                    "responsibility": "验证错误密码被拒绝",
                    "required": True,
                    "blocking": True,
                }],
                "assertions": [{
                    "id": "AST-001",
                    "check_id": "CHK-001",
                    "outcome_refs": [f"{scenario_id}.THEN-001"],
                    "assertion_type": "semantic",
                    "description": "登录请求被拒绝",
                }],
                "open_questions": [],
            },
        },
    }


def incremental_specification_event(event_id: str = "EVT-SPEC-DELTA") -> dict:
    return {
        "document_type": "deep_crew_delivery_event",
        "event": {
            "event_id": event_id,
            "created_at": "2026-08-30T10:00:00+09:00",
            "author": "tester",
            "node": "SPEC",
            "reason": "记录相对基础 SPEC 的增量变化",
            "subject_id": "SPEC-002",
            "specification": {
                "requirement_ref": "REQ-001",
                "base_spec_ref": "SPEC-002",
                "changes": {
                    "added": {
                        "scenarios": [{
                            "id": "SCN-002",
                            "title": "明确验收授权",
                            "business_result": "只有明确授权才开始验收",
                            "given": ["实现状态为 READY"],
                            "when": "用户明确说执行验收",
                            "then": [{"id": "THEN-002", "statement": "系统进入验收流程"}],
                            "delivery_surfaces": ["skill"],
                        }],
                        "checks": [{
                            "id": "CHK-002",
                            "scenario_ids": ["SCN-002"],
                            "verification_type": "e2e",
                            "responsibility": "验证明确授权后进入验收",
                            "required": True,
                            "blocking": True,
                        }],
                        "assertions": [{
                            "id": "AST-002",
                            "check_id": "CHK-002",
                            "outcome_refs": ["SCN-002.THEN-002"],
                            "assertion_type": "semantic",
                            "description": "明确授权后才进入验收",
                        }],
                    },
                    "modified": {"scenarios": [], "checks": [], "assertions": []},
                    "removed": {"scenarios": [], "checks": [], "assertions": []},
                },
                "open_questions": [],
            },
        },
    }


def implementation_event(
    event_id: str,
    *,
    subject_id: str = "IMP-001",
    git_commit: str = "a" * 40,
) -> dict:
    implementation = {
        "status": "READY",
        "requirement_ref": "REQ-001",
        "spec_refs": ["SCN-001", "CHK-001", "AST-001"],
        "summary": "完成登录失败响应并补齐开发测试。",
        "completed_items": [{
            "id": "SLICE-001",
            "title": "实现登录失败响应",
            "kind": "behavior_slice",
            "objective": "返回可理解的失败原因",
            "check_refs": ["CHK-001"],
            "assertion_refs": ["AST-001"],
        }],
        "change_surface": {
            "production_files": ["server/auth/login_handler.go"],
            "test_files": ["server/auth/login_handler_test.go"],
            "scripts": [],
            "new_interfaces": [],
            "changed_interfaces": ["POST /api/login"],
            "database_changes": [],
            "configuration_changes": [],
            "dependency_changes": [],
            "external_contract_changes": [],
        },
        "development_checks": [{
            "command": "go test ./server/auth/...",
            "status": "PASSED",
            "summary": "登录处理器测试通过。",
        }],
        "known_limits": [],
        "repository": {"worktree_root": "/tmp/example-worktree", "git_toplevel": "/tmp/example-worktree"},
        "git_commit": git_commit,
        "completion_review": {
            "status": "PASSED",
            "performed_after_self_test": True,
            "preflight": {"status": "PASSED", "report": "artifacts/completion-preflight.txt"},
            "program": {"status": "PASSED", "command": "python3 review_implementation.py", "report": "artifacts/completion-program.txt", "findings": []},
            "semantic": {"status": "PASSED", "reviewed_assertions": ["AST-001"], "findings": []},
        },
    }

    return {
        "document_type": "deep_crew_delivery_event",
        "event": {
            "event_id": event_id,
            "created_at": "2026-08-26T10:00:00+09:00",
            "author": "tester",
            "node": "IMPLEMENTATION",
            "subject_id": subject_id,
            "reason": "实现完成并形成交付总结",
            "implementation": implementation,
            "impact": {"affected_ids": ["REQ-001", "SCN-001", "CHK-001", "AST-001"], "next_actions": [{"action": "等待明确验收指令", "owner": "需求负责人"}]},
        },
    }


def relation_specification_event(event_id: str = "EVT-SPEC-RELATION") -> dict:
    document = specification_event(event_id)
    spec = document["event"]["specification"]
    spec["scenarios"][0].update({
        "title": "展示完整关系链",
        "business_result": "用户理解场景、切片、检查和断言的关系",
        "then": [{"id": "THEN-001", "statement": "关系表按 AST 展示语义"}],
    })
    spec["checks"][0]["responsibility"] = "验证关系表的语义和覆盖范围"
    spec["assertions"][0]["description"] = "关系表一行对应一个实际覆盖的 AST"
    return document


def acceptance_event(
    event_id: str,
    *,
    subject_id: str = "ACC-001",
    run_id: str = "RUN-001",
    artifact_id: str = "ART-001",
    git_commit: str = "a" * 40,
    mode: str = "targeted",
) -> dict:
    result = {
        "status": "SATISFIED",
        "requirement_ref": "REQ-001",
        "spec_refs": ["SCN-001", "CHK-001", "AST-001"],
        "implementation_refs": ["IMP-001"],
        "mode": mode,
        "scope_refs": {"scenarios": ["SCN-001"], "checks": ["CHK-001"], "assertions": ["AST-001"]},
        "req_completion_impact": "NONE" if mode == "targeted" else "ELIGIBLE",
        "repository": {"worktree_root": "/tmp/example-worktree", "git_toplevel": "/tmp/example-worktree"},
        "git_commit": git_commit,
        "runs": [{"id": run_id, "execution_type": "api", "purpose": "feature_verification", "scope": "focused", "check_refs": ["CHK-001"], "assertion_refs": ["AST-001"], "status": "PASSED"}],
        "artifacts": [{"id": artifact_id, "type": "api_exchange", "location": f"artifacts/{run_id}.json"}],
        "assertion_results": [{"assertion_id": "AST-001", "expected": "请求被拒绝", "observed": "返回 401", "status": "PASSED", "artifact_refs": [artifact_id], "evidence_locator": "response:1"}],
        "traceability": [{"scenario_id": "SCN-001", "check_ids": ["CHK-001"], "assertion_ids": ["AST-001"]}],
        "reason": "当前 commit 上的必需断言均有直接证据支持。",
    }
    return {
        "document_type": "deep_crew_delivery_event",
        "event": {
            "event_id": event_id,
            "created_at": "2026-08-26T10:00:00+09:00",
            "author": "tester",
            "node": "ACCEPTANCE",
            "subject_id": subject_id,
            "reason": "本地验收完成并形成结论",
            "acceptance": result,
            "impact": {"affected_ids": ["REQ-001"], "next_actions": []},
        },
    }


def load_script_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载脚本模块: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def implementation_plan_document() -> dict:
    return {
        "document_type": "implementation_plan",
        "implementation_plan": {
            "status": "READY",
            "slices": [{
                "id": "SLICE-001",
                "title": "实现登录失败响应",
                "kind": "behavior_slice",
                "objective": "返回可理解的失败原因",
                "production_refs": ["server/auth/login_handler.go"],
                "test_refs": ["server/auth/login_handler_test.go"],
                "assertion_refs": ["AST-001"],
                "status": "COMPLETED",
            }],
            "test_strategy": {"exemptions": []},
            "completion_review": {
                "status": "PASSED",
                "performed_after_self_test": True,
                "preflight": {"status": "PASSED", "report": "artifacts/preflight.txt"},
                "program": {"status": "PASSED", "command": "python3 review_implementation.py", "report": "artifacts/program.txt", "findings": []},
                "semantic": {"status": "PASSED", "reviewed_assertions": ["AST-001"], "findings": []},
            },
        },
    }
class ContextLoopTest(unittest.TestCase):
    def test_resources_are_internalized_by_unique_owner(self) -> None:
        target_paths = [KIT_ROOT / relative for relative in INTERNALIZED_RESOURCES.values()]
        self.assertEqual(len(target_paths), len(set(target_paths)))
        for source_name, relative in INTERNALIZED_RESOURCES.items():
            target = KIT_ROOT / relative
            self.assertTrue(target.exists(), f"{source_name} -> {target} 缺少目标资源")
            self.assertTrue(target.is_file(), str(target))
        self.assertFalse((KIT_ROOT / LEGACY_RESOURCE_DIR_NAME).exists())

    def test_active_skill_package_has_no_legacy_resource_path_references(self) -> None:
        legacy_path = LEGACY_RESOURCE_DIR_NAME
        scanned = []
        for path in KIT_ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            if path.suffix.lower() not in {".md", ".py", ".json", ".yaml", ".yml"}:
                continue
            content = path.read_text(encoding="utf-8")
            if legacy_path in content:
                scanned.append(str(path.relative_to(KIT_ROOT)))
        self.assertEqual(scanned, [], f"活跃技能包仍包含旧资源路径: {scanned}")

    def test_active_skill_package_has_no_host_install_path_references(self) -> None:
        forbidden_fragments = (
            "." + "agents/skills",
            "." + "codex/skills",
            "." + "claude/skills",
            "/" + "Users/",
            "dc-context-" + "loop-kit",
        )
        findings = []
        for path in KIT_ROOT.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".md", ".py", ".json", ".yaml", ".yml"}:
                continue
            content = path.read_text(encoding="utf-8")
            matches = [fragment for fragment in forbidden_fragments if fragment in content]
            if matches:
                findings.append((str(path.relative_to(KIT_ROOT)), matches))
        self.assertEqual(findings, [], f"活跃技能包仍绑定宿主安装路径: {findings}")

    def test_repository_tracks_one_source_tree_and_documents_flat_installation(self) -> None:
        raw_root = os.environ.get("DC_LOOP_PROJECT_ROOT")
        if not raw_root:
            self.skipTest("独立复制包不携带仓库级源码布局")
        root = Path(raw_root).expanduser().resolve()
        readme = (root / "README.md").read_text(encoding="utf-8")
        agents = (root / "AGENTS.md").read_text(encoding="utf-8")
        ignore = (root / ".gitignore").read_text(encoding="utf-8")
        legacy_wrapper = "." + "agents/skills/" + "dc-context-" + "loop-kit"
        self.assertNotIn(legacy_wrapper, readme)
        self.assertIn("根目录 `skills/`", readme)
        self.assertIn("平铺", readme)
        self.assertIn("](skills/", readme)
        self.assertIn("根目录 `skills/` 是唯一规范源码", agents)
        local_install_root = "." + "agents/skills/"
        self.assertIn(local_install_root, ignore)
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        self.assertTrue(any(path.startswith("skills/") for path in tracked))
        self.assertFalse(any(path.startswith(local_install_root) for path in tracked))

    def test_internalized_resources_match_saved_baseline_content(self) -> None:
        raw_baseline = os.environ.get("DC_LOOP_MIGRATION_BASELINE")
        if not raw_baseline:
            self.skipTest("独立复制包不携带仓库级迁移基线")
        baseline = Path(raw_baseline).expanduser().resolve()
        self.assertTrue(baseline.is_file(), f"显式迁移基线不存在: {baseline}")
        expected = {}
        for line in baseline.read_text(encoding="utf-8").splitlines():
            digest, _, source = line.partition("  ")
            source_parts = Path(source).parts
            self.assertIn(LEGACY_RESOURCE_DIR_NAME, source_parts, source)
            marker = source_parts.index(LEGACY_RESOURCE_DIR_NAME)
            expected[str(Path(*source_parts[marker + 1 :]))] = digest
        self.assertEqual(set(expected), set(INTERNALIZED_RESOURCES))
        for source_name, target_relative in INTERNALIZED_RESOURCES.items():
            target = KIT_ROOT / target_relative
            content = target.read_bytes()
            if source_name == "references/workflow-contract.md":
                current_command = b"<kit-dir>/dc-context-loop/scripts/render_delivery_review.py"
                previous_command = f"<kit-dir>/{LEGACY_RESOURCE_DIR_NAME}/scripts/render_delivery_review.py".encode()
                content = content.replace(current_command, previous_command)
            actual = hashlib.sha256(content).hexdigest()
            self.assertEqual(actual, expected[source_name], source_name)

    def test_independent_copy_runs_core_checks_without_source_path(self) -> None:
        if os.environ.get("DC_LOOP_SKIP_INDEPENDENT_COPY_TEST"):
            self.skipTest("避免独立复制测试递归")
        with tempfile.TemporaryDirectory() as temporary:
            install_roots = [
                Path(temporary) / "agent-a" / "skills",
                Path(temporary) / "nested" / "runtime-b" / "custom-skills-root",
            ]
            for index, copy_root in enumerate(install_roots, start=1):
                shutil.copytree(KIT_ROOT, copy_root)
                self.assertFalse((copy_root / LEGACY_RESOURCE_DIR_NAME).exists())
                workspace_script = copy_root / "dc-context-loop/scripts/operation_workspace.py"
                operation_id = f"copy-test-{index}"
                create = subprocess.run(
                    [sys.executable, str(workspace_script), "create", "--worktree-root", str(copy_root), "--operation-id", operation_id],
                    check=False, capture_output=True, text=True,
                )
                self.assertEqual(create.returncode, 0, create.stderr)
                operation = copy_root / ".local/dc-loop/tmp" / operation_id
                env = os.environ.copy()
                env["DC_LOOP_SKIP_INDEPENDENT_COPY_TEST"] = "1"
                env.pop("DC_LOOP_PROJECT_ROOT", None)
                env.pop("DC_LOOP_MIGRATION_BASELINE", None)
                run = subprocess.run(
                    [sys.executable, str(copy_root / "dc-context-loop/scripts/context_loop_test.py")],
                    check=False, capture_output=True, text=True, cwd=copy_root, env=env,
                )
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                cleanup = subprocess.run(
                    [sys.executable, str(workspace_script), "cleanup", "--worktree-root", str(copy_root), "--operation-id", operation_id, "--terminal-status", "SUCCESS"],
                    check=False, capture_output=True, text=True,
                )
                self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
                self.assertFalse(operation.exists())

    def test_new_numeric_implementation_requires_direct_spec_ref(self) -> None:
        document = implementation_event("EVT-IMP-NUMERIC", subject_id="IMP-001-01")
        document["event"]["implementation"]["spec_ref"] = "SPEC-001"
        specification = relation_specification_event()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            spec_file = root / "spec.yaml"
            output_dir = root / "out"
            comments_file = root / "comments.json"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            spec_file.write_text(yaml.safe_dump(specification, allow_unicode=True, sort_keys=False), encoding="utf-8")
            comments_file.write_text(json.dumps([]), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--spec-file", str(spec_file), "--issue", "HTW-1", "--comments-json", str(comments_file), "--output-dir", str(output_dir)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_numeric_implementation_rejects_mismatched_spec_ref(self) -> None:
        document = implementation_event("EVT-IMP-NUMERIC-BAD", subject_id="IMP-001-01")
        document["event"]["implementation"]["spec_ref"] = "SPEC-002"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("大编号必须与 spec_ref 一致", result.stderr)

    def test_legacy_implementation_remains_readable(self) -> None:
        document = implementation_event("EVT-IMP-LEGACY", subject_id="IMP-001")
        specification = relation_specification_event()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            spec_file = root / "spec.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            spec_file.write_text(yaml.safe_dump(specification, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--spec-file", str(spec_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_targeted_numeric_acceptance_requires_matching_implementation(self) -> None:
        document = acceptance_event("EVT-ACC-NUMERIC", subject_id="ACC-001-01-01")
        document["event"]["acceptance"]["implementation_refs"] = ["IMP-001-02"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("targeted ACC 编号必须与 implementation_refs 一致", result.stderr)

    def test_numeric_implementation_round_must_increase_within_spec(self) -> None:
        document = implementation_event("EVT-IMP-ROUND-02", subject_id="IMP-001-02")
        document["event"]["implementation"]["spec_ref"] = "SPEC-001"
        previous = implementation_event("EVT-IMP-ROUND-01", subject_id="IMP-001-01")
        previous["event"]["implementation"]["spec_ref"] = "SPEC-001"
        specification = relation_specification_event()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            spec_file = root / "spec.yaml"
            comments_file = root / "comments.json"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            spec_file.write_text(yaml.safe_dump(specification, allow_unicode=True, sort_keys=False), encoding="utf-8")
            comments_file.write_text(json.dumps([comment("c1", "2026-08-26T10:00:00+09:00", previous)]), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--spec-file", str(spec_file), "--issue", "HTW-1", "--comments-json", str(comments_file), "--output-dir", str(output_dir)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_numeric_implementation_round_rejects_non_increasing_history(self) -> None:
        document = implementation_event("EVT-IMP-ROUND-01-RETRY", subject_id="IMP-001-01")
        document["event"]["implementation"]["spec_ref"] = "SPEC-001"
        previous = implementation_event("EVT-IMP-ROUND-01", subject_id="IMP-001-01")
        previous["event"]["implementation"]["spec_ref"] = "SPEC-001"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            comments_file = root / "comments.json"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            comments_file.write_text(json.dumps([comment("c1", "2026-08-26T10:00:00+09:00", previous)]), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--comments-json", str(comments_file), "--output-dir", str(output_dir)],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("subject/对象 ID 已存在于 Issue 历史", result.stderr)

    def test_full_numeric_acceptance_is_valid(self) -> None:
        document = acceptance_event("EVT-ACC-ALL", subject_id="ACC-ALL-01", mode="full")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_numeric_spec_object_ids_require_three_digits_in_delta(self) -> None:
        document = {
            "document_type": "deep_crew_delivery_event",
            "event": {
                "event_id": "EVT-SPEC-DELTA-BAD-ID",
                "created_at": "2026-08-26T10:00:00+09:00",
                "author": "tester",
                "node": "SPEC",
                "subject_id": "SPEC-002",
                "reason": "更新规格",
                "specification": {
                    "requirement_ref": "REQ-001",
                    "base_spec_ref": "SPEC-001",
                    "changes": {
                        "added": {"scenarios": [], "checks": [], "assertions": []},
                        "modified": {"scenarios": [{"id": "SCN-12", "title": "非法", "business_result": "非法", "given": ["前置"], "when": "执行", "then": [{"id": "THEN-001", "statement": "结果"}], "delivery_surfaces": ["unit"]}], "checks": [], "assertions": []},
                        "removed": {"scenarios": [], "checks": [], "assertions": []},
                    },
                    "open_questions": [],
                },
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("数字编号必须为三位", result.stderr)
    def test_operation_exec_injects_project_local_temp_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = SCRIPT_DIR / "operation_workspace.py"
            created = subprocess.run(
                [sys.executable, str(script), "create", "--worktree-root", str(root), "--operation-id", "exec-1"],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            result = subprocess.run(
                [
                    sys.executable, str(script), "exec", "--worktree-root", str(root),
                    "--operation-id", "exec-1", "--", sys.executable, "-c",
                    "import json,os,tempfile; print(json.dumps({'tmp': tempfile.gettempdir(), 'workspace': os.environ.get('DC_LOOP_OPERATION_WORKSPACE'), 'pycache': os.environ.get('PYTHONPYCACHEPREFIX')}))",
                ],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            environment = json.loads(result.stdout)
            operation = (root / ".local" / "dc-loop" / "tmp" / "exec-1").resolve()
            self.assertTrue(Path(environment["tmp"]).is_relative_to(operation))
            self.assertEqual(Path(environment["workspace"]), operation)
            self.assertTrue(Path(environment["pycache"]).is_relative_to(operation))

    def test_operation_workspace_is_project_local_and_unique(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = SCRIPT_DIR / "operation_workspace.py"
            created = subprocess.run(
                [sys.executable, str(script), "create", "--worktree-root", str(root), "--operation-id", "acceptance-1"],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            path = Path(json.loads(created.stdout)["path"])
            self.assertEqual(path, (root / ".local" / "dc-loop" / "tmp" / "acceptance-1").resolve())
            duplicate = subprocess.run(
                [sys.executable, str(script), "create", "--worktree-root", str(root), "--operation-id", "acceptance-1"],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(duplicate.returncode, 0)
            traversal = subprocess.run(
                [sys.executable, str(script), "path", "--worktree-root", str(root), "--operation-id", "../outside"],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(traversal.returncode, 0)

    def test_operation_cleanup_is_scoped_and_preserves_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            index = root / "docs" / "交付证明" / "HTW-1.md"
            index.parent.mkdir(parents=True)
            index.write_text("index", encoding="utf-8")
            script = SCRIPT_DIR / "operation_workspace.py"
            create = subprocess.run(
                [sys.executable, str(script), "create", "--worktree-root", str(root), "--operation-id", "op-1"],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(create.returncode, 0, create.stderr)
            operation = root / ".local" / "dc-loop" / "tmp" / "op-1"
            (operation / "raw-output.txt").write_text("temporary", encoding="utf-8")
            cleaned = subprocess.run(
                [sys.executable, str(script), "cleanup", "--worktree-root", str(root), "--operation-id", "op-1", "--terminal-status", "SUCCESS"],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(cleaned.returncode, 0, cleaned.stderr)
            self.assertFalse(operation.exists())
            self.assertEqual(index.read_text(encoding="utf-8"), "index")

    def test_operation_workspace_rejects_external_tmp_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as outside:
            root = Path(temporary)
            target = root / ".local" / "dc-loop"
            target.mkdir(parents=True)
            (target / "tmp").symlink_to(outside, target_is_directory=True)
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "operation_workspace.py"), "create", "--worktree-root", str(root), "--operation-id", "escape"],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("越出", result.stderr)

    def test_operation_cleanup_requires_terminal_status(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "operation_workspace.py"), "cleanup", "--worktree-root", tempfile.gettempdir(), "--operation-id", "missing"],
            check=False, capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_legacy_event_cleanup_is_issue_scoped_and_preserves_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / ".local" / "dc-loop" / "drafts" / "HTW-1"
            other = root / ".local" / "dc-loop" / "drafts" / "HTW-2"
            current.mkdir(parents=True)
            other.mkdir(parents=True)
            (current / "IMP-002-事件.yaml").write_text("event", encoding="utf-8")
            (current / "SPEC-001-事件.yaml").write_text("event", encoding="utf-8")
            (current / "实现计划.md").write_text("keep", encoding="utf-8")
            (current / "notes.yaml").write_text("keep", encoding="utf-8")
            (other / "IMP-999-事件.yaml").write_text("keep", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "event_artifact_cleanup.py"),
                    "cleanup_legacy_drafts",
                    "--worktree-root", str(root),
                    "--issue-key", "HTW-1",
                ],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["count"], 2)
            self.assertFalse((current / "IMP-002-事件.yaml").exists())
            self.assertFalse((current / "SPEC-001-事件.yaml").exists())
            self.assertTrue((current / "实现计划.md").exists())
            self.assertTrue((current / "notes.yaml").exists())
            self.assertTrue((other / "IMP-999-事件.yaml").exists())

    def test_prepare_event_rejects_legacy_drafts_output(self) -> None:
        document = canonical_requirement_event("EVT-LEGACY-DRAFT-OUTPUT")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            requirement_file = root / "需求.md"
            output_dir = root / ".local" / "dc-loop" / "drafts" / "HTW-1"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            write_requirement(requirement_file, requirement_document())
            result = subprocess.run(
                [
                    sys.executable, str(SCRIPT_DIR / "prepare_event.py"),
                    "--event-file", str(event_file), "--requirement-file", str(requirement_file),
                    "--issue", "HTW-1", "--output-dir", str(output_dir),
                ],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("不得位于 .local/dc-loop/drafts", result.stderr)
            self.assertFalse(output_dir.exists())

    def test_repository_has_no_issue_level_delivery_index_entrypoint(self) -> None:
        self.assertFalse((SCRIPT_DIR / "delivery_index.py").exists())
        references = [
            SCRIPT_DIR.parent / "SKILL.md",
            SCRIPT_DIR.parent / "references" / "workflow-contract.md",
            SCRIPT_DIR.parent / "references" / "glossary.md",
        ]
        for path in references:
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("delivery_index.py", content, str(path))
            self.assertNotIn("docs/交付证明/<ISSUE-KEY>.md", content, str(path))

    def test_catalog_uses_issue_no_and_keeps_only_markdown_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "交付证明"
            write_requirement(root / "REQ-001" / "需求.md", requirement_document())
            result = subprocess.run(
                [sys.executable, str(PROOF_SCRIPT_DIR / "render_delivery_review.py"), str(root)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            catalog = (root / "需求清单.md").read_text(encoding="utf-8")
            self.assertIn("| REQ | Issue No | 需求状态 | 交付阶段 | 标题 |", catalog)
            self.assertIn("| [REQ-001](./REQ-001/需求.md) | HTW-1 |", catalog)
            files = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
            self.assertEqual(files, ["REQ-001/需求.md", "需求清单.md"])

    def test_catalog_and_targeted_validation_ignore_invalid_historical_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "交付证明"
            current_requirement = requirement_document(requirement_id="REQ-001")
            current_requirement["requirement"]["status"] = "CONFIRMED"
            current_requirement["requirement"]["confirmation"] = {
                "confirmed_by": "tester",
                "confirmed_at": "2026-09-08T10:00:00+08:00",
                "content_digest": requirement_digest(current_requirement["requirement"]),
            }
            current_scenarios = {
                "document_type": "acceptance_scenarios",
                "requirement_ref": {"requirement_id": "REQ-001"},
                "acceptance_scenarios": {
                    "status": "CONFIRMED",
                    "scenarios": [{
                        "id": "SCN-001",
                        "title": "当前规格",
                        "business_result": "当前需求可以独立完成规格门禁",
                        "given": ["当前 REQ 已确认"],
                        "when": "执行当前 REQ 完整校验",
                        "then": [{"id": "THEN-001", "statement": "当前规格通过校验"}],
                        "delivery_surfaces": ["skill"],
                    }],
                    "open_questions": [],
                    "confirmation": None,
                },
            }
            current_matrix = {
                "document_type": "acceptance_matrix",
                "requirement_ref": {"requirement_id": "REQ-001"},
                "acceptance_scenarios_ref": {"requirement_id": "REQ-001"},
                "acceptance_matrix": {
                    "status": "CONFIRMED",
                    "checks": [{
                        "id": "CHK-001",
                        "scenario_ids": ["SCN-001"],
                        "dependency_ids": [],
                        "verification_type": "unit",
                        "responsibility": "验证当前规格可独立通过门禁",
                        "assertions": [{
                            "id": "AST-001",
                            "description": "当前规格通过完整交付链校验",
                            "outcome_refs": ["SCN-001.THEN-001"],
                            "assertion_type": "semantic",
                        }],
                        "required": True,
                        "blocking": True,
                        "external_verification": None,
                    }],
                    "confirmation": None,
                },
            }
            write_requirement(root / "REQ-001" / "需求.md", current_requirement)
            write_requirement(root / "REQ-001" / "验收场景.md", current_scenarios)
            write_requirement(root / "REQ-001" / "验收矩阵.md", current_matrix)
            write_requirement(root / "REQ-OLD" / "需求.md", requirement_document(requirement_id="REQ-OLD"))
            historical_evidence = {
                "document_type": "test_evidence",
                "requirement_ref": {"requirement_id": "REQ-OLD"},
                "test_evidence": {
                    "git_commit": None,
                    "definition_digests": {},
                    "runs": [{"id": "RUN-OLD", "phase": "api_verification"}],
                    "artifacts": [],
                },
            }
            write_requirement(root / "REQ-OLD" / "测试证据.md", historical_evidence)

            render = subprocess.run(
                [sys.executable, str(PROOF_SCRIPT_DIR / "render_delivery_review.py"), str(root)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(render.returncode, 0, render.stderr)
            catalog = (root / "需求清单.md").read_text(encoding="utf-8")
            self.assertIn("REQ-001", catalog)
            self.assertIn("开发未开始", catalog)

            targeted = subprocess.run(
                [sys.executable, str(PROOF_SCRIPT_DIR / "validate_delivery_proof.py"), str(root / "REQ-001")],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(targeted.returncode, 0, targeted.stderr)

            health = subprocess.run(
                [sys.executable, str(PROOF_SCRIPT_DIR / "validate_delivery_proof.py"), str(root)],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(health.returncode, 0)
            self.assertIn("phase", health.stderr)

            invalid_gate = subprocess.run(
                [
                    sys.executable,
                    str(PROOF_SCRIPT_DIR / "validate_delivery_proof.py"),
                    "--gate",
                    "application-ready",
                    str(root),
                ],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(invalid_gate.returncode, 1)
            self.assertIn("必须指定一个 REQ 目录", invalid_gate.stderr)
            self.assertNotIn("Traceback", invalid_gate.stderr)

    def test_requirement_validation_rejects_missing_or_invalid_issue_no(self) -> None:
        for issue_no in (None, "htw-1", ["HTW-1", "HTW-2"]):
            with self.subTest(issue_no=issue_no), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "交付证明"
                document = requirement_document(issue_no=issue_no)
                if issue_no is None:
                    del document["requirement"]["issue_no"]
                write_requirement(root / "REQ-001" / "需求.md", document)
                result = subprocess.run(
                    [sys.executable, str(PROOF_SCRIPT_DIR / "validate_delivery_proof.py"), str(root)],
                    check=False, capture_output=True, text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("REQ-001", result.stderr)
                self.assertIn("issue_no", result.stderr)

    def test_prepare_req_event_requires_draft_business_content_match(self) -> None:
        document = canonical_requirement_event("EVT-REQ-CONSISTENT")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            requirement_file = root / "需求.md"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            write_requirement(requirement_file, requirement_document())
            result = subprocess.run(
                [
                    sys.executable, str(SCRIPT_DIR / "prepare_event.py"),
                    "--event-file", str(event_file), "--requirement-file", str(requirement_file),
                    "--issue", "HTW-1", "--output-dir", str(root / "out"),
                ],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = (root / "out" / "EVT-REQ-CONSISTENT.md").read_text(encoding="utf-8")
            for heading in ("## Issue No", "## 业务结果", "## 约束", "## 依赖", "## 未决事项", "## 发布说明"):
                self.assertIn(heading, content)

    def test_prepare_req_event_reports_each_drift_field(self) -> None:
        for field, changed in (
            ("title", "被篡改的标题"),
            ("business_outcomes", ["被篡改的业务结果"]),
            ("dependencies", [{"id": "DEP-001", "description": "被篡改的依赖", "related_requirement_id": None}]),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                document = canonical_requirement_event(f"EVT-REQ-DRIFT-{field.upper()}")
                document["event"]["requirement"][field] = changed
                event_file = root / "event.yaml"
                requirement_file = root / "需求.md"
                event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
                write_requirement(requirement_file, requirement_document())
                result = subprocess.run(
                    [
                        sys.executable, str(SCRIPT_DIR / "prepare_event.py"),
                        "--event-file", str(event_file), "--requirement-file", str(requirement_file),
                        "--issue", "HTW-1", "--output-dir", str(root / "out"),
                    ],
                    check=False, capture_output=True, text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"requirement.{field}", result.stderr)
                self.assertFalse((root / "out").exists())

    def test_preflight_accepts_spec_event_as_matrix_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plan_copy = Path(temporary) / "plan.md"
            plan_document = implementation_plan_document()
            plan_document["implementation_plan"]["status"] = "PLANNED"
            plan_document["implementation_plan"]["slices"][0]["assertion_refs"] = ["AST-002"]
            plan_copy.write_text(yaml.safe_dump(plan_document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            matrix_file = Path(temporary) / "spec-event.yaml"
            matrix_file.write_text(yaml.safe_dump(incremental_specification_event(), allow_unicode=True, sort_keys=False), encoding="utf-8")
            report = Path(temporary) / "preflight.txt"
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "review_implementation.py"), "--phase", "preflight", "--plan-file", str(plan_copy), "--matrix-file", str(matrix_file), "--report-file", str(report)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("COMPLETION_REVIEW: PASSED", result.stdout)

    def test_ready_waits_for_explicit_acceptance_authorization(self) -> None:
        loop_skill = (SCRIPT_DIR.parent / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`IMPLEMENTATION READY` 只是交给验收角色的条件，不是验收授权", loop_skill)
        self.assertIn("明确的“执行验收”“开始验收”“请验收”等指令", loop_skill)
        self.assertIn("没有明确验收指令时，硬停止在等待状态", loop_skill)
        self.assertIn("不调用 `dc-acceptance-verification`，不生成 `RUN`、`ART` 或 `ACC-*`", loop_skill)
        self.assertIn("“继续”“可以”“来吧”等泛化表达不构成验收授权", loop_skill)

    def test_acceptance_scope_modes_are_documented(self) -> None:
        loop_skill = (SCRIPT_DIR.parent / "SKILL.md").read_text(encoding="utf-8")
        closure_skill = (SCRIPT_DIR.parent.parent / "dc-acceptance-closure" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`targeted` 单次验收", loop_skill)
        self.assertIn("`full` 全量验收", loop_skill)
        self.assertIn("scope_refs.scenarios/checks/assertions", loop_skill)
        self.assertIn("只有 `full + SATISFIED` 才能使用 `ELIGIBLE`", loop_skill)
        self.assertIn("`targeted` 只能裁决指定 IMP 的完整切片", closure_skill)

    def test_routing_contract_distinguishes_spec_change(self) -> None:
        loop_skill = (SCRIPT_DIR.parent / "SKILL.md").read_text(encoding="utf-8")
        slicing_skill = (SCRIPT_DIR.parent.parent / "dc-requirement-slicing" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("SPEC_CHANGE", loop_skill)
        self.assertIn("业务承诺不变，但场景、CHK、AST、验证责任或验证方式变化", loop_skill)
        self.assertIn("SPEC_CHANGE", slicing_skill)
        self.assertIn("只有业务承诺变化才发布 REQ", slicing_skill)

    def test_implementation_requires_completion_review_before_ready(self) -> None:
        implementation_skill = (SCRIPT_DIR.parent.parent / "dc-implementation-execution" / "SKILL.md").read_text(encoding="utf-8")
        planning_reference = (SCRIPT_DIR.parent.parent / "dc-implementation-execution" / "references" / "implementation-planning.md").read_text(encoding="utf-8")
        self.assertIn("自测前覆盖预检", implementation_skill)
        self.assertIn("自测后程序化完成复核", implementation_skill)
        self.assertIn("自测后 Agent 语义完成复核", implementation_skill)
        self.assertIn("固定 commit → 发布 READY", implementation_skill)
        self.assertIn("completion_review", planning_reference)

    def test_completion_review_assigns_program_and_agent_responsibilities(self) -> None:
        loop_skill = (SCRIPT_DIR.parent / "SKILL.md").read_text(encoding="utf-8")
        implementation_skill = (SCRIPT_DIR.parent.parent / "dc-implementation-execution" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("程序检查计划覆盖、引用、文件变更、开发检查记录、阻塞状态和 Git 事实", loop_skill)
        self.assertIn("程序不得从“文件存在”推断业务行为已经实现", implementation_skill)
        self.assertIn("Agent 必须逐一对照当前 REQ、SPEC", implementation_skill)

    def test_spec_confirmation_requires_clickable_draft_link(self) -> None:
        loop_skill = (SCRIPT_DIR.parent / "SKILL.md").read_text(encoding="utf-8")
        design_skill = (SCRIPT_DIR.parent.parent / "dc-acceptance-design" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("人类可点击的草案文件链接", loop_skill)
        self.assertIn("确认前必须给出可点击的草案文件链接", design_skill)
        self.assertIn("确认前不得发布对应 REQ/SPEC 事件", loop_skill)

    def test_spec_draft_is_single_schema_validated_source(self) -> None:
        design_skill = (SCRIPT_DIR.parent.parent / "dc-acceptance-design" / "SKILL.md").read_text(encoding="utf-8")
        workflow_contract = (SCRIPT_DIR.parent / "references" / "workflow-contract.md").read_text(encoding="utf-8")
        self.assertIn("SPEC 事件 YAML 必须先通过事件 Schema 校验", design_skill)
        self.assertIn("render_spec_draft.py", design_skill)
        self.assertIn("禁止手工拼接第二份内容", design_skill)
        self.assertIn("确认前标准 `验收场景.md` 和 `验收矩阵.md` 保持 `DRAFT`", design_skill)
        self.assertIn("草案、场景文件、矩阵文件和正式事件必须使用同一份 SPEC 数据", workflow_contract)

    def test_acceptance_design_uses_sequential_scn_ids(self) -> None:
        design_skill = (SCRIPT_DIR.parent.parent / "dc-acceptance-design" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("未占用的三位序号", design_skill)
        self.assertIn("`SCN-001`、`SCN-002`、`SCN-003`", design_skill)
        self.assertIn("不得拼接需求名称、草稿状态、标题或其他语义", design_skill)
        self.assertIn("复用同一个 SCN ID", design_skill)
        self.assertIn("更新场景沿用已有 ID", design_skill)

    def test_issue_intake_is_loop_owned_and_conditionally_gated(self) -> None:
        loop_skill = (SCRIPT_DIR.parent / "SKILL.md").read_text(encoding="utf-8")
        grilling_skill = (SCRIPT_DIR.parent.parent / "dc-grilling" / "SKILL.md").read_text(encoding="utf-8")
        implementation_skill = (SCRIPT_DIR.parent.parent / "dc-implementation-execution" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("完整 `dc-issue-intake` 只在读取门禁命中时触发", loop_skill)
        self.assertIn("普通交互复用当前动作上下文", loop_skill)
        self.assertIn("读取门禁按可观察条件而非对话轮次计算", loop_skill)
        self.assertIn("SPEC 和 IMPLEMENTATION 在上下文有效且没有刷新信号时复用当前已确认定义和 Issue context", loop_skill)
        self.assertIn("当前上下文缺失、存在冲突、关键引用无法确认、用户明确说明 Issue 已变化", loop_skill)
        self.assertIn("首次处理 Issue、设计 REQ、正式验收开始前和用户明确刷新时执行完整 intake", loop_skill)
        self.assertIn("验收失败后重新设计或调整实现时不因动作本身自动刷新", loop_skill)
        self.assertIn("完整刷新失败或刷新后仍无法裁决时，不调用 SPEC/IMPLEMENTATION 节点技能", loop_skill)
        self.assertIn("每轮只处理一个责任节点", loop_skill)
        self.assertIn("最多调用一个节点技能", loop_skill)
        self.assertIn("最多发布一个结构化事件", loop_skill)
        self.assertIn("下游节点在下一轮先按读取门禁判断复用或刷新上下文", loop_skill)
        self.assertIn("本轮输出只报告事实、结果和下一轮入口", loop_skill)
        self.assertIn("intake 覆盖状态为 `FULL`", loop_skill)
        self.assertIn("节点技能不得自行调用 `dc-issue-intake`", loop_skill)
        self.assertIn("本技能不自行调用 `dc-issue-intake`", grilling_skill)
        self.assertIn("进入本技能后不调用 `dc-issue-intake`", implementation_skill)
        self.assertIn("不因进入 IMPLEMENTATION 动作本身重新读取", implementation_skill)
        self.assertIn("开始前复用 `dc-context-loop` 提供的当前有效 Issue context", (SCRIPT_DIR.parent.parent / "dc-acceptance-design" / "SKILL.md").read_text(encoding="utf-8"))
        self.assertNotIn("每轮开始都通过 `dc-issue-intake` 完整读取 Issue 评论", loop_skill)
        self.assertNotIn("每轮重新读取原始评论", loop_skill)
        self.assertNotIn("节点技能返回结果后重新调用 `dc-issue-intake`", loop_skill)
        self.assertNotIn("进入 REQ/SPEC/实现方案设计动作前", loop_skill)
        self.assertNotIn("下一个关键动作在其动作入口重新 intake", loop_skill)
        self.assertNotIn("每次开始都通过 `dc-issue-intake`", grilling_skill)
        self.assertNotIn("进入本技能后先调用 `dc-issue-intake`", implementation_skill)

    def test_event_attachments_are_machine_source_and_terminal_cleanup_is_documented(self) -> None:
        loop_skill = (SCRIPT_DIR.parent / "SKILL.md").read_text(encoding="utf-8")
        intake_skill = (SCRIPT_DIR.parent.parent / "dc-issue-intake" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("机器 YAML 附件", loop_skill)
        self.assertIn("操作工作区中的附件上传", loop_skill)
        self.assertIn("按操作工作区清理规则删除本地事件 YAML", loop_skill)
        self.assertIn("treat the referenced YAML attachment as the machine source", intake_skill)
        self.assertIn("parse it as `deep_crew_delivery_event`", intake_skill)
        self.assertIn("If the attachment is missing", intake_skill)

    def test_event_publication_uses_displayed_body_and_status_without_post_read(self) -> None:
        loop_skill = (SCRIPT_DIR.parent / "SKILL.md").read_text(encoding="utf-8")
        implementation_skill = (SCRIPT_DIR.parent.parent / "dc-implementation-execution" / "SKILL.md").read_text(encoding="utf-8")
        verification_skill = (SCRIPT_DIR.parent.parent / "dc-acceptance-verification" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("事件发布前，先在当前 Agent 上下文中完整展示人类摘要、事件标识和附件引用", loop_skill)
        self.assertIn("实际上传正文必须复用已展示的同一内容", loop_skill)
        self.assertIn("2xx 判定成功，非 2xx 判定失败，超时或无响应判定结果未知", loop_skill)
        self.assertIn("不执行发布确认后的 Issue 重读", loop_skill)
        self.assertIn("发布 API 的正文必须复用同一内容", implementation_skill)
        self.assertIn("发布结果只依据 API 状态码分类，不在发布后重新读取 Issue", implementation_skill)
        self.assertIn("发布结果只依据本次 `multica issue comment add` 调用结果", verification_skill)
        self.assertIn("不执行发布后的 Issue/附件读取或线上线下内容比对", verification_skill)
        self.assertIn("发布失败或结果未知时，不得声明本次验收操作为 `SATISFIED`", verification_skill)
        self.assertNotIn("线上读取确认", verification_skill)
        self.assertNotIn("下载或读取并比对内容", verification_skill)
        self.assertIn("只有用户提供或确认唯一 Issue 标识后才能执行 intake", loop_skill)
        self.assertIn("确认前不得调用 Issue 读取 API", loop_skill)

    def test_snapshot_rejects_unknown_fields(self) -> None:
        document = requirement_event("EVT-REQ-WITH-UNKNOWN")
        document["event"]["legacy"] = {"value": "不属于当前事件结构"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("event 存在未定义字段: legacy", result.stderr)

    def test_prepare_event_detects_duplicate(self) -> None:
        document = canonical_requirement_event("EVT-001")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            comments_file = root / "comments.json"
            requirement_file = root / "需求.md"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            write_requirement(requirement_file, requirement_document())
            comments_file.write_text(json.dumps({"comments": [comment("c1", "2026-08-26T10:00:00+09:00", document)]}, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--requirement-file", str(requirement_file), "--issue", "HTW-1", "--comments-json", str(comments_file), "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["duplicate"])

    def test_prepare_event_detects_duplicate_from_attachment_summary(self) -> None:
        document = canonical_requirement_event("EVT-ATTACHMENT-DUPLICATE")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            comments_file = root / "comments.json"
            requirement_file = root / "需求.md"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            write_requirement(requirement_file, requirement_document())
            comments_file.write_text(json.dumps({"comments": [{"id": "c1", "content": "## 机器事件附件\n\n- event_id：`EVT-ATTACHMENT-DUPLICATE`\n- YAML 附件：`REQ-001-事件.yaml`"}]}, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--requirement-file", str(requirement_file), "--issue", "HTW-1", "--comments-json", str(comments_file), "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["duplicate"])

    def test_initial_req_renders_structured_human_sections(self) -> None:
        document = canonical_requirement_event("EVT-REQ-001")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            requirement_file = root / "需求.md"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            write_requirement(requirement_file, requirement_document())
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--requirement-file", str(requirement_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = (output_dir / "EVT-REQ-001.md").read_text(encoding="utf-8")
            for heading in ("## 需求目标", "## 需求陈述", "## Issue No", "## 业务结果", "### 范围内", "### 范围外", "## 约束", "## 依赖", "## 未决事项", "## 发布说明"):
                self.assertIn(heading, content)
            self.assertNotIn("DEEP_CREW_EVENT_START", content)
            self.assertIn("EVT-REQ-001", content)
            attachment = output_dir / "REQ-001-事件.yaml"
            self.assertTrue(attachment.is_file())
            machine = yaml.safe_load(attachment.read_text(encoding="utf-8"))
            self.assertEqual(machine["event"]["event_id"], "EVT-REQ-001")
            self.assertEqual(machine["event"]["node"], "REQ")

    def test_unsupported_node_is_rejected(self) -> None:
        document = {
            "document_type": "deep_crew_delivery_event",
            "event": {
                "event_id": "EVT-UNSUPPORTED-001",
                "created_at": "2026-08-26T09:00:00+09:00",
                "author": "agent",
                "node": "UNSUPPORTED",
                "reason": "澄清需求边界",
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("node 非法: UNSUPPORTED", result.stderr)
            self.assertFalse((output_dir / "EVT-UNSUPPORTED-001.md").exists())

    def test_delivery_event_with_unknown_field_is_rejected(self) -> None:
        document = requirement_event("EVT-REQ-UNKNOWN-FIELD")
        document["event"]["unknown_field"] = {"value": "unexpected"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("event 存在未定义字段: unknown_field", result.stderr)

    def test_spec_renderer_renders_full_snapshot(self) -> None:
        # The assertions below intentionally check both semantic readability and layout width.
        document = specification_event("EVT-SPEC-RENDER")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = (output_dir / "EVT-SPEC-RENDER.md").read_text(encoding="utf-8")
            for subject_id in ("SCN-001", "CHK-001", "AST-001"):
                self.assertIn(subject_id, content)
            self.assertIn("当前验收规格", content)
            self.assertIn("SPEC-001 当前验收规格", content)
            self.assertNotIn("DEEP_CREW_EVENT_START", content)
            self.assertIn("YAML 附件：`SPEC-001-事件.yaml`", content)
            self.assertIn("| SCN | 标题 | 业务结果 | 交付面 |", content)
            self.assertIn("### 场景详情", content)
            self.assertIn("### 检查责任详情", content)
            self.assertIn("### 原子断言详情", content)
            self.assertIn("- When：用户提交错误密码", content)
            self.assertIn("SCN-001.THEN-001` · 登录失败：系统拒绝登录", content)
            self.assertIn("所属 CHK：`CHK-001` · 验证错误密码被拒绝", content)
            self.assertNotIn("| SCN | 标题 | 业务结果 | Given | When | Then | 交付面 |", content)
            self.assertNotIn("<br", content)

    def test_spec_draft_renderer_matches_prepare_event_comment(self) -> None:
        draft_document = specification_event("EVT-SPEC-DRAFT-CONSISTENCY")
        formal_document = specification_event("EVT-SPEC-FORMAL-CONSISTENCY")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            draft_file = root / "draft-event.yaml"
            formal_file = root / "formal-event.yaml"
            draft_output = root / "draft.md"
            formal_dir = root / "formal"
            draft_file.write_text(yaml.safe_dump(draft_document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            formal_file.write_text(yaml.safe_dump(formal_document, allow_unicode=True, sort_keys=False), encoding="utf-8")

            draft_result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "render_spec_draft.py"), "--event-file", str(draft_file), "--output-file", str(draft_output)],
                check=False, capture_output=True, text=True,
            )
            formal_result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(formal_file), "--issue", "HTW-1", "--output-dir", str(formal_dir)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(draft_result.returncode, 0, draft_result.stderr)
            self.assertEqual(formal_result.returncode, 0, formal_result.stderr)
            draft = draft_output.read_text(encoding="utf-8").replace("EVT-SPEC-DRAFT-CONSISTENCY", "EVT-SPEC-CONSISTENCY")
            formal = (formal_dir / "EVT-SPEC-FORMAL-CONSISTENCY.md").read_text(encoding="utf-8").replace("EVT-SPEC-FORMAL-CONSISTENCY", "EVT-SPEC-CONSISTENCY")
            self.assertEqual(draft, formal)

    def test_incremental_spec_validates_and_renders_changes(self) -> None:
        document = incremental_specification_event()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = (output_dir / "EVT-SPEC-DELTA.md").read_text(encoding="utf-8")
            self.assertIn("基础 SPEC", content)
            self.assertIn("SPEC-002", content)
            self.assertIn("新增", content)
            self.assertIn("SCN-002", content)
            self.assertIn("SPEC-002 验收规格增量", content)
            self.assertIn("### 新增场景", content)
            self.assertIn("### 新增检查责任", content)
            self.assertIn("### 新增原子断言", content)
            self.assertNotIn("| SCN | 标题 | 业务结果 | Given | When | Then | 交付面 |", content)

    def test_spec_draft_renderer_merges_incremental_view(self) -> None:
        base = specification_event("EVT-SPEC-BASE")
        base["event"]["subject_id"] = "SPEC-002"
        delta = incremental_specification_event("EVT-SPEC-DRAFT-DELTA")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base_file = root / "base.yaml"
            delta_file = root / "delta.yaml"
            output_file = root / "draft.md"
            base_file.write_text(yaml.safe_dump(base, allow_unicode=True, sort_keys=False), encoding="utf-8")
            delta_file.write_text(yaml.safe_dump(delta, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "render_spec_draft.py"), "--event-file", str(delta_file), "--base-spec-file", str(base_file), "--output-file", str(output_file)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = output_file.read_text(encoding="utf-8")
            self.assertIn("SPEC-002 验收规格增量", content)
            self.assertIn("SCN-002", content)
            self.assertIn("CHK-002", content)
            self.assertIn("AST-002", content)
            self.assertNotIn("DEEP_CREW_EVENT_START", content)
            self.assertIn("YAML 附件：`SPEC-002-事件.yaml`", content)
            self.assertIn("SCN-002.THEN-002` · 明确验收授权：系统进入验收流程", content)
            self.assertNotIn("SCN-001", content)
            self.assertNotIn("| SCN | 标题 | 业务结果 | Given | When | Then | 交付面 |", content)

    def test_req_draft_renderer_generates_human_readable_markdown_and_machine_block(self) -> None:
        document = canonical_requirement_event("EVT-REQ-DRAFT-RENDER")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_file = root / "需求草案.md"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "render_req_draft.py"), "--event-file", str(event_file), "--output-file", str(output_file)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            raw = output_file.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
            content = raw.decode("utf-8")
            for heading in ("## 需求目标", "## 需求陈述", "## Issue No", "## 业务结果", "## 范围", "## 约束", "## 依赖", "## 未决事项", "## 发布说明"):
                self.assertIn(heading, content)
            self.assertNotRegex(content, r"<\s*/?\s*[A-Za-z][^>]*>")
            machine = yaml.safe_load(content.split("```yaml", 1)[1].split("```", 1)[0])
            self.assertEqual(machine["document_type"], "requirement")
            self.assertEqual(machine["requirement"]["status"], "DRAFT")
            event_req = document["event"]["requirement"]
            for field in ("id", "issue_no", "title", "statement", "business_outcomes", "scope", "constraints", "dependencies", "open_questions"):
                self.assertEqual(machine["requirement"][field], event_req[field])
            self.assertEqual(machine["requirement"]["release_notes"], document["event"]["reason"])

    def test_req_draft_renderer_rejects_non_req_and_invalid_events(self) -> None:
        cases = []
        non_req = specification_event("EVT-NON-REQ-DRAFT")
        cases.append(non_req)
        invalid = canonical_requirement_event("EVT-INVALID-REQ-DRAFT")
        del invalid["event"]["requirement"]["issue_no"]
        cases.append(invalid)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, document in enumerate(cases):
                event_file = root / f"event-{index}.yaml"
                output_file = root / f"draft-{index}.md"
                event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(SCRIPT_DIR / "render_req_draft.py"), "--event-file", str(event_file), "--output-file", str(output_file)],
                    check=False, capture_output=True, text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output_file.exists())

    def test_spec_requires_spec_subject_id(self) -> None:
        document = specification_event("EVT-SPEC-MISSING-ID")
        del document["event"]["subject_id"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("event.subject_id 必须是非空字符串", result.stderr)

    def test_spec_rejects_non_spec_subject_id(self) -> None:
        document = specification_event("EVT-SPEC-BAD-ID")
        document["event"]["subject_id"] = "IMP-001"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SPEC 节点不能使用 subject_id: IMP-001", result.stderr)

    def test_incremental_spec_rejects_modified_object_without_id(self) -> None:
        document = incremental_specification_event("EVT-SPEC-DELTA-BAD")
        document["event"]["specification"]["changes"]["modified"]["scenarios"] = [{"title": "缺少 ID"}]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("modified.scenarios", result.stderr)

    def test_implementation_renders_completed_delivery(self) -> None:
        document = implementation_event("EVT-IMP-001", subject_id="IMP-001-01")
        document["event"]["implementation"]["spec_ref"] = "SPEC-001"
        specification = relation_specification_event()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            spec_file = root / "spec.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            spec_file.write_text(yaml.safe_dump(specification, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--spec-file", str(spec_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = (output_dir / "EVT-IMP-001.md").read_text(encoding="utf-8")
            self.assertIn("IMP-001-01 实现完成", content)
            self.assertIn("交付摘要", content)
            self.assertIn("## 覆盖摘要", content)
            self.assertIn("## 验收关系", content)
            self.assertIn("| 验收场景 | 实现切片 | 验收检查 | 原子断言 |", content)
            self.assertIn("展示完整关系链", content)
            self.assertIn("实现登录失败响应", content)
            self.assertIn("验证关系表的语义和覆盖范围", content)
            self.assertIn("关系表一行对应一个实际覆盖的 AST", content)
            self.assertEqual(content.count("`AST-001`"), 1)
            self.assertNotIn("## 绑定上下文", content)
            self.assertNotIn("## 已完成内容", content)
            self.assertNotIn("<br", content.lower())
            self.assertNotIn("<table", content.lower())
            self.assertIn("实际变更面", content)
            self.assertIn("server/auth/login_handler.go", content)
            self.assertIn("POST /api/login", content)
            self.assertIn("go test ./server/auth/...", content)
            self.assertIn("实现工作树：/tmp/example-worktree", content)
            self.assertIn("Git 根目录：/tmp/example-worktree", content)
            self.assertIn("完成前复核", content)
            self.assertIn("自测之后", content)
            attachment = yaml.safe_load((output_dir / "IMP-001-01-事件.yaml").read_text(encoding="utf-8"))
            self.assertEqual(attachment["event"]["implementation"]["spec_refs"], ["SCN-001", "CHK-001", "AST-001"])
            self.assertEqual(attachment["event"]["implementation"]["completed_items"], document["event"]["implementation"]["completed_items"])

    def test_implementation_expands_shared_scenario_and_check_per_slice_assertion(self) -> None:
        document = implementation_event("EVT-IMP-SHARED")
        document["event"]["implementation"]["completed_items"].append({
            "id": "SLICE-002",
            "title": "补充第二个实现切片",
            "kind": "behavior_slice",
            "objective": "由第二个切片覆盖同一断言",
            "check_refs": ["CHK-001"],
            "assertion_refs": ["AST-001"],
        })
        specification = relation_specification_event()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            spec_file = root / "spec.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            spec_file.write_text(yaml.safe_dump(specification, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--spec-file", str(spec_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = (output_dir / "EVT-IMP-SHARED.md").read_text(encoding="utf-8")
            relation_rows = [line for line in content.splitlines() if line.startswith("| ") and "`AST-001`" in line]
            self.assertEqual(len(relation_rows), 2)
            self.assertTrue(any("`SLICE-001`" in line for line in relation_rows))
            self.assertTrue(any("`SLICE-002`" in line for line in relation_rows))

    def test_implementation_comment_requires_complete_matching_spec(self) -> None:
        document = implementation_event("EVT-IMP-SPEC-GATE")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")

            missing = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(root / "missing")],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("--spec-file", missing.stderr)
            self.assertFalse((root / "missing").exists())

            specification = relation_specification_event()
            specification["event"]["specification"]["assertions"][0]["id"] = "AST-999"
            spec_file = root / "spec.yaml"
            spec_file.write_text(yaml.safe_dump(specification, allow_unicode=True, sort_keys=False), encoding="utf-8")
            mismatch = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--spec-file", str(spec_file), "--issue", "HTW-1", "--output-dir", str(root / "mismatch")],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(mismatch.returncode, 0)
            self.assertIn("不存在的对象: AST-001", mismatch.stderr)
            self.assertFalse((root / "mismatch").exists())

    def test_implementation_requires_completion_review(self) -> None:
        document = implementation_event("EVT-IMP-MISSING-REVIEW")
        del document["event"]["implementation"]["completion_review"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("completion_review", result.stderr)

    def test_programmatic_completion_review_catches_files_not_in_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in ("server/auth/login_handler.go", "server/auth/login_handler_test.go"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("initial\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=tester", "-c", "user.email=test@example.com", "commit", "-qm", "initial"], check=True)
            (root / "README.md").write_text("second commit\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=tester", "-c", "user.email=test@example.com", "commit", "-qm", "second"], check=True)
            commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            event = implementation_event("EVT-IMP-REVIEW-FAIL", git_commit=commit)
            event["event"]["implementation"]["repository"] = {"worktree_root": str(root), "git_toplevel": str(root)}
            event_file = root / "event.yaml"
            plan_file = root / "plan.yaml"
            report_file = root / "report.txt"
            event_file.write_text(yaml.safe_dump(event, allow_unicode=True, sort_keys=False), encoding="utf-8")
            plan_file.write_text(yaml.safe_dump(implementation_plan_document(), allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT_DIR / "review_implementation.py"), "--plan-file", str(plan_file), "--event-file", str(event_file), "--report-file", str(report_file)], check=False, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("变更面文件出现在 commit diff", result.stderr + result.stdout)

    def test_programmatic_completion_review_passes_when_files_are_in_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in ("server/auth/login_handler.go", "server/auth/login_handler_test.go"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("initial\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=tester", "-c", "user.email=test@example.com", "commit", "-qm", "initial"], check=True)
            (root / "server/auth/login_handler.go").write_text("implemented\n", encoding="utf-8")
            (root / "server/auth/login_handler_test.go").write_text("asserted\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=tester", "-c", "user.email=test@example.com", "commit", "-qm", "implementation"], check=True)
            commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            event = implementation_event("EVT-IMP-REVIEW-OK", git_commit=commit)
            event["event"]["implementation"]["repository"] = {"worktree_root": str(root), "git_toplevel": str(root)}
            event_file = root / "event.yaml"
            plan_file = root / "plan.yaml"
            event_file.write_text(yaml.safe_dump(event, allow_unicode=True, sort_keys=False), encoding="utf-8")
            plan_file.write_text(yaml.safe_dump(implementation_plan_document(), allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT_DIR / "review_implementation.py"), "--plan-file", str(plan_file), "--event-file", str(event_file)], check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("COMPLETION_REVIEW: PASSED", result.stdout)

    def test_programmatic_completion_review_supports_utf8_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = root / "文档/实现计划.md"
            test_file = root / "tests/实现计划_test.md"
            for path in (production, test_file):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("initial\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=tester", "-c", "user.email=test@example.com", "commit", "-qm", "initial"], check=True)
            production.write_text("implemented\n", encoding="utf-8")
            test_file.write_text("asserted\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=tester", "-c", "user.email=test@example.com", "commit", "-qm", "implementation"], check=True)
            commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            event = implementation_event("EVT-IMP-REVIEW-UTF8", git_commit=commit)
            event["event"]["implementation"]["repository"] = {"worktree_root": str(root), "git_toplevel": str(root)}
            event["event"]["implementation"]["change_surface"]["production_files"] = ["文档/实现计划.md"]
            event["event"]["implementation"]["change_surface"]["test_files"] = ["tests/实现计划_test.md"]
            event_file = root / "event.yaml"
            plan_file = root / "plan.yaml"
            event_file.write_text(yaml.safe_dump(event, allow_unicode=True, sort_keys=False), encoding="utf-8")
            plan_file.write_text(yaml.safe_dump(implementation_plan_document(), allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT_DIR / "review_implementation.py"), "--plan-file", str(plan_file), "--event-file", str(event_file)], check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_preflight_checks_current_matrix_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = implementation_plan_document()
            plan["implementation_plan"]["status"] = "IN_PROGRESS"
            plan_file = root / "plan.yaml"
            matrix_file = root / "验收矩阵.md"
            plan_file.write_text(yaml.safe_dump(plan, allow_unicode=True, sort_keys=False), encoding="utf-8")
            matrix_file.write_text("""```yaml\ndocument_type: acceptance_matrix\nacceptance_matrix:\n  checks:\n  - id: CHK-001\n    required: true\n    blocking: true\n    assertions:\n    - id: AST-001\n```\n""", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT_DIR / "review_implementation.py"), "--phase", "preflight", "--plan-file", str(plan_file), "--matrix-file", str(matrix_file)], check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("当前矩阵必需 AST 均有切片覆盖", result.stdout)

    def test_verify_git_binding_accepts_real_head(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "README.md").write_text("ok\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=tester", "-c", "user.email=test@example.com", "commit", "-qm", "init"], check=True)
            commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            document = implementation_event("EVT-IMP-GIT-OK", git_commit=commit)
            document["event"]["implementation"]["repository"] = {"worktree_root": str(root), "git_toplevel": str(root)}
            event_file = root / "event.yaml"
            spec_file = root / "spec.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            spec_file.write_text(yaml.safe_dump(relation_specification_event(), allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--spec-file", str(spec_file), "--issue", "HTW-1", "--verify-git", "--output-dir", str(output_dir)], check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_verify_git_binding_rejects_fake_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "README.md").write_text("ok\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=tester", "-c", "user.email=test@example.com", "commit", "-qm", "init"], check=True)
            document = implementation_event("EVT-IMP-GIT-BAD", git_commit="b" * 40)
            document["event"]["implementation"]["repository"] = {"worktree_root": str(root), "git_toplevel": str(root)}
            event_file = root / "event.yaml"
            spec_file = root / "spec.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            spec_file.write_text(yaml.safe_dump(relation_specification_event(), allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--spec-file", str(spec_file), "--issue", "HTW-1", "--verify-git", "--output-dir", str(output_dir)], check=False, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Git 校验失败", result.stderr)

    def test_implementation_rejects_unknown_fields(self) -> None:
        document = implementation_event("EVT-IMP-WITH-UNKNOWN")
        document["event"]["legacy"] = "过程状态"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("event 存在未定义字段: legacy", result.stderr)

    def test_acceptance_renders_one_final_conclusion(self) -> None:
        document = acceptance_event("EVT-ACC-001")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = (output_dir / "EVT-ACC-001.md").read_text(encoding="utf-8")
            self.assertIn("验收结论", content)
            self.assertIn("SATISFIED", content)
            self.assertIn("RUN-001", content)
            self.assertIn("ART-001", content)
            self.assertIn("AST-001", content)
            self.assertIn("targeted", content)
            self.assertIn("单次验收", content)

    def test_acceptance_run_requires_three_orthogonal_fields_and_rejects_phase(self) -> None:
        for field in ("execution_type", "purpose", "scope"):
            document = acceptance_event(f"EVT-ACC-MISSING-{field.upper()}")
            del document["event"]["acceptance"]["runs"][0][field]
            self.assert_satisfied_acceptance_rejected(document, field)

        invalid = acceptance_event("EVT-ACC-INVALID-RUN-DIMENSION")
        invalid["event"]["acceptance"]["runs"][0]["execution_type"] = "shell"
        self.assert_satisfied_acceptance_rejected(invalid, "execution_type")

        legacy = acceptance_event("EVT-ACC-LEGACY-PHASE")
        legacy["event"]["acceptance"]["runs"][0]["phase"] = "api_verification"
        self.assert_satisfied_acceptance_rejected(legacy, "phase")

    def test_run_contracts_define_orthogonal_dimensions(self) -> None:
        evidence_schema = yaml.safe_load((KIT_ROOT / "dc-acceptance-verification/contracts/test-evidence.schema.yaml").read_text(encoding="utf-8"))
        evidence_run = evidence_schema["properties"]["test_evidence"]["properties"]["runs"]["items"]
        acceptance_schema = yaml.safe_load((KIT_ROOT / "dc-context-loop/contracts/event.schema.yaml").read_text(encoding="utf-8"))
        acceptance_run = acceptance_schema["$defs"]["acceptance_result"]["properties"]["runs"]["items"]
        expected = {
            "execution_type": ["unit", "api", "ui", "e2e", "app_start", "cleanup"],
            "purpose": ["feature_verification", "regression", "test_data_management"],
            "scope": ["focused", "module", "impacted", "full"],
        }
        for run in (evidence_run, acceptance_run):
            self.assertTrue(set(expected).issubset(run["required"]))
            self.assertNotIn("phase", run["required"])
            self.assertTrue(all(run["properties"][key]["enum"] == values for key, values in expected.items()))
            self.assertIn({"required": ["phase"]}, run["not"]["anyOf"])

    def test_regression_purpose_does_not_grant_ast_coverage(self) -> None:
        validator = load_script_module("validate_delivery_proof_for_run_model", SCRIPT_DIR / "validate_delivery_proof.py")
        digests = {"requirement": "req", "scenarios": "scn", "matrix": "matrix"}
        regression = {
            "id": "RUN-REGRESSION",
            "execution_type": "unit",
            "purpose": "regression",
            "scope": "impacted",
            "check_refs": [],
            "assertion_refs": [],
            "supporting_run_refs": [],
            "artifact_refs": ["ART-REGRESSION"],
            "definition_digests": digests,
            "result": "PASSED",
        }
        evidence = {"git_commit": "a" * 40, "definition_digests": digests, "runs": [regression]}
        self.assertEqual(validator.acceptance_eligible_runs(evidence, digests), [])

        regression["check_refs"] = ["CHK-001"]
        regression["assertion_refs"] = ["AST-001"]
        self.assertEqual(validator.acceptance_eligible_runs(evidence, digests), [regression])

    def test_acceptance_renders_conclusion_first_and_markdown_traceability(self) -> None:
        document = acceptance_event("EVT-ACC-TRACEABILITY")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = (output_dir / "EVT-ACC-TRACEABILITY.md").read_text(encoding="utf-8")
            self.assertLess(content.index("## 最终结论"), content.index("## 验收基线"))
            self.assertIn("## 验收导航", content)
            self.assertIn("[`SCN-001`](#scn-001)", content)
            self.assertIn("[`CHK-001`](#chk-001)", content)
            self.assertIn("[`AST-001`](#ast-001)", content)
            self.assertIn("### SCN-001", content)
            self.assertIn("#### CHK-001", content)
            self.assertIn("##### AST-001", content)
            self.assertNotRegex(content, r"<\s*/?\s*[A-Za-z][^>]*>")
            self.assertIn("evidence_locator", content)

    def test_all_event_comments_are_html_free(self) -> None:
        cases = [
            (canonical_requirement_event("EVT-REQ-HTML-FREE"), None),
            (specification_event("EVT-SPEC-HTML-FREE"), None),
            (implementation_event("EVT-IMP-HTML-FREE"), relation_specification_event()),
            (acceptance_event("EVT-ACC-HTML-FREE"), None),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for document, specification in cases:
                event_id = document["event"]["event_id"]
                case_root = root / event_id
                case_root.mkdir()
                event_file = case_root / "event.yaml"
                output_dir = case_root / "out"
                event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
                command = [
                    sys.executable,
                    str(SCRIPT_DIR / "prepare_event.py"),
                    "--event-file",
                    str(event_file),
                    "--issue",
                    "HTW-1",
                    "--output-dir",
                    str(output_dir),
                ]
                if specification is not None:
                    spec_file = case_root / "spec.yaml"
                    spec_file.write_text(yaml.safe_dump(specification, allow_unicode=True, sort_keys=False), encoding="utf-8")
                    command.extend(["--spec-file", str(spec_file)])
                if document["event"]["node"] == "REQ":
                    requirement_file = case_root / "requirement.md"
                    write_requirement(requirement_file, requirement_document())
                    command.extend(["--requirement-file", str(requirement_file)])
                result = subprocess.run(command, check=False, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                content = (output_dir / f"{event_id}.md").read_text(encoding="utf-8")
                self.assertNotRegex(content, r"<\s*/?\s*[A-Za-z][^>]*>", event_id)

    def assert_satisfied_acceptance_rejected(self, document: dict, expected_error: str) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(expected_error, result.stderr)

    def test_satisfied_acceptance_requires_evidence_locator_for_every_assertion(self) -> None:
        document = acceptance_event("EVT-ACC-MISSING-LOCATOR")
        del document["event"]["acceptance"]["assertion_results"][0]["evidence_locator"]
        self.assert_satisfied_acceptance_rejected(document, "evidence_locator")

    def test_satisfied_acceptance_requires_parseable_evidence_locator(self) -> None:
        document = acceptance_event("EVT-ACC-BAD-LOCATOR")
        document["event"]["acceptance"]["assertion_results"][0]["evidence_locator"] = "somewhere"
        self.assert_satisfied_acceptance_rejected(document, "evidence_locator 格式非法")

    def test_satisfied_acceptance_requires_traceability(self) -> None:
        document = acceptance_event("EVT-ACC-MISSING-TRACEABILITY")
        del document["event"]["acceptance"]["traceability"]
        self.assert_satisfied_acceptance_rejected(document, "traceability")

    def test_satisfied_acceptance_rejects_run_refs_outside_scope(self) -> None:
        document = acceptance_event("EVT-ACC-RUN-OUTSIDE-SCOPE")
        run = document["event"]["acceptance"]["runs"][0]
        run["check_refs"] = ["CHK-999"]
        run["assertion_refs"] = ["AST-999"]
        self.assert_satisfied_acceptance_rejected(document, "范围外")

    def test_satisfied_acceptance_rejects_orphan_artifact(self) -> None:
        document = acceptance_event("EVT-ACC-ORPHAN-ARTIFACT")
        document["event"]["acceptance"]["artifacts"].append({
            "id": "ART-002",
            "type": "command_output",
            "location": "issue://HTW-1/attachments/ART-002",
        })
        self.assert_satisfied_acceptance_rejected(document, "孤立 ART")

    def test_satisfied_acceptance_requires_assertion_results_to_cover_scope(self) -> None:
        document = acceptance_event("EVT-ACC-INCOMPLETE-RESULTS")
        acceptance = document["event"]["acceptance"]
        acceptance["spec_refs"].append("AST-002")
        acceptance["scope_refs"]["assertions"].append("AST-002")
        acceptance["runs"][0]["assertion_refs"].append("AST-002")
        acceptance["traceability"][0]["assertion_ids"].append("AST-002")
        self.assert_satisfied_acceptance_rejected(document, "断言结果必须完整覆盖验收范围")

    def test_not_satisfied_acceptance_keeps_diagnostic_evidence_compatibility(self) -> None:
        document = acceptance_event("EVT-ACC-NOT-SATISFIED-COMPAT")
        acceptance = document["event"]["acceptance"]
        acceptance["status"] = "NOT_SATISFIED"
        acceptance["runs"][0]["status"] = "FAILED"
        acceptance["assertion_results"][0]["status"] = "FAILED"
        del acceptance["assertion_results"][0]["evidence_locator"]
        del acceptance["traceability"]
        acceptance["artifacts"].append({
            "id": "ART-002",
            "type": "command_output",
            "location": "issue://HTW-1/attachments/ART-002",
        })
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_full_acceptance_renders_full_scope(self) -> None:
        document = acceptance_event("EVT-ACC-FULL", subject_id="ACC-002", mode="full")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = (output_dir / "EVT-ACC-FULL.md").read_text(encoding="utf-8")
            self.assertIn("全量验收", content)
            self.assertIn("当前有效 SPEC", content)
            self.assertIn("REQ 完成资格", content)

    def test_targeted_acceptance_requires_one_implementation(self) -> None:
        document = acceptance_event("EVT-ACC-TARGETED-BAD")
        document["event"]["acceptance"]["implementation_refs"] = ["IMP-001", "IMP-002"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("targeted", result.stderr)

    def test_acceptance_rejects_unknown_fields(self) -> None:
        document = acceptance_event("EVT-ACC-WITH-UNKNOWN")
        document["event"]["legacy"] = "过程状态"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("event 存在未定义字段: legacy", result.stderr)


if __name__ == "__main__":
    try:
        require_operation_temp_environment()
    except RuntimeError as error:
        print(f"受控测试环境错误: {error}", file=sys.stderr)
        raise SystemExit(2)
    unittest.main()
