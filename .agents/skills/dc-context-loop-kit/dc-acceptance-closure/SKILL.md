---
name: dc-acceptance-closure
description: 汇总当前定义对应的 RUN/ART 并裁决验收报告。
---

# Acceptance Closure

## 节点职责

本技能是 ACCEPTANCE 节点内部的裁决步骤。它不重新执行验证，也不发布独立的收口评论；它审查 `dc-acceptance-verification` 在本地形成的 RUN/ART，按 `targeted` 单次范围或 `full` 全量范围生成逐 AST 结果和最终结论，再把完整结果交回 `dc-context-loop`，由总协调器发布唯一一条 `ACCEPTANCE` 结论事件。`targeted` 只能裁决指定 IMP 的完整切片，`full` 才能裁决当前有效 SPEC 的全部必需、阻断 CHK/AST。

只接受当前唯一 `git_commit` 上、匹配当前 REQ、场景和矩阵摘要的当前 `PASSED` 正式 RUN/ART。根据正式 RUN 的 `assertion_refs` 汇总 AST 覆盖；其 `supporting_run_refs` 引用的辅助 RUN 也必须在当前提交上有效。任一必需阻断 CHK 存在未被有效 PASSED 正式 RUN 覆盖的 AST、失败或阻塞，报告为 `NOT_SATISFIED`。辅助 RUN 不产生 AST 覆盖，不得用 CHK 级 RUN 或辅助 RUN 推定全部 AST 已通过，也不得组合不同提交上的结果。

RUN 只有在所引 ART 中逐 AST 存在非空 `expected`、`observed`、`status: PASSED` 和可解析的 `evidence_locator` 时才产生覆盖；定位必须能在附件中找到实际依据。CHK 声明的 `evidence_requirements.required_artifact_types` 也必须满足。截图只证明视觉事实，不能替代 `api_exchange`、`state_observation` 或 `command_output` 证据。

对于 predicate AST，覆盖还要求 ART 的 `evaluation.observations` 能使矩阵 predicate 重算为真。ART 手写 `PASSED` 但事实值不满足 predicate 时，不产生 AST 覆盖。

验收者逐 AST 检查“预期、实际、定位内容”是否证明同一件事。测试名、退出码、汇总性“全部通过”或无关状态变化都不是直接观察；无法确认语义对应时，不将该 AST 计入 PASSED 覆盖。

最终 ACCEPTANCE 事件必须携带可渲染的 `traceability` 关系：每个 `SCN-*` 映射其 `CHK-*` 和 `AST-*`，每个 AST 结果保留 `expected`、`observed`、`status`、`artifact_refs`，并在可用时保留 `evidence_locator`。总协调器使用该关系生成结论先行的评论、Markdown 目录、章节锚点和附件链接；不得另行维护展示状态。

只有全部阻断 CHK 的 AST 都被当前有效证据覆盖时，SCN 才显示 `PASS`；当前失败显示“未通过”，当前阻塞显示“已阻塞”，其余显示“待验证”。这些状态由当前 CHK 证明结果派生，不读取报告中的手工状态。`scenario_results` 只保存已经成立的 `PASS` 裁决、非空 `reason` 和至少一个 `run_refs`；报告未满足时可以为空。

验收收口不保存测试路径、生产代码路径、执行状态，也不修改业务定义或回填矩阵。

每次验收报告都绑定本次使用的 REQ、SCN、CHK、目标 Git commit 和实现仓库定位；后续工作从最新评论中的当前定义和最新实现继续。验收前的仓库定位只确认路径与 commit 能读取正确实现内容，不承担业务验收职责。每条业务依赖由当前矩阵中引用其 `DEP-*` ID 的必需阻断 CHK 证明；不读取关联 REQ 的场景、摘要、验收或递归状态。

Deep Crew 结论只允许 `SATISFIED`、`NOT_SATISFIED`、`BLOCKED` 或 `INCOMPLETE`。本技能负责依据当前证据裁决 AST 和总体验收结论；返回结果必须包含当前 REQ/SPEC/IMPLEMENTATION 引用、唯一 Git commit、RUN、ART、逐 AST 的预期/实际/状态/证据引用，以及非空裁决原因。总协调器为每次本地验收创建新的 `ACC-*`，并根据本结论负责后续节点路由；不得更新旧验收结论。
