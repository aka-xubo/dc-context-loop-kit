# SPEC-005 草案：SPEC 人类可读审查与验收范围标识

## 路由判断

- Issue：HTW-1671（`7ae49575-945b-474c-baf7-3908c95ac006`）
- 当前需求：`REQ-DC-CONTEXT-LOOP-SEMANTIC`
- 需求变化判断：`SPEC_CHANGE`
- 基础规格：`SPEC-004`
- 原因：业务目标和范围不变，但 SPEC 草案当前主要以 YAML 呈现，SCN、CHK、AST 不便于人类逐项审查；同时验收结论没有显式区分指定 IMP 的单次验收和当前有效 SPEC 的全量验收；两者都是验收定义的可观察表达方式变化。

## 本次变更

本次新增两个验收场景，并要求本地 SPEC 草案和验收结论同时提供：

1. SCN 表格，展示场景 ID、业务结果、Given、When、Then 和交付面；
2. CHK 表格，展示检查 ID、场景、验证类型、验证责任、必需和阻断属性；
3. AST 表格，展示断言 ID、CHK、结果引用、断言类型和断言描述；
4. 增量内容表格，以及将基础 SPEC 应用增量后的当前有效规格表格；
5. 与上述表格由同一结构化数据生成的 YAML 机器块。
6. 验收模式 `targeted`（指定单次 `IMP-*`）和 `full`（当前有效 SPEC 全量），以及与模式一致的验收范围和结论影响。

表格是人工确认入口，YAML 是机器校验和后续引用入口；二者内容不允许出现语义不一致。对于增量 SPEC，表格必须同时标明本次新增、修改、删除和继承对象，不能只展示新增对象而隐藏当前有效集合。

验收指令中明确指定 `IMP-*` 时使用 `targeted` 模式（单次验收，也可称指定 IMP 的增量验收），只验收该 IMP 声明范围内的完整 CHK/AST；未指定 IMP 时使用 `full` 模式，验收当前有效 SPEC 的全部必需、阻断 CHK/AST。两种模式均可产生 `SATISFIED`，但只有 `full` 模式的 `SATISFIED` 才能影响整个 REQ 的完成状态。

### 验收结论的可读区分

| 模式 | 触发指令 | 验收目标 | 结论影响 |
|---|---|---|---|
| `targeted` | `执行验收 IMP-004` | `IMP-004` 的 `spec_refs` 展开的完整 CHK/AST | 仅证明该 IMP 切片，不改变整个 REQ 的完成状态 |
| `full` | `执行验收`、`开始验收` | 当前有效 SPEC 的全部必需、阻断 CHK/AST | `SATISFIED` 时可影响整个 REQ 的完成状态 |

验收评论标题必须带模式和目标，例如：

```text
[DP:ACCEPTANCE] ACC-005 · 单次验收 · IMP-004
[DP:ACCEPTANCE] ACC-006 · 全量验收 · 当前有效 SPEC
```

机器块中的 `acceptance` 必须保存 `mode`、`scope_refs` 和对应的 `implementation_refs`；`scope_refs` 是本次实际裁决范围，不得用评论标题或 `status` 推断。

## 本次新增场景

### SCN-011 SPEC 草案提供人类可读表格

| Given | When | Then | 交付面 |
|---|---|---|---|
| 当前 Issue 存在已确认的基础 SPEC；模型生成完整或增量 SPEC 草案；草案包含 SCN、CHK、AST 结构化数据 | 用户打开本地 SPEC 草案进行确认 | 草案提供 SCN、CHK、AST 的人类可读表格；增量草案同时展示合并后的当前有效规格；表格与 YAML 机器块表达同一组 ID、引用和描述 | skill |

业务结果：负责人能够在不解析 YAML 的情况下逐项审查当前验收场景、检查责任和原子断言，并确认本次 SPEC 变化。

### SCN-012 验收结论标识单次或全量范围

