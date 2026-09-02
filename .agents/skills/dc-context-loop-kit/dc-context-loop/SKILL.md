---
name: dc-context-loop
description: 基于 Deep Crew Issue 评论时间线持续推进需求、验收定义、实现和验收的循环交付技能。只要用户提供 Deep Crew Issue URL、UUID、Issue Key，或要求继续处理一个正在变化的 Issue，就使用本技能。它把评论作为历史输入，由模型结合 REQ、SPEC（SCN/CHK/AST）、IMPLEMENTATION、ACCEPTANCE 四类交付事件恢复当前理解并决定下一步；存在高影响歧义时在当前对话中调用 dc-grilling 澄清，再直接生成目标节点事件。适用于需求不断调整、代码反复修复、测试和验收多轮循环的真实开发过程。
---

# Deep Crew Context Loop

## 核心模型

这是 Deep Crew 专属的长期循环技能。Issue 的全部相关评论保存协作历史；本地文件、HTML 或缓存保存当前定义、执行材料和派生视图。

Issue 读取由 `dc-context-loop` 统一协调，不由节点技能自行触发。每一轮开始时，必须通过 `dc-issue-intake` 读取 Issue 和全部评论；完整原始时间线交给模型理解。模型结合评论内容、结构化事件、本地代码和用户最新指令，总结当前上下文并判断本轮唯一下一步。时间和评论 ID 只作为阅读历史时的排序依据。

```text
每轮重新读取原始评论 → 模型总结当前上下文 → 判断本轮唯一节点 → 调用至多一个节点协调技能 → 发布事件后按 API 结果结束本轮
```

需求、实现和验收都可以持续多轮进行。每轮只处理一个责任节点：最多调用一个节点技能，最多发布一个结构化事件。事件发布动作返回成功、失败或结果未知后，立即结束本轮；下一轮重新 intake，不在同一轮自动切换下游节点。

## 角色定位与边界

使用 `dc-issue-intake` 获取实时 Issue Context Package；不要使用陈旧评论缓存。只有用户提供或确认唯一 Issue 标识后才能执行 intake；无法唯一确定仓库或 Issue 对应的本地上下文时，先询问，不猜测。当前轮的节点技能可复用本轮已读取的 context，但不得跨轮复用，也不得创建额外的上下文版本副本。

本技能是 Issue 级总协调器，不只是评论读取器或评论渲染器。它负责在每轮开始时让模型从新读取的完整时间线恢复当前理解，判断当前应进入哪个节点，并调用至多一个对应的节点协调技能；它在本轮完成一个节点动作后停止，等待下一轮重新读取和路由。节点完成后不在同一轮自动进入下游节点。

本技能不替代节点技能完成节点内部工作：

| 当前节点 | 节点协调技能 | 节点技能负责内容 |
|---|---|---|
| `REQ` | `dc-requirement-slicing` 配合 `dc-grilling` | 需求归类、需求边界和 REQ 事件 |
| `SPEC` | `dc-acceptance-design` 配合 `dc-grilling` | SCN、CHK、AST、映射和确认 |
| `IMPLEMENTATION` | `dc-implementation-execution` 配合 `dc-grilling` | 本地完成工程盘点、计划、代码和开发测试，最后发布一条 IMPLEMENTATION 完成事件 |
| `ACCEPTANCE` | `dc-acceptance-verification` → `dc-acceptance-closure` | 本地完成 RUN、ART、逐 AST 验证和验收裁决，最后发布一条结论事件 |

节点技能拥有其节点内容的推进权和事件写入责任；本技能拥有跨节点路由权和循环推进责任。它不自动替用户确认业务决策，不把代码测试直接写成验收通过，也不修改负责人或人工结论。没有 Issue 时使用普通的本地交付或开发技能。

## 模型上下文理解与路由契约

`dc-context-loop` 的核心职责是语义理解和路由，不是把评论字段机械合并成状态机。每轮开始触发完整 intake 后，模型必须以以下材料为输入：

- `dc-issue-intake` 返回的 Issue 原文、完整评论时间线、回复、附件信息和覆盖状态；
- 用户在当前对话中的最新消息和明确指令；
- 与当前任务相关的本地代码、`AGENTS.md`、README、项目配置、知识文件和已有交付材料；
- 评论中的结构化 REQ、SPEC、IMPLEMENTATION、ACCEPTANCE 事件，作为可引用的交付事实，而不是自动优先于普通讨论的隐藏状态。

