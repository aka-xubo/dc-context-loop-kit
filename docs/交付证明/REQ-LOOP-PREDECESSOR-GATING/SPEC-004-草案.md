# SPEC-004 验收规格增量草案

本文件是基于已确认 `SPEC-003` 的增量规格。负责人已确认，现用于生成线上 `SPEC-004` 事件。

<!-- DEEP_CREW_EVENT_START -->
```yaml
document_type: deep_crew_delivery_event
event:
  event_id: EVT-20260902-HTW1735-SPEC-004
  created_at: "2026-09-02T14:08:38+08:00"
  author: acceptance-owner
  node: SPEC
  subject_id: SPEC-004
  reason: 在 SPEC-003 基础上增加每轮刷新和单节点边界
  specification:
    requirement_ref: REQ-LOOP-PREDECESSOR-GATING
    base_spec_ref: SPEC-003
    changes:
      added:
        scenarios: []
        checks: []
        assertions:
          - id: AST-LOOP-PREDECESSOR-GATING-004
            check_id: CHK-LOOP-PREDECESSOR-GATING-001
            outcome_refs:
              - SCN-LOOP-PREDECESSOR-GATING-001.THEN-LOOP-PREDECESSOR-GATING-004
            assertion_type: semantic
            description: 每一轮 Loop 最多调用一个节点技能并最多发布一个结构化事件，不在同一轮连续完成多个节点
          - id: AST-LOOP-PREDECESSOR-GATING-005
            check_id: CHK-LOOP-PREDECESSOR-GATING-001
            outcome_refs:
              - SCN-LOOP-PREDECESSOR-GATING-001.THEN-LOOP-PREDECESSOR-GATING-005
            assertion_type: semantic
            description: 每轮开始前 Loop 都重新完整读取当前 Issue 评论和附件，不能把上一轮 Issue context 或评论缓存当作本轮事实来源
          - id: AST-LOOP-PREDECESSOR-GATING-006
            check_id: CHK-LOOP-PREDECESSOR-GATING-001
            outcome_refs:
              - SCN-LOOP-PREDECESSOR-GATING-001.THEN-LOOP-PREDECESSOR-GATING-006
            assertion_type: semantic
            description: 结构化事件发布动作返回成功、失败或结果未知后，Loop 都结束当前轮次，不在同一轮自动路由下游节点
      modified:
        scenarios:
          - id: SCN-LOOP-PREDECESSOR-GATING-001
            title: 节点路由前检查线上前置材料并限定单轮边界
            business_result: Loop 只在当前 Issue 的前置交付事实齐全时进入一个目标节点，并为下一轮重新获取事实
            given:
              - dc-issue-intake 已读取当前 Issue 的完整评论和附件
              - 用户请求继续处理当前 Issue
            when: dc-context-loop 判断下一责任节点并准备调用节点技能
            then:
              - id: THEN-LOOP-PREDECESSOR-GATING-001
                statement: REQ 节点不要求前置交付事件，其他节点按规则检查线上可解析的前置事件
              - id: THEN-LOOP-PREDECESSOR-GATING-002
                statement: 缺少前置事件或引用不匹配时，Loop 停止在当前节点并报告缺失材料
              - id: THEN-LOOP-PREDECESSOR-GATING-003
                statement: 前置材料齐全且引用匹配时，Loop 才调用目标节点技能
              - id: THEN-LOOP-PREDECESSOR-GATING-004
                statement: 每一轮最多调用一个节点技能，最多发布一个结构化事件
              - id: THEN-LOOP-PREDECESSOR-GATING-005
                statement: 每一轮开始都重新完整读取当前 Issue；不得用上一轮缓存替代本轮 intake
              - id: THEN-LOOP-PREDECESSOR-GATING-006
                statement: 当前节点事件发布成功、失败或结果未知后，本轮结束，不在同一轮自动进入下游节点
            delivery_surfaces:
              - skill
              - issue-event
        checks: []
        assertions: []
      removed:
        scenarios: []
        checks: []
        assertions: []
    open_questions: []
```
<!-- DEEP_CREW_EVENT_END -->

## 本次增量

- 基线：`SPEC-003`
- 新增断言：`AST-LOOP-PREDECESSOR-GATING-004`、`AST-LOOP-PREDECESSOR-GATING-005`、`AST-LOOP-PREDECESSOR-GATING-006`
- 修改场景：`SCN-LOOP-PREDECESSOR-GATING-001`
- 未修改需求：`REQ-LOOP-PREDECESSOR-GATING`
- 当前状态：已确认，待发布线上事件

已确认内容将使用 `prepare_event.py` 校验并发布线上 `SPEC-004`。
