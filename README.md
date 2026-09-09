# Deep Crew Context Loop Kit

Deep Crew Context Loop Kit 是一套可复制、可独立分发的 Issue 驱动交付技能包。它把一条持续变化的需求，组织成可追溯的需求定义、验收规格、实现提交和验收证据链。

这套技能面向需要协作交付的产品、研发、测试和项目负责人。团队成员不需要先记住所有字段；只要拿到一个 Multica/Deep Crew Issue 的 URL、UUID 或 Issue Key，就可以从总入口开始，由技能根据当前上下文选择下一步。

## 5 分钟上手

### 1. 准备 Issue 标识

Issue 是协作历史的事实来源。使用完整的 Issue URL、UUID 或 Issue Key，确保它能唯一定位到目标 Issue。

### 2. 从总协调器开始

第一次处理、需求设计、正式验收，以及你明确要求刷新上下文时，从 `dc-context-loop` 开始。规格设计和实现方案设计也由它协调，但在当前上下文有效且没有变化信号时直接复用，不因节点动作本身重新读取：

```text
处理 Issue <URL 或 Issue Key>，先读取完整上下文并判断当前应该进入哪个节点。
```

它会按读取门禁决定复用当前上下文或读取完整评论和必要附件，再结合本地材料与当前消息判断当前节点。不要直接跳到实现或验收技能。

### 3. 按当前节点继续

| 你正在解决的问题 | 入口技能 | 产出或下一步 |
| --- | --- | --- |
| 业务目标、范围、约束是否清楚 | `dc-requirement-slicing` | REQ，需人工确认 |
| 怎么证明业务结果成立 | `dc-acceptance-design` | SPEC（SCN/CHK/AST），需人工确认 |
| 已确认定义如何落地 | `dc-implementation-execution` | 实现计划、代码、自测、`IMP-* READY` |
| 已授权如何正式验收 | `dc-acceptance-verification` + `dc-acceptance-closure` | RUN/ART、`ACC-*` 结论 |

遇到需要负责人决策的歧义时，使用 `dc-grilling` 做当前对话澄清；澄清后仍回到正确的 REQ、SPEC、IMPLEMENTATION 或 ACCEPTANCE 节点。

## 它解决什么问题

普通对话容易出现“需求变了但实现没同步”“测试通过但没有业务证据”“新人不知道下一步找谁”等断点。Context Loop 用 Issue 时间线保存协作历史，用结构化事件保存交付事实，用本地文件承载当前工作材料，再用 Git commit 和验收证据把结果固定下来。

核心原则只有三条：

1. 首次处理、REQ 和正式验收前读取该 Issue 的完整上下文；SPEC/IMPLEMENTATION 默认复用，仅在上下文不足、冲突或显式变化时刷新。
2. 每一轮只推进一个责任节点，最多发布一个结构化事件；发布结果确定后结束本轮。
3. `IMPLEMENTATION READY` 只是实现提交已经具备验收条件，不等于验收通过；只有正式验收形成完整 RUN/ART 后，才能得出 `SATISFIED`。

## 技能包架构

根目录 `skills/` 是本仓库唯一的技能源码目录。每个 `dc-*` 子目录都是一个可独立发现的技能；技能之间通过包内相对关系、脚本自身位置或显式路径参数定位资源，不依赖仓库的绝对路径。

```text
skills/
├── dc-context-loop/                 总协调器、路由、事件和共享交付证明工具
├── dc-issue-intake/                 Issue、评论和附件的完整读取
├── dc-requirement-slicing/          REQ 归类与需求定义
├── dc-acceptance-design/            SPEC：场景、检查责任和断言
├── dc-implementation-execution/     实现计划、编码、自测和 READY 复核
├── dc-acceptance-verification/      执行正式验证，形成 RUN/ART
├── dc-acceptance-closure/            审查证据，逐 AST 裁决验收
└── dc-grilling/                     当前对话中的按需澄清
```

安装时由使用者根据 Agent 宿主协议选择 skills 根目录，例如 `.agents/skills/`、`.codex/skills/`、`.claude/skills/` 或其他约定位置，然后将 `skills/` 下的各个 `dc-*` 目录直接平铺到目标根目录：

```text
<host-skills-root>/
├── dc-context-loop/
├── dc-issue-intake/
├── dc-requirement-slicing/
├── dc-acceptance-design/
├── dc-implementation-execution/
├── dc-acceptance-verification/
├── dc-acceptance-closure/
└── dc-grilling/
```