模型必须先形成当前上下文理解，再进行路由。理解至少要明确区分：

- 已确认事实和已确认决策；
- 普通讨论、建议和未经确认的意见；
- 用户最新指令及其相对历史的变化；
- 当前仍适用的需求、规格、实现和验收事实；
- 冲突、缺失信息、未决问题和真实阻塞。

然后模型负责判断：

1. 先判断用户最新消息是否改变业务目标、业务结果、范围、约束或失败规则；
2. 只有业务承诺未变化时，再判断场景、参与者、条件、动作、结果、CHK、AST、验证责任或验证方式是否变化；
3. 只有 REQ 和 SPEC 都未变化时，才判断是否只是代码、测试或环境变化；
4. 据此选择当前最小责任节点 `REQ`、`SPEC`、`IMPLEMENTATION` 或 `ACCEPTANCE`；
5. 判断是否存在会改变当前结果的高影响歧义，需要调用 `dc-grilling`；
6. 判断当前可以安全执行的下一步、所需负责人和必要门禁。

判定结果必须遵守以下优先级：

```text
业务目标、业务结果、范围、约束或失败规则变化
  → REQUIREMENT_CHANGE；若形成独立业务结果则为 NEW_REQUIREMENT
业务承诺不变，但场景、CHK、AST、验证责任或验证方式变化
  → SPEC_CHANGE
REQ 和 SPEC 都不变，只改代码、测试或环境
  → IMPLEMENTATION_ONLY
以上都未变化
  → NO_REQUIREMENT_CHANGE
```

`SPEC_CHANGE` 表示当前验收定义变化，不表示修改或删除历史 SPEC 事件。已确认的 SPEC 发生变化时，发布新的 SPEC 事件；默认使用相对最新已确认 SPEC 的增量 `changes`，只记录新增、修改、删除的对象，旧事件保留为历史事实。需要建立基线或增量无法可靠表达时，才发布完整 SPEC 快照。

模型的路由输出至少包含：

```text
当前上下文：基于完整历史的事实、决策、适用定义和阻塞摘要
需求变化判断：NEW_REQUIREMENT / REQUIREMENT_CHANGE / SPEC_CHANGE / IMPLEMENTATION_ONLY / NO_REQUIREMENT_CHANGE
当前节点：REQ / SPEC / IMPLEMENTATION / ACCEPTANCE
追问判断：不需要，或需要澄清的高影响问题
下一步：一个最小可执行动作及其负责人
依据：相关评论、用户指令、本地代码或知识文件引用
```

只有完成上述理解和路由后，才调用节点技能。节点技能不得自行调用 `dc-issue-intake`，而是使用总协调器已经放入当前 Agent 会话的 Issue context；发布事件后也不得为了确认评论而重新 intake。不得由脚本根据 `next_actions`、最新评论或事件时间自动推进节点。

### 节点前置材料检查

在调用目标节点技能前，总协调器必须基于本轮 `dc-issue-intake` 返回的完整 Issue context 检查前置交付材料。检查对象是 Issue 评论中的结构化事件及其可解析 YAML 附件；本地 `需求.md`、`验收场景.md`、`验收矩阵.md` 或实现计划只能作为工作材料，不能单独替代线上事件。

最小前置关系如下：

| 目标节点 | 进入前必须在线存在的材料 | 关键匹配关系 |
|---|---|---|
| `REQ` | 无前置事件 | 当前输入足以形成需求时才生成 REQ |
| `SPEC` | 当前需求对应的已确认 `REQ` 事件 | `specification.requirement_ref` 必须匹配 REQ ID |
| `IMPLEMENTATION` | 当前需求对应的 `REQ` 事件、已确认的 `SPEC` 事件 | REQ ID 匹配；实现计划引用的 SCN/CHK/AST 必须属于当前 SPEC |
| `ACCEPTANCE` | 当前 `REQ`、已确认 `SPEC`、适用的 `IMPLEMENTATION READY` 事件 | 验收引用的 REQ/SPEC/IMP 必须与当前定义和目标 commit 匹配；且必须有明确验收授权 |

