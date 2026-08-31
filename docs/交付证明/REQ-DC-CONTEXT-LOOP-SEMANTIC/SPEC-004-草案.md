# SPEC-004 草案：SPEC 评论编号与实现/验收一致

## 路由判断

- Issue：HTW-1671（`7ae49575-945b-474c-baf7-3908c95ac006`）
- 当前需求：`REQ-DC-CONTEXT-LOOP-SEMANTIC`
- 需求变化判断：`SPEC_CHANGE`
- 基础规格：`SPEC-003`
- 原因：业务目标和范围不变，但 SPEC 事件评论的可追踪编号与 IMPLEMENTATION、ACCEPTANCE 评论不一致，属于验收定义和事件可观察格式的变化。

## 待确认的增量 SPEC

```yaml
requirement_ref: REQ-DC-CONTEXT-LOOP-SEMANTIC
base_spec_ref: SPEC-003
changes:
  added:
    scenarios:
      - id: SCN-010
        title: SPEC 评论使用稳定编号
        business_result: 评审者能够像引用 IMP-* 和 ACC-* 一样，使用稳定的 SPEC-* 编号识别和引用每一条 SPEC 评论。
        given:
          - 当前 Issue 已存在已确认的 SPEC-003
          - 模型决定发布新的完整或增量 SPEC
        when: 事件准备工具校验并渲染 SPEC 事件
        then:
          - id: THEN-020
            statement: SPEC 事件具有唯一且稳定的 SPEC-* 标识，并与其 event_id 和基础 SPEC 引用保持可追溯关系
          - id: THEN-021
            statement: 人类可读评论标题展示该 SPEC-* 标识，格式与 [DP:IMPLEMENTATION] IMP-* 和 [DP:ACCEPTANCE] ACC-* 一致
          - id: THEN-022
            statement: YAML 机器块保留同一 SPEC-* 标识，后续实现和验收能够引用该规格编号
        delivery_surfaces: [skill]
    checks:
      - id: CHK-010
        scenario_ids: [SCN-010]
        dependency_ids: []
        verification_type: unit
        responsibility: 直接调用事件准备工具，验证完整 SPEC 和增量 SPEC 都要求、保留并渲染稳定的 SPEC-* 编号，且缺失或前缀错误时拒绝事件。
        required: true
        blocking: true
        evidence_requirements:
          required_artifact_types: [command_output]
        external_verification: null
    assertions:
      - id: AST-019
        check_id: CHK-010
        outcome_refs: [SCN-010.THEN-020]
        assertion_type: semantic
        description: 完整和增量 SPEC 事件都具有唯一且稳定的 SPEC-* 标识，并能与 event_id、base_spec_ref 建立可追溯关系。
      - id: AST-020
        check_id: CHK-010
        outcome_refs: [SCN-010.THEN-021]
        assertion_type: semantic
        description: SPEC 人类可读评论标题展示 SPEC-* 标识，与 IMPLEMENTATION 和 ACCEPTANCE 标题的编号格式一致。
      - id: AST-021
        check_id: CHK-010
        outcome_refs: [SCN-010.THEN-022]
        assertion_type: semantic
        description: SPEC-* 标识同时出现在 YAML 机器块中，可被后续实现和验收事件引用；缺失或前缀错误的标识被事件工具拒绝。
  modified:
    scenarios: []
    checks: []
    assertions: []
  removed:
    scenarios: []
    checks: []
    assertions: []
open_questions: []
```

## 实现约束（不属于本次业务确认内容）

确认后，IMPLEMENTATION 节点应选择一种稳定实现，使以下行为成立：SPEC 事件拥有 `SPEC-*` 编号；人类评论标题显示该编号；机器块保存同一编号；完整快照和增量事件均适用；历史 `SPEC-001` 至 `SPEC-003` 评论保持不变。

## 人工确认

请确认以上 `SPEC-004` 增量草案。确认后才能发布 SPEC 事件并进入实现节点；确认前不修改生产实现、不生成 `IMP-*`，也不发布新的 SPEC 评论。
