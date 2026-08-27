---
name: dc-acceptance-design
description: 为一个已确认 REQ 设计包含验收场景、验证责任和断言的完整 SPEC，并通过一次人工确认同时确认场景与矩阵。用户要求“生成验收场景”“设计怎么验收”“生成验收矩阵”“修改已确认验收设计”时使用。
---

# Acceptance Design

## 目标

```text
CONFIRMED REQ → 完整 SPEC（场景 + 矩阵）DRAFT → 一次人工确认 → 完整 SPEC CONFIRMED
```

开始前完整读取 workflow contract、glossary、两个 Schema 和对应模板。

## 场景阶段

准入：目标 REQ 的 `需求.md` 状态为 `CONFIRMED`，且路径与 `requirement.id` 一致。场景文件保存于：

```text
docs/交付证明/<REQ-ID>/验收场景.md
```

每个新建或重新设计的 SCN 包含一个 `business_result`，并用 Gherkin 结构保存 `given`、`when`、`then`。`given` 是业务前置条件，`when` 是单一用户或系统动作，`then` 是带稳定 `THEN-*` ID 的可观察结果列表。`business_result` 直接定义该场景必须成立的可观察业务结果，一个场景只表达一个可独立裁决结论。Gherkin 只作为 SCN 表达层，不生成 Feature/Rule 等新的交付实体，也不取代 CHK、AST、RUN 或 ART。

- 每个 SCN 必须有非空且可独立裁决的 `business_result`。
- `given`、`when`、`then` 必须同时存在；每条 Then 使用场景内唯一的 `THEN-*` ID。
- 业务结果不能只描述实现技术、内部模块、表结构、代码路径或测试方式。
- Web/API/CLI/Skill 等声明的交付面必须有可观察场景。
- 无法从来源推出的规则进入 `open_questions`。
- 每次需要调整时重新生成一份当前完整场景集合；Issue 评论时间线保存各次完整发布。

场景和矩阵必须作为同一份完整 SPEC 一起生成。用户明确确认完整 SPEC 后，同时将场景文件和矩阵文件置为 `CONFIRMED`；确认事实由 Issue 中的 SPEC 事件保存，本地文件不要求复制确认人或确认时间。不得先单独确认场景再单独确认矩阵，也不得自行确认。

## 矩阵内容

准入：目标 REQ 的 `需求.md` 状态为 `CONFIRMED`。矩阵文件与场景文件共同组成完整 SPEC，保存于：

```text
docs/交付证明/<REQ-ID>/验收矩阵.md
```

每个 CHK 只承担一个验证责任，引用一个或多个 SCN，并包含 `dependency_ids`、稳定 AST 断言、验证类型、是否必需/阻断和必要的验证环境配置。每个 AST 使用 `outcome_refs` 引用一个或多个 `SCN-*.THEN-*`；引用必须属于该 CHK 的 `scenario_ids`，且每条 Then 至少由一个 AST 覆盖。业务交付面只定义在 SCN 的 `delivery_surfaces`；CHK 不重复保存交付面。

每个 AST 必须能够由验收者直接观察和反驳，不能只写结论性口号。对于“请求被拒绝”“未建立上下文”“业务动作未执行”这类复合结论，拆为独立 AST，并分别说明响应、上下文或 handler 探针、目标业务状态等观察对象。读取型认证端点的 401 不能代替受保护写操作未执行的证明。

AST 默认使用 `assertion_type: semantic` 和自然语言 `description`。当规则能由稳定的事实值确定性裁决时，使用 `assertion_type: predicate`：在 `predicate` 中以受限表达式树定义 `left operator right`，并在 ART 的 `evaluation.observations` 保存对应事实值。支持 `eq`、比较、集合包含和加减乘除/计数；不使用任意代码、SQL 或字符串表达式。`ontology_refs` 可引用已确认的业务对象、属性、动作或约束，帮助解释事实含义；本体不保存该 AST 的验收公式。

例如“新增成员后人数增加 1”可定义为 `result.member_count eq input.member_count + 1`。验收者仍需提供原始 ART 与可定位依据；validator 根据 observations 重算 predicate，不能仅手写 `PASSED`。难以量化的业务语言、错误提示和视觉质量继续使用语义 AST，不强行公式化。

CHK 可用 `evidence_requirements.required_artifact_types` 声明证明所需的 ART 类型，只允许 `command_output`、`api_exchange`、`state_observation` 和 `screenshot`。只有视觉事实确实属于 AST 时才要求 `screenshot`；接口值、系统状态和命令结果仍需相应的结构化证据，截图不能替代这些证据。未要求特定类型时使用空数组或省略该字段。

矩阵只确认“怎么证明”：

