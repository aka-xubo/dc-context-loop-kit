# 事件契约

本文是四类 Deep Crew 交付事件的开发接入说明。它解释事件语义、示例和发布规则；机器校验以 [`contracts/event.schema.yaml`](../contracts/event.schema.yaml) 为准，Issue 评论正文和附件由 [`scripts/prepare_event.py`](../scripts/prepare_event.py) 生成。

## 权威关系

| 内容 | 权威来源 | 作用 |
|---|---|---|
| YAML 字段、类型、枚举和必填项 | `contracts/event.schema.yaml` | 机器结构约束；`additionalProperties: false` 的节点不得添加未声明字段 |
| 评论章节、标题和机器附件区块 | `scripts/prepare_event.py` | 从合法事件数据生成可读评论和 YAML 附件 |
| 事件语义、快照/增量规则、接入示例 | 本文 | 面向开发者和 Agent 的解释层 |
| Issue 历史、确认和交付事实 | Issue comments | 当前循环的事实来源；普通评论不会自动成为事件 |

如果本文、Schema 和脚本出现不一致，先以 Schema 和脚本的当前行为为准，并在同一 Issue 中修正文档或实现；不要通过手写评论绕过校验。

## 公共结构和评论布局

所有结构化事件都使用以下顶层包络。`node` 决定后续唯一的节点对象：

```yaml
document_type: deep_crew_delivery_event
event:
  event_id: EVT-20260902-001
  created_at: "2026-09-02T12:00:00+08:00"
  author: developer
  node: REQ
  reason: 根据当前讨论整理交付事实
  # REQ/SPEC/IMPLEMENTATION/ACCEPTANCE 只能选择一个节点对象，见下文
```

每条结构化 Issue 评论由脚本生成，正文包含人类摘要和以下附件引用；机器 YAML 不内嵌到评论正文：

```text
## 机器事件附件

- event_id：`EVT-...`
- YAML 附件：`<事件对象 ID>-事件.yaml`
- 解析方式：从 Issue comment 附件下载并解析该 YAML；评论正文不内嵌机器 YAML。
```

附件命名规则如下：

| 节点 | `subject_id` | YAML 附件 |
|---|---|---|
| `REQ` | 不使用 | `<requirement.id>-事件.yaml`，例如 `REQ-001-事件.yaml` |
| `SPEC` | `SPEC-*` | `<subject_id>-事件.yaml` |
| `IMPLEMENTATION` | `IMP-*` | `<subject_id>-事件.yaml` |
| `ACCEPTANCE` | `ACC-*` | `<subject_id>-事件.yaml` |

普通 Issue 评论只作为上下文阅读，不改变机器快照。高影响歧义在当前对话中澄清，收束后写入目标事件；讨论本身不是第五种事件。

## 四类事件总览

| `node` | 事件对象 | 稳定 ID | 结构形态 | 评论标题 |
|---|---|---|---|---|
| `REQ` | `requirement` | `REQ-*` | 每次完整需求快照 | `[DP:REQ] REQ-* 当前需求` |
| `SPEC` | `specification` | `SPEC-*` | 完整快照或相对基础 SPEC 的增量 | `[DP:SPEC] SPEC-* 当前验收规格` 或 `验收规格增量` |
| `IMPLEMENTATION` | `implementation` + `impact` | `IMP-*` | 一次 READY 实现完成事实 | `[DP:IMPLEMENTATION] IMP-* 实现完成` |
| `ACCEPTANCE` | `acceptance` + `impact` | `ACC-*` | 一次 targeted/full 验收结论 | `[DP:ACCEPTANCE] ACC-* · 单次/全量验收 · ...` |

`REQ` 不携带 `subject_id` 或 `impact`；`SPEC` 不携带 `impact`；`IMPLEMENTATION` 和 `ACCEPTANCE` 必须携带 `impact`。同一 `event_id` 重复准备时脚本返回 `duplicate`；不同的 `IMP-*` 和 `ACC-*` 是独立事实，全部保留。

## REQ：完整需求快照

REQ 每次都保存发布时的完整需求，不保存相对上一条 REQ 的差异。下面是可作为事件文件起点的完整最小结构：

```yaml
document_type: deep_crew_delivery_event
event:
  event_id: EVT-20260902-REQ-001
  created_at: "2026-09-02T12:00:00+08:00"
  author: product-owner
  node: REQ
  reason: 根据当前讨论整理完整需求
  references:
    issue: http://example/issues/1
  requirement:
    id: REQ-001
    issue_no: HTW-000
    title: 登录失败反馈
    statement: 用户能够理解登录失败原因
    business_outcomes:
      - 用户能够判断下一步操作
    scope:
      included: [Web 登录, 移动端登录]
      excluded: [账号注册]
    constraints:
      - 继续使用现有认证服务
    dependencies: []
    open_questions: []
```