“在线存在”至少要求：评论已被本轮完整 intake 读取，事件附件存在且可下载/解析，事件 `node`、稳定 ID、引用关系和确认状态可从机器内容复核。评论正文中的摘要、失效附件、旧事件或本地文件不能单独满足前置条件。

若前置材料缺失、不可解析、未确认或引用不匹配：

- 不调用目标节点技能；
- 不生成目标节点事件、RUN 或 ART；
- 明确列出缺失材料、失效引用和下一步动作；
- 若只是当前 Issue 历史不完整，先回到 `dc-issue-intake`；若事件确实不存在，停在当前节点，等待先补齐上游事件。

该检查是 Loop 的编排门禁，不改变事件 Schema，也不替代 `prepare_event.py` 的字段校验。它必须在每次跨节点路由前执行，不能仅依赖上一轮的判断或 `impact.next_actions`。

`dc-context-loop` 负责跨节点判断和交接；节点技能负责本节点的专业工作和结构化事件内容；`prepare_event.py` 只负责事件格式校验与评论渲染。

## 四个交付内容节点

事件契约支持 `REQ`、`SPEC`、`IMPLEMENTATION` 和 `ACCEPTANCE` 四类交付内容。它们负责保存定义或完成事实；讨论在当前对话中完成，收束结果进入目标内容。

REQ 事件保存发布时的完整快照。SPEC 事件可以保存完整快照，也可以保存相对 `base_spec_ref` 的增量 `changes`；模型结合完整时间线把增量应用到基础 SPEC，形成当前有效定义。脚本只校验和渲染，不读取历史、不自动合并、不自动路由。快照内部的 `REQ-*`、`SCN-*`、`CHK-*`、`AST-*` 只用于当前内容的引用。IMPLEMENTATION 和 ACCEPTANCE 是独立事实，每次完成动作都创建新的 `IMP-*` 或 `ACC-*`。

| 交付内容节点 | 稳定 ID 示例 | 负责内容 | 常见后继动作 |
|---|---|---|---|
| `REQ` | `REQ-001` | 目标、业务结果、范围、约束 | 补充或调整 SPEC |
| `SPEC` | `SCN-001`、`CHK-001`、`AST-001` | 当前场景、检查责任、可观察断言及映射 | 更新实现或重新验收 |
| `IMPLEMENTATION` | `IMP-001` | 一次完成后的实现交付摘要、实际变更面、开发检查、限制和 commit | 请求验收或处理后续反馈 |
| `ACCEPTANCE` | `ACC-001`、`RUN-001`、`ART-001` | 正式运行、证据、逐 AST 结果、结论 | 回到实现、SPEC 或 REQ |

`SPEC` 是一个逻辑节点，SCN、CHK、AST 在同一份完整结构化快照中协同维护。它们在该快照内通过 `scenario_ids`、`check_id` 和 `outcome_refs` 建立关系；下一份 SPEC 快照可以整体重写场景集合。

### 讨论：节点内部的辅助流程

当目标内容存在会改变结果的高影响歧义时，调用 `dc-grilling` 在当前对话中查事实、追问并形成共享理解。它可以辅助四个节点；收束后的决策直接进入目标节点内容。

讨论只持续到当前动作可以安全执行。内容足够明确时直接继续；低风险且可逆的歧义可以明确假设后继续。收束后把确认结果直接写入对应的 REQ、SPEC、IMPLEMENTATION 或 ACCEPTANCE 事件；若用户要求长期保留某个业务决策，也应落入目标节点字段。未回答的关键问题不能由 Agent 猜测。请求人工确认 REQ 或 SPEC 时，必须先在当前对话中展示人类可点击的草案文件链接；在用户明确确认前不得发布对应 REQ/SPEC 事件。

### REQ 当前完整定义

每条 REQ 事件都必须一次提供完整 `requirement`：`id`、`title`、`statement`、`business_outcomes`、`scope.included`、`scope.excluded`、`constraints`、`open_questions`。人类区展示完整需求和本次发布说明。REQ 只表达业务目标、范围和约束，不直接修改 SPEC、代码或验收结论。

### SPEC 当前完整定义

每条 SPEC 事件都必须一次提供 `requirement_ref`、`open_questions`，以及以下二选一：

