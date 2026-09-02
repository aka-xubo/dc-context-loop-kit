---
name: dc-implementation-execution
description: 根据已确认的 REQ、验收场景和 CHK/AST 矩阵，复用 dc-context-loop 提供的 Issue 会话上下文，先盘点代码结构与项目上下文，必要时与负责人确认未决决策，再制定并执行完整实现计划。对可单元验证的行为默认执行测试先行；仅在明确工程性、外部系统或无稳定公开接口时记录豁免。
---

# Implementation Execution

## 节点角色

本技能是 `dc-context-loop` 调用的 IMPLEMENTATION 节点协调器。它负责在当前 REQ、SPEC 和已有 IMPLEMENTATION 上下文内推动真实实现；计划、编码、调试和开发测试留在本地，完成后只向 Issue 写入一次结构化交付事实。

它不负责跨节点路由：发现业务定义、验收定义或需求边界需要变化时，返回 `dc-context-loop`，由总协调器路由到 `dc-grilling`、`dc-requirement-slicing` 或 `dc-acceptance-design`。实现达到 READY 后，也返回总协调器，由总协调器决定是否进入验收。

## 入口和边界

仅在 REQ 和包含验收场景及 CHK/AST 矩阵的完整 SPEC 均为 `CONFIRMED` 后进入。实现计划是本地工程执行契约，不是业务定义，也不是验收报告：

- 不改写 REQ、SCN、CHK 或 AST 的语义；发现业务行为、边界、失败规则或验收观察面需要改变时，暂停受影响切片，返回 `dc-requirement-slicing` 或 `dc-acceptance-design`。
- 不把 TDD 的 RED/GREEN/REFACTOR、测试名称、退出码或代码路径当作正式 RUN/ART。
- 实现过程中不发布 `PLANNED`、`IN_PROGRESS` 或 `BLOCKED` 事件；普通命令、测试和调试过程保留在本地工作上下文。
- 所有切片完成、应用就绪且 commit 固定后发布一个新的 `IMP-*` 完成事件；`READY` 不等于验收通过。

## 制定计划前：上下文盘点

进入本技能后不调用 `dc-issue-intake`。由 `dc-context-loop` 在进入 IMPLEMENTATION 前按读取门禁完成必要的完整 intake，并将基于完整历史形成的当前 Issue context 放入当前 Agent 会话；本技能直接复用该上下文。若当前会话没有有效上下文、历史存在冲突或关键字段缺失，应返回 `dc-context-loop` 补做 intake 或澄清，不得自行读取或基于猜测继续实现。

先完整阅读并在 `实现计划.md` 的 `context_review` 中记录依据：

1. 当前 `需求.md`、`验收场景.md`、`验收矩阵.md`，明确业务结果、范围、CHK 责任和逐 AST 断言。
2. `AGENTS.md`、项目 README、构建清单、依赖清单、配置示例、迁移和启动说明。
3. 代码结构、现有模块和公共入口；相关生产代码、测试、路由/页面/命令、数据库和外部系统适配层。
4. 当前运行方式、测试方式、环境前置条件和已有工程模式。

盘点必须形成：需求/场景/矩阵引用、项目上下文引用、代码结构引用，以及“已发现事实 → 对计划的影响”的 `findings`。没有完成上下文盘点，不得把计划推进到 `IN_PROGRESS`。

## 必要交互

把发现的问题分成三类处理：

- 能从当前代码、项目规范或已有模式确定的工程事实：直接采用并在 `context_review.decisions` 记录来源。
- 只影响实现方式、不改变外部行为的选择：优先沿用仓库模式；确实存在高风险或多种同等方案时，向负责人提问并记录回答。
- 会改变业务结果、边界、失败行为、数据兼容性、安全策略、迁移不可逆性或验收方式的决定：必须暂停受影响切片，与人确认；若改变 REQ/SCN/CHK/AST，退回定义阶段，不能把答案偷偷写进实现计划。

未决问题放入 `context_review.open_questions`，并保持计划停在 `PLANNED`；问题解决后从未决列表移除，在 `decisions` 中记录问题、答案、来源和受影响切片。进入 `IN_PROGRESS` 或 `READY` 时不得有未决问题。

## 条件式人工门禁

实现计划不是所有项目都要人工审批的阶段。只有计划包含下列高风险实现决策时，才在 `implementation_plan.human_gate` 声明门禁：`database_migration`、`public_api`、`auth_security`、`data_compatibility`、`irreversible_change` 或 `acceptance_observation`。

```yaml
human_gate:
  required: true
  status: PENDING
  risk_categories: [database_migration, public_api]
```

规则如下：