必填内容是 `id`、`issue_no`、`title`、`statement`、`business_outcomes`、`scope.included`、`scope.excluded`、`constraints`、`dependencies` 和 `open_questions`。人类评论按“需求目标、需求陈述、Issue No、业务结果、范围、约束、依赖、未决事项、发布说明”的顺序展示。REQ 发布时必须向 `prepare_event.py` 提供 `--requirement-file`；脚本比较全部业务字段，并将本地 `release_notes` 与事件 `reason` 比较，只忽略本地状态、确认信息和事件发布技术元数据。

## SPEC：完整快照或增量

首次建立规格、需要重建基线或无法可靠表达为差异时使用完整快照：

```yaml
document_type: deep_crew_delivery_event
event:
  event_id: EVT-20260902-SPEC-001
  created_at: "2026-09-02T12:10:00+08:00"
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

场景必须表达 `business_result`、`given`、`when`、`then` 和 `delivery_surfaces`；检查必须表达场景引用、验证类型、验证责任、是否必需和是否阻断；断言必须表达 CHK 引用、结果引用、类型和可观察描述。

后续规格变化默认使用相对最新已确认 SPEC 的增量。增量是同样完整的事件包络，且必须带新的 `subject_id`：

```yaml
document_type: deep_crew_delivery_event
event:
  event_id: EVT-20260902-SPEC-002
  created_at: "2026-09-02T12:20:00+08:00"
  author: acceptance-owner
  node: SPEC
  subject_id: SPEC-002
  reason: 增加错误提示的验收断言
  specification:
    requirement_ref: REQ-001
    base_spec_ref: SPEC-001
    changes:
      added:
        scenarios: []
        checks: []
        assertions:
          - id: AST-002
            check_id: CHK-001
            outcome_refs: [SCN-001.THEN-001]
            assertion_type: semantic
            description: 失败原因文案对用户可理解
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

新增和修改对象使用完整结构并保留稳定 ID；删除只列对象 ID；同一 ID 不得同时出现在新增、修改或删除中，且三组变化至少有一项。模型负责结合完整评论时间线应用增量，准备脚本只校验和渲染，不读取历史或自动合并。

## IMPLEMENTATION：READY 完成交付

IMPLEMENTATION 只在实现、开发检查、完成前复核和 Git commit 均固定后发布一次。`READY` 表示具备交给验收角色验证的条件，不表示验收通过。下面是结构完整的最小示例；真实事件必须替换路径、报告和 commit：

```yaml
document_type: deep_crew_delivery_event
event:
  event_id: EVT-20260902-IMP-001
  created_at: "2026-09-02T13:00:00+08:00"
  author: developer
  node: IMPLEMENTATION
  subject_id: IMP-001
  reason: 完成本轮事件契约文档优化
  implementation:
    status: READY
    requirement_ref: REQ-EVENT-CONTRACT-DOCS
    spec_refs: [SCN-EVENT-CONTRACT-DOCS-001, CHK-EVENT-CONTRACT-DOCS-001, AST-EVENT-CONTRACT-DOCS-001]
    summary: 补齐四类事件的可执行示例和接入规则
    completed_items:
      - id: SLICE-EVENT-CONTRACT-DOCS-001
        title: 补齐事件契约开发接入说明
        kind: engineering_slice
        objective: 让开发者能够按文档准备四类事件
        check_refs: [CHK-EVENT-CONTRACT-DOCS-001]
        assertion_refs: [AST-EVENT-CONTRACT-DOCS-001]
    change_surface:
      production_files: [.agents/skills/dc-context-loop-kit/dc-context-loop/references/event-contract.md]
      test_files: []
      scripts: []
      new_interfaces: []
      changed_interfaces: []
      database_changes: []
      configuration_changes: []
      dependency_changes: []
      external_contract_changes: []
    development_checks:
      - command: 文档结构检查
        status: PASSED
        summary: 四类事件章节和完整示例均存在
    known_limits: []
    repository:
      worktree_root: /workspace/project
      git_toplevel: /workspace/project
    git_commit: 0000000000000000000000000000000000000000
    completion_review:
      status: PASSED
      performed_after_self_test: true
      preflight:
        status: PASSED
        report: 覆盖预检报告路径或摘要
      program:
        status: PASSED
        command: 文档结构检查
        report: 程序化复核报告路径或摘要
        findings: []
      semantic:
        status: PASSED
        reviewed_assertions: [AST-EVENT-CONTRACT-DOCS-001]
        findings: []
  impact:
    affected_ids: [REQ-EVENT-CONTRACT-DOCS, SPEC-001]
    next_actions:
      - action: 执行当前 SPEC 验收
        owner: acceptance-owner
```