- 完整快照：`scenarios`、`checks`、`assertions`；用于首次建立规格或需要重建基线时。
- 增量：`base_spec_ref` 和 `changes.added/modified/removed`。新增、修改对象使用完整结构并保留稳定 ID；删除只列出对象 ID；同一 ID 不得同时出现在多个操作中；至少有一项变化。

场景至少表达业务结果、`given`、`when`、`then` 和交付面；检查责任表达场景引用、验证类型和验证责任；断言表达 CHK 引用、`outcome_refs`、断言类型和断言描述。人类评论按事件形态展示完整规格或增量内容。模型负责结合历史应用增量，脚本不合并历史。

### IMPLEMENTATION 完成交付

每个 `IMP-*` 代表一次已经完成的实现交付。实现计划、编码、调试和开发测试在本地完成；完成后新建一个 `IMP-*` 完成事实。事件直接保存 `implementation` 完成对象，至少包含 `status: READY`、`requirement_ref`、`spec_refs`、`summary`、`completed_items`、`change_surface`、`development_checks`、`known_limits`、`repository` 和完整 `git_commit`。`repository` 必须记录 `worktree_root` 与 `git_toplevel`，供独立验收 Agent 直接定位代码。

完整时间线保留全部 `IMP-*`。路由到验收时，模型选择引用当前 REQ/SPEC 且仍然适用的 `READY` 实现；验收事件通过 `implementation_refs` 明确本次使用的实现。

`change_surface` 按以下字段记录本次实际交付：`production_files`、`test_files`、`scripts`、`new_interfaces`、`changed_interfaces`、`database_changes`、`configuration_changes`、`dependency_changes`、`external_contract_changes`。这些是实现追踪信息，不是验收证据；代码细节和逐行差异由 Git commit/diff 负责。实现评论必须在人类摘要中展示实现工作树、Git 根目录和完整 commit。

发布 IMPLEMENTATION 或 ACCEPTANCE 事件前，必须在目标 `repository.worktree_root` 执行 Git 绑定校验：确认 `git_toplevel`、完整 40 位 `git_commit`、commit 对象存在、commit 等于当前 `HEAD`，并且没有未提交的 tracked 修改。使用事件准备工具时必须带 `--verify-git`；校验失败不得生成可发布评论。

`READY` 只表示本次实现已经完成并具备交给验收角色验证的条件，不代表验收通过。人类评论展示本次摘要、完成项、实际变更面、开发检查、已知限制和 commit。

实现节点在发布 `IMPLEMENTATION READY` 前必须完成“自测前覆盖预检 → 自测后程序化完成复核 → 自测后 Agent 语义完成复核”。程序检查计划覆盖、引用、文件变更、开发检查记录、阻塞状态和 Git 事实；Agent 逐 AST 判断实现是否真正满足当前语义。任一程序硬检查或语义复核失败，都不得发布 `READY`，应留在 IMPLEMENTATION 或按变化路由到 SPEC/REQ。完成前复核属于实现内部门禁，不是正式验收，不生成 RUN/ART/ACC。

### ACCEPTANCE 最终结论

验收过程全部在本地完成。`dc-acceptance-verification` 负责执行当前实现并形成 RUN/ART，`dc-acceptance-closure` 负责审查证据并逐 AST 裁决；两者完成后由总协调器发布一条独立的 `ACCEPTANCE` 事实事件。该事件使用新的 `ACC-*`，直接保存完整 `acceptance` 结论，绑定当前 REQ、SPEC、IMPLEMENTATION 和唯一 Git commit，保存 RUN、ART、逐 AST 结果和最终 `status`：`SATISFIED`、`NOT_SATISFIED`、`BLOCKED` 或 `INCOMPLETE`。

## 事件契约

完整契约见 `contracts/event.schema.yaml`。评论必须包含人类摘要、事件标识和机器 YAML 附件引用；机器 YAML 不内嵌评论正文：

```text
## 机器事件附件

- event_id：`EVT-...`
- YAML 附件：`<subject-id>-事件.yaml`
- 解析方式：从 Issue comment 附件下载并解析 YAML。
```

REQ 事件最小结构：