- `required: false` 时，`status` 必须为 `NOT_REQUIRED`，普通内部实现无需人工确认；
- `required: true` 时，计划初始保持 `PLANNED` 和 `PENDING`，不能进入 `IN_PROGRESS`；
- 负责人确认后改为 `CONFIRMED`，记录 `confirmed_by`、`confirmed_at` 和对应 `decision_refs`，才能进入 `IN_PROGRESS`；
- `READY` 仍需满足实现、应用就绪和完整 Git commit 条件；人工门禁不等于验收通过；
- 如果决定改变 REQ、SCN、CHK、AST 的业务语义，不能通过此门禁解决，必须返回定义阶段。

## 实现计划契约

实现计划至少包含：

- `requirement_ref`：当前 REQ；
- `context_review`：上下文来源、盘点结论、假设、未决问题和决策；
- `test_strategy`：默认 `tdd`，以及每个豁免的对象、理由和替代检查；
- `blockers`：真实阻塞；
- `delivery_surfaces`：API、Web、CLI 等交付面及完成状态；
- `slices`：可独立执行的垂直切片；
- `readiness`：配置、持久化、启动、外部旅程等验收前置条件。

每个切片至少记录 `id`、`title`、`kind`、`objective`、`depends_on`、`check_refs`、`assertion_refs`、`production_refs`、`test_refs` 和 `status`。`kind` 只使用：

- `behavior_slice`：实现可观察业务行为，必须关联 AST；
- `engineering_slice`：迁移、配置、依赖注入、启动装配等工程工作；
- `readiness_slice`：为真实验收准备应用、数据、环境和入口。

所有当前矩阵 AST 必须至少被一个切片覆盖；工程或就绪切片可以没有 AST，但不能用它们掩盖行为切片的缺失。切片之间的工程依赖写入 `depends_on`，不把业务依赖伪装成实现依赖。

## 执行和状态

### 临时操作工作区

实现计划、自测、完成前复核和事件准备产生的脚本副本、矩阵副本、原始输出和缓存，必须位于目标实现事件声明的
`repository.worktree_root/.local/dc-loop/tmp/<operation-id>/`。实现 Agent 先调用
`dc-context-loop/scripts/operation_workspace.py create --worktree-root <repository.worktree_root>`，并把所有工具的输出目录指向返回路径；所有会生成临时文件或缓存的自测、复核和事件准备命令都通过 `operation_workspace.py exec --worktree-root <root> --operation-id <id> -- <command>` 执行，不得直接运行后依赖系统默认临时目录。操作进入成功、失败、阻塞或中止终态时，使用 `cleanup --terminal-status SUCCESS|FAILED|BLOCKED|INTERRUPTED` 清理并验证目录不存在；清理失败会阻止 READY 和交付声明。源代码、Issue 评论和最终本地交付证明索引不属于可清理临时材料。

本地计划可以使用 `PLANNED → IN_PROGRESS → READY`，整体无法继续时为 `BLOCKED`；切片可以使用 `PLANNED → IN_PROGRESS → COMPLETED`，单个切片无法继续时为 `BLOCKED`。这些状态只服务本地执行，不发布为 Issue 评论。`COMPLETED` 只表示实现切片完成，不代表验收通过。

事件准备的 `--output-dir` 必须位于当前 operation workspace，`prepare_event.py` 会拒绝 `.local/dc-loop/drafts` 及其子目录。历史遗留的事件 YAML 不得继续作为本地事实来源；实现修复时使用 `dc-context-loop/scripts/event_artifact_cleanup.py cleanup_legacy_drafts` 按明确 Issue 清理，并保留 Markdown 草案。

每个可通过稳定公开代码接口验证的行为，默认按一个垂直切片执行 `RED → GREEN → REFACTOR`，详细规则见 [../dc-proof-resources/references/tdd-rules.md](../dc-proof-resources/references/tdd-rules.md)。以下情况才允许豁免，并在 `test_strategy.exemptions` 中写清受影响 AST、理由和替代检查：

- 工程装配、依赖注入、迁移或启动配置；
- 必须依赖真实外部系统的 E2E；
- 纯视觉样式或静态布局；
- 尚无稳定公开接口，必须先建立最小工程结构。

“测试麻烦”不是豁免理由。工程结构就绪后，继续对可单元验证的行为切片执行测试先行。
RED/GREEN/REFACTOR 只记录实现过程，不生成正式 RUN/ART。

## 完成前复核门禁

完成前复核是 IMPLEMENTATION 节点内部的强制门禁，位于开发自测之后、固定 Git commit 和发布 `IMP-* READY` 之前。它不等同于正式 ACCEPTANCE，不生成 `RUN`、`ART` 或 `SATISFIED` 结论。

门禁顺序固定为：

```text
自测前覆盖预检 → 编码与开发自测 → 程序化完成复核 → Agent 语义完成复核 → 固定 commit → 发布 READY
```

### 自测前覆盖预检

在计划从 `PLANNED` 进入 `IN_PROGRESS` 或开始自测前，先执行程序化覆盖预检：