- 保存 CHK、AST、场景引用、验证类型和验证环境配置；交付面从所引用 SCN 读取。
- 不保存测试路径、生产代码路径、执行状态、证据审查或最终裁决。
- 这些执行事实分别属于实现计划、测试证据和验收报告。

执行归属固定为：正式 RUN 同时填写 `check_refs` 与 `assertion_refs`；构建、类型检查、全量回归、清理等不直接证明 AST 的执行填写空的 `check_refs`/`assertion_refs`，作为 REQ 级辅助 RUN。正式 RUN 可用 `supporting_run_refs` 引用辅助 RUN，但辅助 RUN 不属于任何 CHK，也不产生 AST 覆盖。

### CHK 验证类型

`verification_type` 只描述正式 RUN 的主要执行入口，不描述测试框架、交付面或 ART 的观察位置。只允许以下四种类型：

- `unit`：直接执行隔离的代码单元，验证局部业务规则；外部边界可受控，但不能代替公开交付入口验证。
- `api`：从一个真实公开 API 操作进入，验证响应及其业务副作用。
- `ui`：从浏览器或客户端界面进入，验证界面自身的展示、状态和交互行为。
- `e2e`：从真实用户或系统入口进入，经过完整业务旅程所需的交互和系统边界，验证最终业务结果。

选择类型时遵守：

- 验证由多个交互或系统边界组成、不能归结为单个 API 或 UI 契约的完整旅程时，使用 `e2e`；完整 OAuth 旅程必须使用 `e2e`。
- 其余 CHK 按验证责任实际进入系统的位置选择 `unit`、`api` 或 `ui`，不按 Vitest、Playwright、curl 等执行工具选择。
- 一个 CHK 只使用一个验证类型；包含多个独立验证责任时拆分 CHK。
- API 或 UI 行为产生的数据库记录、缓存、消息、文件和日志属于 AST 的预期结果及 ART 的实际证据，不单独形成验证类型。
- `web` 是 SCN 的交付面，不是验证类型。截图是 ART 类型，不是验证类型。

例如，调用添加用户 API 后查询数据库确认用户记录存在，CHK 类型仍为 `api`；API 请求、响应和数据库查询结果共同组成覆盖相应 AST 的 ART。

只要 AST 声明业务副作用或业务动作未执行，CHK 的 `evidence_requirements.required_artifact_types` 必须包含 `api_exchange` 和 `state_observation`。

## 依赖证明

读取当前 REQ 的全部 `dependencies`。每个 CHK 的 `dependency_ids` 始终存在，无关联时为 `[]`；每条 DEP 必须至少由一个 `required: true`、`blocking: true` 的 CHK 在当前 REQ 业务场景中直接证明。CHK 验证当前实现正确满足并使用依赖事实，不验证关联 REQ 是否存在或是否验收。

业务依赖不按内部或外部分类型。`external_verification` 只描述“本条 CHK 是否必须证明外部系统边界”，不是业务依赖，也不是测试实现记录。需要证明外部系统、适配器契约或真实外部旅程时，记录稳定的小写 `provider` 标识和用户明确选择的 `stub | contract | real_test_app` 模式；provider 可以是 `feishu`、`wecom`、`alipay` 等任意外部系统，不为某个平台创建专用字段。

如果 CHK 只验证平台收到一个已准备好的身份、响应或错误后，内部业务行为是否正确，则 `external_verification: null`。测试中可以使用 Stub，但那只是 RUN/ART 的实现手段，不应把 Stub 使用误写成外部系统已被验证。一个 CHK 原则上只声明一个 provider；确实需要多个外部系统共同成立时拆分 CHK，分别证明各自边界。

`real_test_app` 必须覆盖从真实用户/系统入口到最终业务结果的完整旅程。OAuth 至少审查授权入口、回调、token exchange、identity fetch、本地持久化和平台凭证交付；不能从人工准备的中间状态开始。

## 后续调整

- REQ 业务边界需要调整：先回 `dc-requirement-slicing`。
- 参与者、条件、动作、结果或业务不变量需要调整：重新生成并一次确认当前完整 SPEC。
- 验证责任、AST 或验证环境模式需要调整：重新生成并一次确认当前完整 SPEC。
- 测试文件、命令、环境或实现路径调整：在当前定义下执行本次验收并记录 RUN。

用户明确确认完整 SPEC 后，同时为场景和矩阵写入 `CONFIRMED`；确认事件保存在 Issue，不要求本地文档填写确认人或确认时间。

## 输出

每次写入需求、场景或矩阵后，立即执行项目级校验并重生成本地审核页；随后用 `render_delivery_review.py --check` 确认派生视图与真值一致。同步失败时不得进入下一门禁。报告目标 REQ、当前场景/矩阵状态、SCN 与 CHK 覆盖、验证环境模式、未决问题和下一人工门禁。