| Given | When | Then | 交付面 |
|---|---|---|---|
| Issue 有已确认 REQ/SPEC 和一个或多个 READY 的 IMP；用户发出验收指令 | 用户明确指定 `IMP-*`，或明确要求全量验收 | 指定 IMP 时生成 `mode: targeted`，范围为该 IMP 的 `spec_refs` 展开的完整 CHK/AST；未指定 IMP 时生成 `mode: full`，范围为当前有效 SPEC 的全部必需、阻断 CHK/AST；结论明确说明范围，只有全量通过才影响 REQ 完成状态 | skill |

业务结果：负责人能够从验收结论直接判断本次是单个实现交付通过，还是当前有效规格整体通过。

## 当前有效规格的人类可读视图

以下表格是将 `SPEC-003` 完整基线与 `SPEC-004` 增量合并后的当前有效集合，并在此基础上标出本次新增的 `SPEC-005` 对象。

### SCN 表

| 状态 | SCN | 标题 | 业务结果 | Given / When / Then 摘要 | 交付面 |
|---|---|---|---|---|---|
| 继承 | SCN-001 | 基于完整历史形成上下文理解 | 从 Issue、本地材料和用户消息形成可审阅上下文 | Issue 有讨论、事件和指令；继续处理；区分事实、讨论、指令、定义、冲突和未决并给出依据 | skill |
| 继承 | SCN-002 | 选择当前交付节点和下一步 | 区分变化类型并选择最小下一步 | 有历史交付事实；用户继续或反馈；判断 REQ/SPEC/实现变化并选择节点和负责人 | skill |
| 继承 | SCN-003 | 高影响歧义进入澄清而非猜测 | 高影响歧义被澄清，低风险问题不阻塞 | 存在会改变结果的歧义；准备动作；调用 grilling 但不让其执行验收 | skill |
| 继承 | SCN-004 | 结构化事件继续可校验和可渲染 | 事件可读、可解析且不自动路由 | 需要发布交付事件；调用准备工具；生成摘要和 YAML 且不按时间线自动选节点 | skill |
| 继承 | SCN-005 | 审核页不展示场景优先级 | 场景区域只显示有业务含义的信息 | 当前 SPEC 有场景；查看审核工作台；只显示场景 ID 和状态 | web |
| 继承 | SCN-006 | READY 后无明确验收指令时硬停止 | 没有授权不自动启动验收 | 有 READY 实现和已确认 REQ/SPEC；用户只说继续或可以；报告等待且不生成验收材料 | skill |
| 继承 | SCN-007 | 明确验收指令才进入 ACCEPTANCE | 明确授权后才形成独立验收结论 | 有 READY 实现和已确认 REQ/SPEC；用户明确要求验收；调用 verification、closure 并发布唯一结论 | skill |
| 继承 | SCN-008 | 人工确认前提供 SPEC 草案链接 | 确认者能打开草案再决定 | 已有待确认草案；请求确认；给出可点击链接并等待确认 | skill |
| 继承 | SCN-009 | 根据历史语义建立新的 SPEC | 按历史判断 REQ、SPEC 和实现变化 | 有完整历史和已确认 SPEC；用户提出反馈；判断变化类型并正确使用基础 SPEC 增量 | skill |
| 继承 | SCN-010 | SPEC 评论使用稳定编号 | SPEC 可用稳定编号识别和引用 | 有已确认 SPEC-003；发布新 SPEC；编号、标题、机器块和引用一致 | skill |
| 新增 | SCN-011 | SPEC 草案提供人类可读表格 | 负责人无需解析 YAML 即可逐项审查 SCN、CHK、AST | 有基础 SPEC 和结构化草案；打开本地草案；展示三类表格、增量和合并后的有效集合，且与 YAML 一致 | skill |
| 新增 | SCN-012 | 验收结论标识单次或全量范围 | 负责人能够区分指定 IMP 的单次验收和当前有效 SPEC 的全量验收 | 有 READY IMP 和已确认 REQ/SPEC；用户指定 IMP 或要求全量；结论包含模式、范围和对 REQ 状态的影响 | skill |

### CHK 表

