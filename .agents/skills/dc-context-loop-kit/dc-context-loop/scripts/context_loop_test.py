#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent


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
class ContextLoopTest(unittest.TestCase):
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
    unittest.main()