```yaml
document_type: deep_crew_delivery_event
event:
  event_id: EVT-20260826-001
  created_at: "2026-08-26T15:30:00+09:00"
  author: user
  node: REQ
  reason: "根据当前讨论整理完整需求"
  requirement:
    id: REQ-001
    title: 登录失败反馈
    statement: 用户能够理解登录失败原因
    business_outcomes: [用户能够判断下一步操作]
    scope: {included: [Web 登录], excluded: [账号注册]}
    constraints: [继续使用现有认证服务]
    open_questions: []
```

REQ 每次都发布当时的完整内容。SPEC 首次建立或需要重建基线时发布完整快照，后续变化默认发布相对最新已确认 SPEC 的增量。模型结合完整评论时间线应用增量并判断当前适用的定义；评论时间和结构化事件 ID 只作为引用和排序依据。

### 影响传播

`impact.affected_ids` 列出本次完成事实涉及的对象，`next_actions` 列出建议动作和负责人。影响是指导信息，不是隐藏状态机；模型仍需根据完整沟通历史判断最小下一步。

典型路由：

```text
新的 REQ 快照 → 按需重新生成 SPEC → 实现完成后重新验收
新的 SPEC 完整快照或增量 → 模型应用后实现完成并重新验收
新的 IMPLEMENTATION 交付 → 报告 READY 并等待明确验收指令
验收技能产出失败或阻塞结论 → Context Loop 根据验收证据和当前定义路由回 IMPLEMENTATION；若验收定义不可裁决，才回到 SPEC/REQ 并按需调用 grilling
环境问题 → 记录阻塞并只重做受影响验收
```

## 长期循环

### 0. 总协调器循环

总协调器按当前会话和动作触发以下动作：

1. 每轮开始都通过 `dc-issue-intake` 完整读取 Issue 评论，并让模型总结当前上下文；不得用上一轮的 Issue context、评论缓存或模型记忆替代本轮 intake。
2. 若没有用户提供或确认的唯一 Issue 标识，先请求确认；确认前不得调用 Issue 读取 API。
3. 检查冲突、当前定义状态、实现状态和验收状态，根据当前影响选择一个最小可推进节点，不跨过必要门禁。
4. 调用该节点的协调技能；节点不得自行 intake。每轮最多调用一个节点技能；实现尚未完成时不要求发布 IMPLEMENTATION 进度事件。
5. 事件发布前，先在当前 Agent 上下文中完整展示人类摘要、事件标识和附件引用；实际上传正文必须复用已展示的同一内容，并将机器 YAML 作为同一操作工作区中的附件上传。
6. 处理发布 API 结果：2xx 判定成功，非 2xx 判定失败，超时或无响应判定结果未知；无论哪种结果都不执行发布确认后的 Issue 重读。
7. 处理本轮唯一节点动作；每轮最多发布一个结构化事件，事件发布动作返回成功、失败或结果未知后都结束本轮。若节点未发布事件但需要用户决策、人工门禁或外部环境，也结束本轮并明确暂停原因。任何下游节点必须在下一轮重新 intake 后再路由。

总协调器的输出不是“已写评论”这一动作，而是“当前上下文、当前责任节点、节点技能执行结果、下一步路由”。评论只是跨轮次保存状态的载体。

### 1. Intake 和上下文理解

在每轮开始且 Issue 标识已由用户提供或确认时，调用 `dc-issue-intake` 获取 Issue、完整评论和必要附件，并确认 intake 覆盖状态为 `FULL`。不要使用上一轮的 Issue context 或评论缓存；不要再运行独立的时间线归约脚本，也不要把结构化事件的字段合并结果当成自动状态机。模型直接阅读本轮返回的完整原始时间线，区分结构化交付事实、普通讨论、用户最新指令、已确认决策、冲突和未决问题，再形成当前上下文理解。

`dc-issue-intake` 的覆盖状态、分页信息、评论原文和附件信息是输入完整性的依据；如果 intake 报告 `INCOMPLETE`，不得声称已经恢复完整历史。

### 2. 判断新输入归属

模型先按上述上下文理解契约判断新信息属于 `REQ`、`SPEC`、`IMPLEMENTATION` 或 `ACCEPTANCE` 哪个交付内容节点。内容不清、存在多个合理解释或需要负责人决策时，先调用 `dc-grilling` 在当前对话中澄清；讨论足够清晰后直接生成目标内容节点事件，不发布讨论事件。业务承诺变化不能伪装成 SPEC 或代码修复；业务承诺不变但验收定义变化时归入 SPEC；如果已有 SPEC 已覆盖期望但实现错误，归入 IMPLEMENTATION；如果定义无法裁决验收，则先澄清 SPEC 或 REQ。