| 状态 | CHK | 场景 | 类型 | 验证责任 | 必需 | 阻断 |
|---|---|---|---|---|---|---|
| 继承 | CHK-001 | SCN-001 | e2e | 从完整 Issue 历史和本地材料验证上下文理解 | 是 | 是 |
| 继承 | CHK-002 | SCN-002 | e2e | 使用历史定义和新增反馈验证节点与最小下一步 | 是 | 是 |
| 继承 | CHK-003 | SCN-003 | e2e | 使用高影响歧义和失败材料验证 grilling 边界 | 是 | 是 |
| 继承 | CHK-004 | SCN-004 | unit | 调用事件准备工具验证校验、渲染与路由解耦 | 是 | 是 |
| 继承 | CHK-005 | SCN-005 | ui | 打开审核工作台检查场景区域展示内容 | 是 | 是 |
| 继承 | CHK-006 | SCN-006 | e2e | 使用 READY 实现和泛化指令验证硬停止 | 是 | 是 |
| 继承 | CHK-007 | SCN-007 | e2e | 使用 READY 实现和明确指令验证进入 ACCEPTANCE | 是 | 是 |
| 继承 | CHK-008 | SCN-008 | e2e | 请求确认并检查可点击草案链接及发布门禁 | 是 | 是 |
| 继承 | CHK-009 | SCN-009 | e2e | 使用完整历史验证新 SPEC 的建立条件和增量引用 | 是 | 是 |
| 继承 | CHK-010 | SCN-010 | unit | 验证完整、增量 SPEC 的稳定编号、标题、机器块和拒绝行为 | 是 | 是 |
| 新增 | CHK-011 | SCN-011 | unit | 直接生成完整和增量 SPEC 草案，检查 SCN、CHK、AST 表格、增量/合并视图与 YAML 的一致性 | 是 | 是 |
| 新增 | CHK-012 | SCN-012 | e2e | 分别使用指定 IMP 和未指定 IMP 的明确验收指令，检查验收模式、完整范围和 REQ 状态影响 | 是 | 是 |

### AST 表

