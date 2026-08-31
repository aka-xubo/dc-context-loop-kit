# 事件契约

## 评论布局

每条结构化评论包含人类摘要和机器块：

```text
<!-- DEEP_CREW_EVENT_START -->
```yaml
...
```
<!-- DEEP_CREW_EVENT_END -->
```

普通 Issue 评论只作为上下文阅读，不改变机器快照。

## 节点与时间规则

事件只支持四种 `node`：`REQ`、`SPEC`、`IMPLEMENTATION`、`ACCEPTANCE`。

REQ 是完整定义事件。SPEC 首次建立或需要重建基线时使用完整快照，后续变化默认使用相对基础 SPEC 的增量事件。模型阅读完整评论时间线后，结合普通讨论和用户最新指令应用增量并判断哪份定义仍然适用。事件只包含该节点定义的字段。

事件的 `subject_id` 是交付内容的稳定编号：REQ 不使用 subject_id，SPEC 使用 `SPEC-*`，实现使用 `IMP-*`，验收使用 `ACC-*`。快照内的 `REQ-*`、`SCN-*`、`CHK-*`、`AST-*` 只用于当前内容的引用。下一条 REQ/SPEC 可以继续使用原 ID，也可以重建对象集合并使用新 ID；模型根据完整历史判断当前适用的定义。

同一 `event_id` 重复发布时，准备脚本返回 `duplicate`；不同的 `IMP-*` 和 `ACC-*` 是独立事实，全部保留。

## REQ 完整快照

```yaml
event:
  event_id: EVT-20260826-001
  created_at: "2026-08-26T15:30:00+09:00"
  author: product-owner
  node: REQ
  reason: 根据当前讨论整理完整需求
  requirement:
    id: REQ-001
    title: 登录失败反馈
    statement: 用户能够理解登录失败原因
    business_outcomes:
      - 用户能够判断下一步操作
    scope:
      included: [Web 登录, 移动端登录]
      excluded: [账号注册]
    constraints:
      - 继续使用现有认证服务
    open_questions: []
```

人类评论展示需求目标、需求陈述、业务结果、范围、约束、未决事项和发布说明。需求讨论在当前对话中完成；需要长期追溯的决策直接进入这份完整快照。

## SPEC 完整快照或增量

首次建立规格或无法可靠以增量表达时，使用完整快照：

```yaml
event:
  event_id: EVT-20260826-002
  created_at: "2026-08-26T16:00:00+09:00"
  author: acceptance-owner
  node: SPEC
  subject_id: SPEC-001
  reason: 根据当前需求整理完整验收规格
  specification:
    requirement_ref: REQ-001
    scenarios:
      - id: SCN-001
        title: 错误密码登录
        business_result: 用户理解登录失败原因
        given: [用户已打开登录入口]
        when: 用户提交错误密码
        then:
          - id: THEN-001
            statement: 系统拒绝登录并显示可理解的失败原因
        delivery_surfaces: [web, mobile]
    checks:
      - id: CHK-001
        scenario_ids: [SCN-001]
        verification_type: api
        responsibility: 验证错误密码被拒绝
        required: true
        blocking: true
    assertions:
      - id: AST-001
        check_id: CHK-001
        outcome_refs: [SCN-001.THEN-001]
        assertion_type: semantic
        description: 登录请求返回拒绝结果和失败原因
    open_questions: []
```

后续规格变化默认使用增量，仅记录相对基础 SPEC 的新增、修改、删除：

```yaml
specification:
  requirement_ref: REQ-001
  base_spec_ref: SPEC-002
  changes:
    added: {scenarios: [], checks: [], assertions: []}
    modified: {scenarios: [], checks: [], assertions: []}
    removed: {scenarios: [SCN-001], checks: [], assertions: []}
  open_questions: []
```

新增和修改对象使用完整结构并保留稳定 ID；删除只列出对象 ID；同一 ID 不得同时出现在多个操作中，且至少有一项变化。人类评论标题必须展示 `SPEC-*` 编号，按事件形态展示当前完整场景、检查责任、原子断言，或增量的基础 SPEC、新增、修改、删除和未决事项。机器块保存同一 `subject_id`，供后续实现和验收引用。模型负责将增量应用到基础 SPEC；准备脚本只校验和渲染，不读取历史或自动合并。

## IMPLEMENTATION 与 ACCEPTANCE

实现和验收保持独立事实模型：实现计划、编码、调试和本地验收过程不发布过程事件；完成后分别发布完整 `IMPLEMENTATION` 或 `ACCEPTANCE` 事实。ACCEPTANCE 必须显式保存 `mode: targeted | full`、`scope_refs` 和 `req_completion_impact`：指定一个 `IMP-*` 的单次验收使用 `targeted`，未指定 IMP 的当前有效 SPEC 全量验收使用 `full`；只有 `full` 模式的 `SATISFIED` 才能影响 REQ 完成状态。具体字段和示例见 Context Loop 主技能及对应 Schema。

讨论不是事件。高影响歧义由 `dc-grilling` 在当前对话中处理，收束后直接生成上述 REQ 或 SPEC 快照。