### 3. 发布完整定义或完成事实

准备事件并检查重复：

```bash
python3 <skill-dir>/scripts/prepare_event.py \
  --event-file <event.yaml> \
  --issue <issue-ref> \
  --comments-json <fresh-comments.json> \
  --output-dir <operation-workspace>
```

`--output-dir` 只能使用本次操作工作区。工作区必须先由目标 IMPLEMENTATION
事件的 `repository.worktree_root` 派生：

```text
<repository.worktree_root>/.local/dc-loop/tmp/<operation-id>/
```

使用 `scripts/operation_workspace.py create --worktree-root <root>` 创建唯一目录，禁止从验收 Agent 当前目录推断根目录，也禁止使用根目录之外的 `/tmp`、用户目录或其他仓库。所有可能生成临时文件或缓存的命令必须通过 `scripts/operation_workspace.py exec --worktree-root <root> --operation-id <id> -- <command>` 执行；该入口统一注入 `TMPDIR`、`TMP`、`TEMP`、`PYTHONPYCACHEPREFIX` 和 `DC_LOOP_OPERATION_WORKSPACE`。操作成功、失败、阻塞或中止后都必须调用同一脚本的 `cleanup --terminal-status SUCCESS|FAILED|BLOCKED|INTERRUPTED` 并确认清理结果；清理失败不得宣称动作完成。事件准备所需的评论缓存（如有）也属于该操作目录，不用于发布后的确认重读。

`prepare_event.py --output-dir` 不得指向 `.local/dc-loop/drafts` 或其子目录；事件评论和 YAML 附件只能在本次 operation workspace 中生成。升级前遗留的事件 YAML 通过 `scripts/event_artifact_cleanup.py cleanup_legacy_drafts --worktree-root <repository.worktree_root> --issue-key <ISSUE-KEY>` 按明确 Issue 范围清理；该命令只删除 `REQ|SPEC|IMP|ACC-*-事件.yaml`，保留同目录 Markdown 草案和其他 Issue 材料。清理完成后仍按操作工作区终态规则处理本次临时目录。

本地交付证明不是阶段副本。完整 intake 且 ACC 结论落地后，使用
`scripts/delivery_index.py` 刷新 `docs/交付证明/<ISSUE-KEY>.md`；该文件只保存 Issue 导航和同步元数据，不纳入 Git。存在同一 Issue 的旧阶段目录或派生清单时，通过重复的 `--legacy-path` 显式指定，并同时提供 `--worktree-root`；工具只允许归档 `docs/交付证明` 下的明确路径，将其移入 `.local/dc-loop/archive/<ISSUE-KEY>/`，拒绝越界、符号链接和覆盖。检查模式发现任一指定旧路径仍存在时失败。SPEC/IMP 发布期间不刷新最终索引，索引一致性检查必须比较事件编号、event_id、评论 UUID、分类、计数、最后评论 ID 和覆盖状态。

脚本会生成一份人类可读评论和同名机器 YAML 附件，并返回 `duplicate`。REQ 使用完整快照；SPEC 使用完整快照或 `base_spec_ref + changes` 增量；IMPLEMENTATION/ACCEPTANCE 使用独立完成事实。脚本只校验和渲染，不读取历史、不合并增量、不自动路由。相同 `event_id` 已存在时跳过重复发布；不同的 `IMP-*` 或 `ACC-*` 应保留为新的时间线记录。

IMPLEMENTATION 事件准备前还必须在目标实现计划和事件上运行 `dc-context-loop/scripts/review_implementation.py`。该程序执行自测前覆盖预检的结果核对、自测后结构/Git/变更面硬检查，并输出可定位报告；随后由 Agent 完成逐 AST 语义复核并写入 `completion_review`。没有程序复核报告或语义复核未覆盖全部行为 AST 时，不得调用 `prepare_event.py` 发布 READY 事件。

REQ 评论展示本次完整快照；SPEC 评论展示本次完整快照或增量变化；实现完成评论展示本次摘要、交付面、开发检查和限制，不展示上一次实现对比。摘要由结构化事件生成，不手工维护第二份内容。