| 状态 | AST | CHK | 结果引用 | 类型 | 断言描述 |
|---|---|---|---|---|---|
| 继承 | AST-001 | CHK-001 | SCN-001.THEN-001 | semantic | 输出区分事实、讨论、指令、当前定义、冲突和未决问题 |
| 继承 | AST-002 | CHK-001 | SCN-001.THEN-002 | semantic | 关键判断有可定位的 Issue、本地材料或用户指令依据 |
| 继承 | AST-003 | CHK-002 | SCN-002.THEN-003 | semantic | 先判断业务承诺变化并区分 REQUIREMENT_CHANGE 与 NEW_REQUIREMENT |
| 继承 | AST-004 | CHK-002 | SCN-002.THEN-004 | semantic | 验收定义变化为 SPEC_CHANGE，纯实现变化为 IMPLEMENTATION_ONLY，无变化为 NO_REQUIREMENT_CHANGE |
| 继承 | AST-005 | CHK-002 | SCN-002.THEN-005 | semantic | 选择唯一当前责任节点并给出最小下一步 |
| 继承 | AST-006 | CHK-003 | SCN-003.THEN-006 | semantic | 高影响歧义调用 grilling 并只提出必要问题 |
| 继承 | AST-007 | CHK-003 | SCN-003.THEN-007 | semantic | grilling 不执行验收、证据审查或最终裁决 |
| 继承 | AST-008 | CHK-004 | SCN-004.THEN-008 | semantic | 合法事件生成可读摘要和 YAML 机器块 |
| 继承 | AST-009 | CHK-004 | SCN-004.THEN-009 | semantic | 准备工具不按时间线或 next_actions 自动路由 |
| 继承 | AST-010 | CHK-005 | SCN-005.THEN-010 | semantic | 场景区域不显示优先级或“未设”占位 |
| 继承 | AST-011 | CHK-006 | SCN-006.THEN-011 | semantic | 无明确指令时报告 READY 并等待验收授权 |
| 继承 | AST-012 | CHK-006 | SCN-006.THEN-012 | semantic | 无明确指令时不调用验收技能或生成 RUN、ART、ACC |
| 继承 | AST-013 | CHK-007 | SCN-007.THEN-013 | semantic | 明确指令后进入 ACCEPTANCE 并发布唯一验收事件 |
| 继承 | AST-014 | CHK-008 | SCN-008.THEN-014 | semantic | 确认前提供可点击完整 SPEC 草案链接且不发布事件 |
| 继承 | AST-015 | CHK-009 | SCN-009.THEN-016 | semantic | 业务承诺变化时不建立 SPEC，归入 REQ 变化 |
| 继承 | AST-016 | CHK-009 | SCN-009.THEN-017 | semantic | 验收语义、责任、证据或门禁变化时归入 SPEC_CHANGE |
| 继承 | AST-017 | CHK-009 | SCN-009.THEN-018 | semantic | 只改代码、测试或环境时归入 IMPLEMENTATION_ONLY |
| 继承 | AST-018 | CHK-009 | SCN-009.THEN-019 | semantic | 增量应用基础 SPEC，稳定继承、修改、新增和删除对象 |
| 继承 | AST-019 | CHK-010 | SCN-010.THEN-020 | semantic | 完整和增量 SPEC 具有稳定 SPEC-* 编号并可追溯 |
| 继承 | AST-020 | CHK-010 | SCN-010.THEN-021 | semantic | SPEC 人类评论标题展示 SPEC-* 编号 |
| 继承 | AST-021 | CHK-010 | SCN-010.THEN-022 | semantic | YAML 保留 SPEC-* 编号且错误前缀被拒绝 |
| 新增 | AST-022 | CHK-011 | SCN-011.THEN-023 | semantic | 本地草案包含 SCN 表格，且每个当前有效场景均可逐项审查 |
| 新增 | AST-023 | CHK-011 | SCN-011.THEN-024 | semantic | 本地草案包含 CHK 和 AST 表格，且引用、类型、责任和描述可逐项审查 |
| 新增 | AST-024 | CHK-011 | SCN-011.THEN-025 | semantic | 增量表格、合并后的有效规格表格与同一 YAML 机器块的对象 ID、引用和描述一致 |
| 新增 | AST-025 | CHK-012 | SCN-012.THEN-026 | semantic | 明确指定 `IMP-*` 时，验收结论标记 `mode: targeted`，并覆盖该 IMP 的 `spec_refs` 展开的完整 CHK/AST |
| 新增 | AST-026 | CHK-012 | SCN-012.THEN-027 | semantic | 未指定 IMP 而要求验收时，验收结论标记 `mode: full`，并覆盖当前有效 SPEC 的全部必需、阻断 CHK/AST |
| 新增 | AST-027 | CHK-012 | SCN-012.THEN-028 | semantic | 验收结论展示模式、目标、范围和 REQ 状态影响；只有 `full` 模式的 `SATISFIED` 影响整个 REQ |

## 本次增量摘要

| 操作 | SCN | CHK | AST |
|---|---|---|---|
| 新增 | SCN-011 | CHK-011 | AST-022、AST-023、AST-024 |
| 新增 | SCN-012 | CHK-012 | AST-025、AST-026、AST-027 |
| 修改 | 无 | 无 | 无 |
| 删除 | 无 | 无 | 无 |

合并后当前有效规格：12 个 SCN、12 个 CHK、27 个 AST。

## 待确认的增量 SPEC