不要在目标 skills 根目录与 `dc-*` 技能之间增加项目包装层。本仓库自举时可把根 `skills/` 中的技能平铺安装到本地 `.agents/skills/`；该安装入口由使用者维护并被 Git 忽略，不是第二份源码。

### 总协调器：`dc-context-loop`

`dc-context-loop` 负责 Issue 级上下文恢复、节点判断、交接和事件发布边界。它不是单纯的评论读取器，也不是自动状态机：模型仍要阅读当前 intake 返回的完整原始时间线，区分正式事件、普通讨论、已确认决策、冲突和未决问题。

它统一协调 `dc-issue-intake`，在读取门禁命中时取得新鲜 Context Package；否则复用当前有效上下文。节点技能不自行读取 Issue。它不会在同一轮自动从 REQ 跳到 SPEC、从实现跳到验收，也不会因为一个 READY 事件自动开始验收。

### 节点技能的职责边界

- `dc-issue-intake` 只负责读取实时 Issue、完整评论时间线和必要附件，并报告覆盖是否完整。
- `dc-requirement-slicing` 判断输入是新增 REQ、已有需求变化还是纯实现变化；业务目标、范围、约束或失败规则变化时使用它。
- `dc-acceptance-design` 把已确认 REQ 转成完整 SPEC；业务承诺不变但场景、验证责任、断言或验证方式变化时，生成相对已确认 SPEC 的增量。
- `dc-implementation-execution` 只在 REQ 和完整 SPEC 都确认后执行本地实现。它负责实现计划、切片覆盖、自测、完成前复核和 Git commit，不负责修改业务定义或宣布验收通过。
- `dc-acceptance-verification` 在收到明确验收授权且实现为 READY 后执行真实验证，采集 RUN/ART；它不负责最终裁决。
- `dc-acceptance-closure` 审查 RUN/ART 是否覆盖当前定义，按 AST 和 CHK 给出验收结论；最终 `ACC-*` 由总协调器发布。
- `dc-grilling` 只解决需要人工澄清的高影响歧义，不替代正式 REQ、SPEC 或验收事件。

每个技能目录中的 `contracts/`、`templates/`、`references/` 和 `scripts/` 按调用关系归属对应技能，是专业规则和工具的规范来源。根 README 只做导航和解释，不复制完整事件 Schema。

## Context Loop 生命周期

```text
Issue 标识
   ↓
完整 intake → 上下文理解 → 判断唯一责任节点
   ↓
REQ（确认） → SPEC（确认） → IMPLEMENTATION（提交 IMP READY）
                                      ↓ 明确验收授权
                              ACCEPTANCE（RUN/ART → ACC）
                                      ↓
                              根据结论进入下一轮
```

### 0. Intake 与路由

首次处理、进入 REQ、正式验收或用户明确要求刷新时，必须重新读取完整 Issue。进入 SPEC 或 IMPLEMENTATION 时默认复用当前已确认 REQ、SPEC 和有效 Issue context；只有上下文缺失、冲突、关键引用无法确认，或用户明确说明 Issue 已变化时才刷新。若 intake 为 `INCOMPLETE`，不能声称已经恢复完整历史，也不能据此跳过门禁。

模型根据本次完整上下文判断当前唯一节点：

- 业务承诺、目标、范围、约束或失败规则变化：进入 REQ。
- 业务承诺不变，但参与者、条件、动作、结果、验证责任或观察方式变化：进入 SPEC。
- 当前 REQ/SPEC 已覆盖期望，只是代码、配置或测试实现有问题：进入 IMPLEMENTATION。
- 已有 `IMP-* READY` 且用户明确授权验收：进入 ACCEPTANCE。

如果同一条消息同时包含多个方向，先处理会改变后续判断的最小节点；不要在一轮里连续推进多个下游节点。

### 1. REQ：定义为什么做

REQ 是一个业务需求的完整定义，至少说明业务结果、范围、约束、依赖和未决问题。REQ 需要人工确认；确认前不能开始实现或正式验收。

需求变化时发布新的完整 REQ 快照，而不是在旧事件上补丁式修改。若只是代码实现变化，不要伪装成新需求。

### 2. SPEC：定义如何证明

SPEC 与 REQ 分开确认，包含验收场景和矩阵：

- 场景用 `given / when / then` 描述业务结果如何被观察。
- 矩阵定义每个 CHK 的验证责任，以及对应的 AST、验证类型、依赖和证据要求。

首次建立或无法可靠表达变化时，发布完整 SPEC 快照；后续变化默认相对最近确认的 SPEC 发布增量。增量必须说明 `base_spec_ref` 及新增、修改、删除内容。场景和矩阵作为同一份 SPEC 一起确认。