- 当前有效 SPEC 的每个必需 AST 至少被一个实现切片引用，且引用属于当前定义；
- 每个 `behavior_slice` 都有 `production_refs` 和 `test_refs`，或记录完整、合法的 TDD 豁免；
- 不存在无效引用、未决问题或 blocker。

预检失败时不得开始受影响切片的编码或自测。该预检只检查计划结构，不判断代码是否已经实现业务行为。

### 自测后程序化完成复核

所有切片的开发自测完成后，运行 `scripts/review_implementation.py`（或等价的受控程序）检查：

- 计划中的切片、CHK/AST 引用、事件 `completed_items` 和 `spec_refs` 一致；
- 声明的生产文件、测试文件和脚本在目标 commit 中存在，并且实际出现在该 commit 的变更集合中；
- 所有切片、交付面、readiness、blocker 和 open question 满足 READY 条件；
- 开发检查有逐条命令和可复核结果，不能只写“全部通过”；
- 目标仓库、Git 根目录、commit 和 tracked 工作区状态一致。
- 在该 operation workspace 下创建只包含目标 commit 的临时工作树，并通过受控 `exec` 重跑开发检查，证明测试不依赖未跟踪文件或原工作区残留。

程序复核必须输出可定位报告；任一硬检查失败时不得进入语义复核或发布 `READY`。程序不得从“文件存在”推断业务行为已经实现。

### 自测后 Agent 语义完成复核

程序复核通过后，Agent 必须逐一对照当前 REQ、SPEC、实现计划、代码 diff 和开发自测结果，填写 `completion_review.semantic`：

- 每个已声明完成的行为 AST 都要说明生产实现、测试结果与目标语义的对应关系；
- 仅有文件或测试引用但行为未实现、测试未覆盖目标语义或交付摘要不真实时，复核失败，回到 IMPLEMENTATION 修复；
- 发现业务结果、范围、失败规则或验收观察面变化时，停止发布并路由到 REQ/SPEC；
- 只有全部行为 AST 通过语义复核且没有未决语义疑点，才能固定 commit。

语义复核是 Agent 的判断，不得由脚本用文件名、测试名、退出码或文本匹配替代。复核结论必须记录 reviewed AST、结论、实现定位、测试定位和遗留疑点。

## IMPLEMENTATION 完成事件

节点协调器只在实现真正完成后发布一次事件。事件必须使用新的 `IMP-*`，直接保存 `implementation` 完成对象，并在 `impact.next_actions` 指向总协调器下一步。完成对象必须记录 `repository.worktree_root`、`repository.git_toplevel` 和完整 `git_commit`，供独立验收直接定位代码。事件发布前使用 `prepare_event.py --verify-git` 校验仓库根目录、commit、HEAD 和 tracked 工作区状态；校验失败不得发布。发布前由 `dc-context-loop` 在当前 Agent 上下文中展示完整人类摘要、事件标识和 YAML 附件引用，发布 API 的正文必须复用同一内容并附带同一操作工作区中的事件 YAML；发布结果只依据 API 状态码分类，不在发布后重新读取 Issue。后续修复或再次实现使用新的 `IMP-*`，不修改旧事件，也不提交实现差异表。

完成对象必须从本地计划和真实工作区归纳 `requirement_ref`、`spec_refs`、交付 `summary`、已完成 `completed_items`、实际 `change_surface`、`development_checks`、`known_limits`、`repository`、完整 `git_commit` 和 `completion_review`。`completed_items` 保留切片 ID、类型、目标以及 CHK/AST 引用；`change_surface` 只记录本次实际涉及的文件、脚本、接口、数据库、配置、依赖和外部契约，不保存计划面，也不与上一次实现比较。`completion_review` 必须记录自测前预检、程序化复核和 Agent 语义复核均通过。

## READY 准入

只有同时满足以下条件才能发布 `status: READY` 的完成事件：

1. 当前 REQ、SCN、CHK/AST 仍与计划引用一致；
2. 上下文盘点已完成，且没有未决问题；
3. 所有必须实现的 AST 都有切片覆盖；
4. 所有切片、交付面和验收前置条件均完成或明确标记为 `NOT_REQUIRED`；
5. 没有未处理 blocker，生产代码和测试引用已记录；
6. 自测前覆盖预检已通过；
7. 自测后程序化完成复核已通过并生成报告；
8. 自测后 Agent 语义完成复核已通过，所有行为 AST 均已 reviewed；
9. 应用就绪校验通过，并已形成完整 Git commit；事件中的仓库路径和 commit 已通过 `--verify-git` 校验。

`READY` 只表示该次实现交付的 commit 具备交给验收角色验证的条件，不代表 `SATISFIED`。完成实现后固定 commit，再由 `dc-acceptance-verification` 执行正式 RUN/ART；提交变化会使当前验收证据失效。

详细字段、问题分类和交互示例见 [../dc-proof-resources/references/implementation-planning.md](../dc-proof-resources/references/implementation-planning.md)。