```yaml
requirement_ref: REQ-DC-CONTEXT-LOOP-SEMANTIC
base_spec_ref: SPEC-004
changes:
  added:
    scenarios:
      - id: SCN-011
        title: SPEC 草案提供人类可读表格
        business_result: 负责人能够在不解析 YAML 的情况下逐项审查当前验收场景、检查责任和原子断言，并确认本次 SPEC 变化。
        given:
          - 当前 Issue 存在已确认的基础 SPEC
          - 模型生成完整或增量 SPEC 草案
          - 草案包含 SCN、CHK、AST 结构化数据
        when: 用户打开本地 SPEC 草案进行确认
        then:
          - id: THEN-023
            statement: 草案提供 SCN 的人类可读表格，展示 ID、业务结果、Given、When、Then 和交付面
          - id: THEN-024
            statement: 草案提供 CHK 和 AST 的人类可读表格，展示稳定 ID、引用、类型、责任和描述
          - id: THEN-025
            statement: 增量表格、合并后的当前有效规格表格与 YAML 机器块表达同一组对象、引用和描述
        delivery_surfaces: [skill]
      - id: SCN-012
        title: 验收结论标识单次或全量范围
        business_result: 负责人能够从验收结论直接判断本次是单个实现交付通过，还是当前有效规格整体通过。
        given:
          - Issue 有已确认 REQ/SPEC 和一个或多个 READY 的 IMP
          - 用户发出明确验收指令
        when: 用户明确指定 IMP-*，或明确要求全量验收
        then:
          - id: THEN-026
            statement: "指定 IMP 时生成 mode: targeted，范围为该 IMP 的 spec_refs 展开的完整 CHK/AST"
          - id: THEN-027
            statement: "未指定 IMP 时生成 mode: full，范围为当前有效 SPEC 的全部必需、阻断 CHK/AST"
          - id: THEN-028
            statement: "结论明确说明模式、目标、范围和对 REQ 状态的影响，只有 full 模式的 SATISFIED 影响整个 REQ"
        delivery_surfaces: [skill]
    checks:
      - id: CHK-011
        scenario_ids: [SCN-011]
        dependency_ids: []
        verification_type: unit
        responsibility: 直接生成完整和增量 SPEC 草案，检查 SCN、CHK、AST 表格、增量/合并视图与 YAML 的一致性。
        required: true
        blocking: true
        evidence_requirements:
          required_artifact_types: [command_output]
        external_verification: null
      - id: CHK-012
        scenario_ids: [SCN-012]
        dependency_ids: []
        verification_type: e2e
        responsibility: 分别使用指定 IMP 和未指定 IMP 的明确验收指令，检查验收模式、完整范围和 REQ 状态影响。
        required: true
        blocking: true
        evidence_requirements:
          required_artifact_types: [command_output]
        external_verification: null
    assertions:
      - id: AST-022
        check_id: CHK-011
        outcome_refs: [SCN-011.THEN-023]
        assertion_type: semantic
        description: 本地草案包含 SCN 表格，且每个当前有效场景均可逐项审查。
      - id: AST-023
        check_id: CHK-011
        outcome_refs: [SCN-011.THEN-024]
        assertion_type: semantic
        description: 本地草案包含 CHK 与 AST 表格，且引用、类型、责任和描述可逐项审查。
      - id: AST-024
        check_id: CHK-011
        outcome_refs: [SCN-011.THEN-025]
        assertion_type: semantic
        description: 增量表格、合并后的有效规格表格与同一 YAML 机器块的对象 ID、引用和描述一致。
      - id: AST-025
        check_id: CHK-012
        outcome_refs: [SCN-012.THEN-026]
        assertion_type: semantic
        description: "明确指定 IMP-* 时，验收结论标记 mode: targeted，并覆盖该 IMP 的 spec_refs 展开的完整 CHK/AST。"
      - id: AST-026
        check_id: CHK-012
        outcome_refs: [SCN-012.THEN-027]
        assertion_type: semantic
        description: "未指定 IMP 而要求验收时，验收结论标记 mode: full，并覆盖当前有效 SPEC 的全部必需、阻断 CHK/AST。"
      - id: AST-027
        check_id: CHK-012
        outcome_refs: [SCN-012.THEN-028]
        assertion_type: semantic
        description: "验收结论展示模式、目标、范围和 REQ 状态影响；只有 full 模式的 SATISFIED 影响整个 REQ。"
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

确认后，IMPLEMENTATION 节点应选择一种稳定实现，使完整 SPEC 和增量 SPEC 草案都能从同一结构化数据生成上述人类表格、增量/合并视图和 YAML 机器块，并使 ACCEPTANCE 事件保存 `mode`、`scope_refs`、目标 IMP/当前有效 SPEC 和对应的 REQ 状态影响；历史 `SPEC-001` 至 `SPEC-004` 评论保持不变。

## 人工确认

请确认以上 `SPEC-005` 增量草案。确认后才能发布 SPEC 事件并进入实现节点；确认前不修改生产实现、不生成 `IMP-*`，也不发布新的 SPEC 评论。