### 3. IMPLEMENTATION：把定义落到提交

实现节点按以下顺序工作：

```text
自测前 AST 覆盖预检
  → 实现计划与切片
  → 编码和开发自测
  → 程序化完成复核
  → Agent 逐 AST 语义复核
  → 固定 Git commit
  → IMP-* READY
```

每个当前必需 AST 都必须被实现切片覆盖。实现计划记录生产引用、测试或明确豁免、readiness 和开发检查。完成前复核是实现内部质量门禁，不生成正式 RUN/ART。

### 4. ACCEPTANCE：用证据得出结论

正式验收必须有明确授权，并针对当前有效 REQ、SPEC 和指定实现 commit 执行。`dc-acceptance-verification` 先形成 RUN/ART，`dc-acceptance-closure` 再逐 AST、CHK 和场景审查；最后发布一条独立的 `ACC-*` 结论。

验收失败通常回到 IMPLEMENTATION；如果验收定义本身无法裁决，回到 SPEC 或 REQ。环境不可用时记录 `BLOCKED`，不能用测试退出码、旧证据或人工摘要伪造通过。

## 核心概念与证明链

```text
REQ
└── SCN
    └── CHK
        └── AST
            ├── RUN
            └── ART
```

| 概念 | 含义 | 作用 |
| --- | --- | --- |
| `REQ` | 业务需求的完整定义 | 说明为什么做、要产生什么业务结果 |
| `SCN` | 原子验收场景 | 用条件、动作和结果描述一个可独立裁决的业务结果 |
| `CHK` | 验证责任 | 说明谁以什么验证类型证明哪些场景结果 |
| `AST` | 可执行断言 | 把 Then 拆成可观察、可反驳的断言，是最小覆盖单位 |
| `RUN` | 一次实际验证执行事实 | 通过 `check_refs` 和 `assertion_refs` 指向本次验证目标 |
| `ART` | 可读取的证据 | 保存命令输出、接口交互、状态观察或截图等事实 |
| `IMP` | 一次实现完成事实 | 绑定实现计划、变更面、开发检查和完整 Git commit |
| `ACC` | 一次验收结论事实 | 绑定 REQ、SPEC、IMP、RUN/ART 和逐 AST 结果 |

一条正式证明关系是：`REQ → SCN → CHK → AST → RUN → ART`。只有当前必需阻断 CHK 的全部 AST 都由有效的 `PASSED` RUN 覆盖，CHK 才能通过；只有所有必要场景成立，验收才可能是 `SATISFIED`。

### 状态的区别

- `DRAFT`：定义尚未确认，不能进入下游门禁。
- `CONFIRMED`：负责人已确认当前 REQ 或 SPEC，可进入实现或后续节点。
- `READY`：实现切片、自测、复核和 Git commit 已完成，具备交给验收角色验证的条件。
- `PASSED`：某次 RUN 或某条断言的验证结果通过，不等于整个需求通过。
- `SATISFIED`：正式验收证据覆盖当前定义并得出的最终满足结论。
- `NOT_SATISFIED`：已有可裁决的失败证据。
- `BLOCKED`：环境、权限或必要前置事实缺失，当前无法完成验证。
- `INCOMPLETE`：证据或覆盖范围不足，不能作出完整结论。

特别注意：`READY ≠ SATISFIED`。开发测试通过只说明开发检查满足其目标，不代替正式验收的 RUN/ART。

### 完整快照与增量

REQ 始终发布当时的完整内容。SPEC 首次建立或需要重建基线时发布完整快照；在已有确认基线上的小范围调整，发布带 `base_spec_ref` 的增量。模型按 Issue 时间线把增量应用到最近有效基线，不能只看最后一条评论，也不能把增量文件独立当成完整规格。

## 谁是事实来源

| 材料 | 权威职责 | 不应替代什么 |
| --- | --- | --- |
| Issue 评论时间线 | 保存跨轮协作历史、确认、授权和已发布事件的顺序 | 不能用本地缓存替代读取门禁命中时的完整 intake；未刷新时也不能声称已检查最新评论 |
| 结构化 YAML 事件附件 | 保存 REQ、SPEC、IMP、ACC 的机器可解析交付事实 | 不能在 README 里另维护一套字段 Schema |
| 本地 `docs/交付证明/<REQ-ID>/` | 保存当前 REQ、场景、矩阵、实现计划、测试证据和验收材料，便于本地工作 | 不能把本地文件描述成线上协作事实 |
| 技能目录中的 `contracts/`、`templates/`、`references/`、`scripts/` | 保存各技能的字段、流程、模板和工具规范 | 不能被根 README 的简化说明覆盖 |
| Git commit | 固定一次实现实际对应的代码和文件版本 | 不能用当前未提交工作区代表已交付实现 |
| RUN/ART | 保存本次验收的实际观察和可复核证据 | 不能用测试名、退出码或一句“全部通过”替代 |

