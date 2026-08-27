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

REQ 和 SPEC 是完整定义事件：每条事件都携带发布时的完整内容。模型阅读完整评论时间线后，结合普通讨论和用户最新指令判断哪份定义仍然适用。事件只包含该节点定义的字段。

快照内的 `REQ-*`、`SCN-*`、`CHK-*`、`AST-*` 只用于当前内容的引用。下一条 REQ/SPEC 可以继续使用原 ID，也可以重建对象集合并使用新 ID；模型根据完整历史判断当前适用的定义。

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

## SPEC 完整快照

```yaml
event:
  event_id: EVT-20260826-002
  created_at: "2026-08-26T16:00:00+09:00"
  author: acceptance-owner
  node: SPEC
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

人类评论展示当前完整场景、检查责任、原子断言、引用关系和未决事项。下一份 SPEC 可以整体重写场景集合，不生成差异表。

## IMPLEMENTATION 与 ACCEPTANCE

实现和验收保持独立事实模型：实现计划、编码、调试和本地验收过程不发布过程事件；完成后分别发布完整 `IMPLEMENTATION` 或 `ACCEPTANCE` 事实。具体字段和示例见 Context Loop 主技能及对应 Schema。

讨论不是事件。高影响歧义由 `dc-grilling` 在当前对话中处理，收束后直接生成上述 REQ 或 SPEC 快照。