### 4. 实现和验收

实现完成事件记录本次交付和 commit，但不宣称验收通过。`IMPLEMENTATION READY` 只是交给验收角色的条件，不是验收授权。总协调器在 READY 后必须先检查当前用户消息是否包含明确的验收指令：

- 明确的“执行验收”“开始验收”“请验收”等指令，才允许进入 `ACCEPTANCE`，调用 `dc-acceptance-verification` 和 `dc-acceptance-closure`；
- 没有明确验收指令时，硬停止在等待状态，只报告绑定的实现、commit 和等待原因；
- 不调用 `dc-acceptance-verification`，不生成 `RUN`、`ART` 或 `ACC-*`；
- `READY`、`impact.next_actions` 以及“继续”“可以”“来吧”等泛化表达不构成验收授权。

收到明确验收指令后，先在验收验证开始前通过 `dc-issue-intake` 完整读取 Issue comments，确认覆盖状态为 `FULL`，并将本次结果作为验收依据；同一验收轮的后续技能继续复用该上下文，不再次 intake。再确定验收模式：指令明确指定 `IMP-*` 时使用 `targeted` 单次验收，只覆盖该 IMP 的 `spec_refs` 展开的完整 CHK/AST；指令未指定 IMP 时使用 `full` 全量验收，覆盖当前有效 SPEC 的全部必需、阻断 CHK/AST。验收在本地完成并只发布一条验收事件，必须记录：

- `mode: targeted | full`；
- `scope_refs.scenarios/checks/assertions` 本次实际裁决范围；
- `req_completion_impact: NONE | ELIGIBLE`，只有 `full + SATISFIED` 才能使用 `ELIGIBLE`；
- 评论标题明确展示“单次验收 · IMP-*”或“全量验收 · 当前有效 SPEC”。

- 绑定的实现 commit；
- 绑定的 REQ/SPEC 对象 ID；
- RUN 和 ART 引用；
- 每个 AST 的预期、实际和结论；
- 总体结论 `SATISFIED`、`NOT_SATISFIED`、`BLOCKED` 或 `INCOMPLETE`。

`SATISFIED` 表示该时间点、当前定义和当前实现上的验收通过。后续工作从最新评论中的当前内容继续。`NOT_SATISFIED` 和 `BLOCKED` 是有效验收事件，应发布真实结果。

### 5. 回到下一轮

每轮结束时只报告当前事实和最小下一步，例如：

```text
当前上下文：当前适用的 REQ/SPEC、IMP-002，以及相关讨论中的决策和阻塞。
当前状态：当前 SPEC 中的 AST-003 需要在 IMP-002 上验证。
下一步：在新 commit 上执行验收。
```

不要因为某一节点曾经“完成”就终止 Issue；只有用户明确关闭 Issue 或明确结束协作时才停止循环。

## 发布与安全

确认事件不是重复事件后，先在当前 Agent 上下文中展示完整的人类摘要、事件标识和附件引用，再使用：

```bash
multica issue comment add <issue-ref> \
  --content-file <comment-file> \
  --attachment <file-1> \
  --output json
```

发布 API 返回 2xx 时判定成功；返回非 2xx 时判定失败；超时或无响应时判定结果未知。事件 YAML 必须作为当前操作工作区中的附件上传；发布成功后或操作进入任一终态，按操作工作区清理规则删除本地事件 YAML。发布失败或未知必须报告实际结果，不假装成功，且不得通过发布后的 Issue 重读来确认。上传前脱敏凭证、Token、Cookie 和个人敏感数据。

禁止把本地路径、测试名称、退出码或“全部通过”当作证据；必须引用可审阅的结果或 ART。不能删除或覆盖历史评论。

## 参考文件

- `contracts/event.schema.yaml`：事件结构约束；
- `dc-grilling/SKILL.md`：节点内部按需使用的澄清算法；
- `references/event-contract.md`：四个交付内容节点和事件示例；
- `scripts/prepare_event.py`：校验并渲染事件评论；
- `scripts/review_implementation.py`：在发布 IMPLEMENTATION READY 前执行程序化完成复核；
- `dc-issue-intake`：获取完整 Issue 原始时间线，作为模型上下文来源；
- `evals/evals.json`：典型循环场景。
