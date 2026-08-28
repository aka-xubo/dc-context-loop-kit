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
) -> dict:
    result = {
        "status": "SATISFIED",
        "requirement_ref": "REQ-001",
        "spec_refs": ["SCN-001", "CHK-001", "AST-001"],
        "implementation_refs": ["IMP-001"],
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
    def test_routing_contract_distinguishes_spec_change(self) -> None:
        loop_skill = (SCRIPT_DIR.parent / "SKILL.md").read_text(encoding="utf-8")
        slicing_skill = (SCRIPT_DIR.parent.parent / "dc-requirement-slicing" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("SPEC_CHANGE", loop_skill)
        self.assertIn("业务承诺不变，但场景、CHK、AST、验证责任或验证方式变化", loop_skill)
        self.assertIn("SPEC_CHANGE", slicing_skill)
        self.assertIn("只有业务承诺变化才发布 REQ", slicing_skill)

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