`completed_items` 中的切片 ID 使用 `SLICE-*`；`spec_refs` 可引用当前实现覆盖的 `SCN-*`、`CHK-*` 和 `AST-*`。`change_surface` 只记录本次实际涉及面；`completion_review` 必须记录自测前覆盖预检、程序化复核和 Agent 语义复核均通过。发布前必须使用 `prepare_event.py --verify-git` 验证仓库、commit、HEAD 和 tracked 工作区。

## ACCEPTANCE：单次或全量验收结论

ACCEPTANCE 必须保存唯一 Git commit、验收范围、RUN、ART、逐 AST 结果和最终结论。指定一个 `IMP-*` 时使用 `targeted`；未指定 IMP 时使用 `full`。下面是可直接校验的 targeted 阻塞示例：

```yaml
document_type: deep_crew_delivery_event
event:
  event_id: EVT-20260902-ACC-001
  created_at: "2026-09-02T14:00:00+08:00"
  author: acceptance-owner
  node: ACCEPTANCE
  subject_id: ACC-001
  reason: 目标实现的真实验收环境不可用
  acceptance:
    status: BLOCKED
    requirement_ref: REQ-EVENT-CONTRACT-DOCS
    spec_refs: [SCN-EVENT-CONTRACT-DOCS-001, CHK-EVENT-CONTRACT-DOCS-001, AST-EVENT-CONTRACT-DOCS-001]
    implementation_refs: [IMP-001]
    mode: targeted
    scope_refs:
      scenarios: [SCN-EVENT-CONTRACT-DOCS-001]
      checks: [CHK-EVENT-CONTRACT-DOCS-001]
      assertions: [AST-EVENT-CONTRACT-DOCS-001]
    req_completion_impact: NONE
    repository:
      worktree_root: /workspace/project
      git_toplevel: /workspace/project
    git_commit: 0000000000000000000000000000000000000000
    runs:
      - id: RUN-001
        phase: real_test_app
        check_refs: [CHK-EVENT-CONTRACT-DOCS-001]
        assertion_refs: [AST-EVENT-CONTRACT-DOCS-001]
        status: BLOCKED
    artifacts:
      - id: ART-001
        type: state_observation
        location: 验收环境不可用的可审阅记录
    assertion_results:
      - assertion_id: AST-EVENT-CONTRACT-DOCS-001
        expected: 文档示例可用于准备四类事件
        observed: 验收环境不可用，无法完成本次运行
        status: BLOCKED
        artifact_refs: [ART-001]
    reason: 缺少验收所需的真实环境，不能将未观察结果记为通过
  impact:
    affected_ids: [REQ-EVENT-CONTRACT-DOCS, IMP-001]
    next_actions:
      - action: 准备验收环境后重试 targeted 验收
        owner: acceptance-owner
```

`full` 验收使用同一结构，只需将 `mode` 改为 `full`，`scope_refs` 改为当前有效 SPEC 的完整范围；只有 `full + SATISFIED` 时 `req_completion_impact` 才能为 `ELIGIBLE`。`targeted` 必须且只能引用一个 `IMP-*`，并且 `req_completion_impact` 必须为 `NONE`。结论只能是 `SATISFIED`、`NOT_SATISFIED`、`BLOCKED` 或 `INCOMPLETE`。

## 发布和验证

准备事件时使用本次 operation workspace 作为输出目录：

```bash
python3 <skill-dir>/scripts/prepare_event.py \
  --event-file <event.yaml> \
  --requirement-file <需求.md> \
  --issue <issue-ref> \
  --comments-json <fresh-comments.json> \
  --output-dir <operation-workspace>
```

`--requirement-file` 仅用于 REQ 事件，其他节点不得提供。

脚本会校验节点字段、生成同名 Markdown 评论和 YAML 附件，并报告是否已存在相同 `event_id`。发布时正文必须复用生成的 Markdown，YAML 作为同一操作工作区中的附件上传；API 返回 2xx 才算发布成功。不要通过发布后的 Issue 重读来确认结果，也不要把本地路径、测试名称或退出码当作验收证据。
