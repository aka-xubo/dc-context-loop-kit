#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent


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
        "runs": [{"id": run_id, "phase": "api_verification", "check_refs": ["CHK-001"], "assertion_refs": ["AST-001"], "status": "PASSED"}],
        "artifacts": [{"id": artifact_id, "type": "api_exchange", "location": f"artifacts/{run_id}.json"}],
        "assertion_results": [{"assertion_id": "AST-001", "expected": "请求被拒绝", "observed": "返回 401", "status": "PASSED", "artifact_refs": [artifact_id]}],
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

    def test_delivery_index_contains_only_issue_navigation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            req = requirement_event("EVT-HTW-1-REQ-001")
            spec = specification_event("EVT-HTW-1-SPEC-001")
            imp = implementation_event("EVT-HTW-1-IMP-001")
            acc = acceptance_event("EVT-HTW-1-ACC-001")
            comments = [
                comment("c-req", "2026-08-26T10:00:00+09:00", req),
                comment("c-spec", "2026-08-26T11:00:00+09:00", spec),
                comment("c-imp", "2026-08-26T12:00:00+09:00", imp),
                comment("c-acc", "2026-08-26T13:00:00+09:00", acc),
            ]
            comments_file = root / "comments.json"
            output_file = root / "docs" / "交付证明" / "HTW-1.md"
            comments_file.write_text(json.dumps({"comments": comments}, ensure_ascii=False), encoding="utf-8")
            command = [sys.executable, str(SCRIPT_DIR / "delivery_index.py"), "--issue-key", "HTW-1", "--issue-url", "http://example/issues/1", "--comments-json", str(comments_file), "--output-file", str(output_file), "--coverage", "FULL", "--synced-at", "2026-08-26T14:00:00+00:00"]
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            content = output_file.read_text(encoding="utf-8")
            self.assertIn("## SPEC（1）", content)
            self.assertIn("## IMPLEMENTATION（1）", content)
            self.assertIn("## ACCEPTANCE（1）", content)
            self.assertIn("comment `c-acc`", content)
            self.assertNotIn("DEEP_CREW_EVENT_START", content)
            self.assertNotIn("AST-001", content)
            checked = subprocess.run(command + ["--check"], check=False, capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_delivery_index_archives_explicit_legacy_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            proof = root / "docs" / "交付证明"
            legacy_req = proof / "REQ-OLD"
            legacy_req.mkdir(parents=True)
            (legacy_req / "验收报告.md").write_text("legacy", encoding="utf-8")
            legacy_catalog = proof / "需求清单.md"
            legacy_catalog.write_text("legacy catalog", encoding="utf-8")
            comments_file = root / "comments.json"
            comments_file.write_text(json.dumps({"comments": [comment("c1", "2026-08-26T10:00:00+09:00", requirement_event("EVT-HTW-1-REQ-001"))]}, ensure_ascii=False), encoding="utf-8")
            output = proof / "HTW-1.md"
            command = [
                sys.executable, str(SCRIPT_DIR / "delivery_index.py"),
                "--issue-key", "HTW-1", "--issue-url", "http://example/issues/1",
                "--comments-json", str(comments_file), "--output-file", str(output),
                "--coverage", "FULL", "--synced-at", "2026-08-26T14:00:00+00:00",
                "--worktree-root", str(root), "--legacy-path", str(legacy_req),
                "--legacy-path", str(legacy_catalog),
            ]
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual([path.name for path in proof.iterdir()], ["HTW-1.md"])
            archive = root / ".local" / "dc-loop" / "archive" / "HTW-1"
            self.assertEqual((archive / "REQ-OLD" / "验收报告.md").read_text(encoding="utf-8"), "legacy")
            self.assertEqual((archive / "需求清单.md").read_text(encoding="utf-8"), "legacy catalog")

    def test_delivery_index_check_rejects_remaining_legacy_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            proof = root / "docs" / "交付证明"
            proof.mkdir(parents=True)
            legacy = proof / "REQ-OLD"
            legacy.mkdir()
            comments_file = root / "comments.json"
            document = requirement_event("EVT-HTW-1-REQ-001")
            comments_file.write_text(json.dumps({"comments": [comment("c1", "2026-08-26T10:00:00+09:00", document)]}, ensure_ascii=False), encoding="utf-8")
            output = proof / "HTW-1.md"
            base = [sys.executable, str(SCRIPT_DIR / "delivery_index.py"), "--issue-key", "HTW-1", "--issue-url", "http://example/issues/1", "--comments-json", str(comments_file), "--output-file", str(output), "--coverage", "FULL", "--synced-at", "2026-08-26T14:00:00+00:00"]
            self.assertEqual(subprocess.run(base, check=False).returncode, 0)
            checked = subprocess.run(base + ["--check", "--worktree-root", str(root), "--legacy-path", str(legacy)], check=False, capture_output=True, text=True)
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("旧交付路径仍存在", checked.stderr)

    def test_delivery_index_rejects_symlink_and_nested_legacy_paths_before_moving(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            proof = root / "docs" / "交付证明"
            legacy = proof / "REQ-OLD"
            nested = legacy / "artifacts"
            nested.mkdir(parents=True)
            link = proof / "REQ-LINK"
            link.symlink_to(legacy, target_is_directory=True)
            comments_file = root / "comments.json"
            comments_file.write_text(json.dumps({"comments": [comment("c1", "2026-08-26T10:00:00+09:00", requirement_event("EVT-HTW-1-REQ-001"))]}, ensure_ascii=False), encoding="utf-8")
            base = [
                sys.executable, str(SCRIPT_DIR / "delivery_index.py"),
                "--issue-key", "HTW-1", "--issue-url", "http://example/issues/1",
                "--comments-json", str(comments_file), "--output-file", str(proof / "HTW-1.md"),
                "--coverage", "FULL", "--worktree-root", str(root),
            ]
            symlink_result = subprocess.run(base + ["--legacy-path", str(link)], check=False, capture_output=True, text=True)
            self.assertNotEqual(symlink_result.returncode, 0)
            self.assertIn("符号链接", symlink_result.stderr)
            nested_result = subprocess.run(base + ["--legacy-path", str(nested), "--legacy-path", str(legacy)], check=False, capture_output=True, text=True)
            self.assertNotEqual(nested_result.returncode, 0)
            self.assertIn("相互嵌套", nested_result.stderr)
            self.assertTrue(legacy.is_dir())
            self.assertTrue(link.is_symlink())

    def test_delivery_index_rejects_archiving_current_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            proof = root / "docs" / "交付证明"
            proof.mkdir(parents=True)
            output = proof / "HTW-1.md"
            output.write_text("existing", encoding="utf-8")
            comments_file = root / "comments.json"
            comments_file.write_text(json.dumps({"comments": [comment("c1", "2026-08-26T10:00:00+09:00", requirement_event("EVT-HTW-1-REQ-001"))]}, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable, str(SCRIPT_DIR / "delivery_index.py"),
                    "--issue-key", "HTW-1", "--issue-url", "http://example/issues/1",
                    "--comments-json", str(comments_file), "--output-file", str(output),
                    "--coverage", "FULL", "--worktree-root", str(root), "--legacy-path", str(output),
                ],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("当前索引", result.stderr)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing")

    def test_delivery_index_rejects_incomplete_sync(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            comments_file = root / "comments.json"
            comments_file.write_text("[]", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "delivery_index.py"), "--issue-key", "HTW-1", "--issue-url", "http://example/issues/1", "--comments-json", str(comments_file), "--output-file", str(root / "index.md")],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("coverage: FULL", result.stderr)

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
        planning_reference = (SCRIPT_DIR.parent.parent / "dc-proof-resources" / "references" / "implementation-planning.md").read_text(encoding="utf-8")
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
        document = requirement_event("EVT-001")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_file = root / "event.yaml"
            comments_file = root / "comments.json"
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            comments_file.write_text(json.dumps({"comments": [comment("c1", "2026-08-26T10:00:00+09:00", document)]}, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--comments-json", str(comments_file), "--output-dir", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["duplicate"])

    def test_initial_req_renders_structured_human_sections(self) -> None:
        document = requirement_event("EVT-REQ-001")
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
            content = (output_dir / "EVT-REQ-001.md").read_text(encoding="utf-8")
            for heading in ("## 需求目标", "## 需求陈述", "## 业务结果", "### 范围内", "### 范围外", "## 约束与依赖", "## 未决事项", "## 发布说明"):
                self.assertIn(heading, content)
            self.assertIn("DEEP_CREW_EVENT_START", content)

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
            self.assertIn("subject_id: SPEC-001", content)
            self.assertIn("| SCN | 标题 | 业务结果 | Given | When | Then | 交付面 |", content)

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
            self.assertIn("| SCN | 标题 | 业务结果 | Given | When | Then | 交付面 |", content)

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
            self.assertIn("当前有效规格", content)
            self.assertIn("SCN-001", content)
            self.assertIn("SCN-002", content)
            self.assertIn("CHK-001", content)
            self.assertIn("AST-002", content)
            self.assertIn("DEEP_CREW_EVENT_START", content)
            self.assertIn("2 个独立场景", content)
            self.assertIn("#### `SCN-001`", content)
            self.assertIn("#### `SCN-002`", content)

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
        document = implementation_event("EVT-IMP-001")
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
            content = (output_dir / "EVT-IMP-001.md").read_text(encoding="utf-8")
            self.assertIn("IMP-001 实现完成", content)
            self.assertIn("交付摘要", content)
            self.assertIn("实际变更面", content)
            self.assertIn("server/auth/login_handler.go", content)
            self.assertIn("POST /api/login", content)
            self.assertIn("go test ./server/auth/...", content)
            self.assertIn("实现工作树：/tmp/example-worktree", content)
            self.assertIn("Git 根目录：/tmp/example-worktree", content)
            self.assertIn("完成前复核", content)
            self.assertIn("自测之后", content)

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
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--verify-git", "--output-dir", str(output_dir)], check=False, capture_output=True, text=True)
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
            output_dir = root / "out"
            event_file.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT_DIR / "prepare_event.py"), "--event-file", str(event_file), "--issue", "HTW-1", "--verify-git", "--output-dir", str(output_dir)], check=False, capture_output=True, text=True)
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