事件发布通常由脚本根据结构化 YAML 生成人类摘要和机器附件。README 只解释关系；详细字段、校验规则和发布要求请以 [事件契约](skills/dc-context-loop/references/event-contract.md) 与 [事件 Schema](skills/dc-context-loop/contracts/event.schema.yaml) 为准。

## 常见门禁与处理方式

| 情况 | 正确处理 |
| --- | --- |
| 没有唯一 Issue 标识 | 先补充或确认 URL、UUID 或 Issue Key；不能猜仓库或 Issue |
| Issue 评论或附件读取不完整 | 停在 intake，补齐读取；不要基于旧缓存继续路由 |
| REQ 未确认 | 停在 REQ，补充业务目标、范围、约束并请求人工确认 |
| SPEC 未确认或场景/矩阵不完整 | 停在 SPEC；场景和矩阵一起确认，不直接编码 |
| 实现过程中发现业务边界变了 | 返回 REQ 或 SPEC；不要把业务变化写成代码修复 |
| 缺少验收授权 | 实现可以发布 `IMP-* READY` 后停止；等待明确的验收指令 |
| 验收定义无法裁决 | 停止当前验收，回到 SPEC 或 REQ 澄清；不能自行放宽断言 |
| 验收失败 | 保留本次 RUN/ART，按证据回到 IMPLEMENTATION 修复；必要时产生新的 IMP |
| 环境、权限或外部系统阻塞 | 记录 `BLOCKED` 及受影响范围；不能用 Stub、旧结果或人工判断冒充真实证据 |
| 事件、附件或证据不完整 | 发布或收口前停止，补齐结构化材料和可定位证据 |
| 测试通过但没有完整验收覆盖 | 仍不能判定 `SATISFIED`；继续正式验收并覆盖所有必需 AST |

自举规则同样适用于本仓库自身：修改技能、Schema、模板、脚本、测试、文档或协作规则，也必须绑定 Issue 并经过同样的 Context Loop。具体边界见 [AGENTS.md](AGENTS.md)。

## 资源导航

先看：

- [项目协作与自举规则](AGENTS.md)
- [总协调器技能](skills/dc-context-loop/SKILL.md)
- [Issue Intake](skills/dc-issue-intake/SKILL.md)
- [需求切分](skills/dc-requirement-slicing/SKILL.md)
- [验收设计](skills/dc-acceptance-design/SKILL.md)
- [实现执行](skills/dc-implementation-execution/SKILL.md)
- [验收验证](skills/dc-acceptance-verification/SKILL.md)
- [验收收口](skills/dc-acceptance-closure/SKILL.md)

需要查规则时：

- [术语表](skills/dc-context-loop/references/glossary.md)：对象层级、状态和证据关系。
- [流程契约](skills/dc-context-loop/references/workflow-contract.md)：节点门禁、循环和 RUN/ART 规则。
- [事件契约](skills/dc-context-loop/references/event-contract.md)：事件发布、快照/增量和结构化附件。
- [实现计划模板](skills/dc-implementation-execution/templates/实现计划.md)：本地实现执行契约。
- [实现规划参考](skills/dc-implementation-execution/references/implementation-planning.md)：上下文盘点、切片和完成前复核。

需要运行工具时：

- `dc-context-loop/scripts/prepare_event.py`：校验并生成结构化事件评论和附件。
- `dc-context-loop/scripts/render_req_draft.py`：从统一 REQ 事件生成独立、人类可读的 Markdown 需求草案。
- `dc-context-loop/scripts/review_implementation.py`：执行实现覆盖预检和 READY 前程序化复核。
- `dc-context-loop/scripts/validate_delivery_proof.py`：校验本地交付证明。
- `dc-context-loop/scripts/render_delivery_review.py`：渲染或检查交付证明视图。

在本仓库源码中，脚本目录是：

```text
skills/dc-context-loop/scripts/
```

安装后则从 `<host-skills-root>/dc-context-loop/scripts/` 定位，不应写死某个宿主目录。

使用脚本前，先阅读对应技能说明和 `--help`；临时材料应放入由 `operation_workspace.py` 创建的操作工作区，不能把系统临时目录或项目根目录当作交付证据目录。
