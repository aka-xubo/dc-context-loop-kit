# Workflow Contract

## 证明链

```text
REQ → SCN → CHK → AST → 证明 RUN → ART → 验收报告
                         ↑
                      辅助 RUN
```

每次验收材料绑定本次使用的 REQ、场景和矩阵定义摘要，以及本次目标 `git_commit`。

SCN 使用 `given / when / then` 表达业务场景；Then 结果通过 `SCN-*.THEN-*` 被 AST 的 `outcome_refs` 引用。Gherkin 是人类可读的场景表达层，不改变 CHK、RUN、ART 的证明职责。

当前 REQ 的业务依赖使用局部 `DEP-*` ID 和完整描述；可选关联 REQ 只用于展示。矩阵中的必需阻断 CHK 通过 `dependency_ids` 直接证明这些依赖，验收不读取其他 REQ 的材料或状态。

## 文件结构

```text
docs/交付证明/
└── <REQ-ID>/
    ├── 需求.md
    ├── 验收场景.md
    ├── 验收矩阵.md
    ├── 实现计划.md
    ├── 测试证据.md
    ├── 验收报告.md
    ├── artifacts/
    └── 审核工作台.html
```

固定 YAML 数据块是机器真值源；HTML 和需求清单是只读派生视图。

当前本地交付证明采用 Issue 单一索引：完整 intake 且 ACC 结论落地后，索引保存为
`docs/交付证明/<ISSUE-KEY>.md`，只记录编号、event_id、评论 UUID、评论地址、计数和同步元数据，不进入 Git，也不复制事件、规格或证据正文。SPEC/IMP 发布期间不刷新最终索引；索引刷新前必须确认 intake `coverage: FULL`，并精确比较事件集合。

索引同步时，调用方必须显式传入同一 Issue 的旧阶段路径（`--legacy-path`）。工具只允许将
`docs/交付证明` 下的明确路径移入被 Git 忽略的 `.local/dc-loop/archive/<ISSUE-KEY>/`，不得静默删除、覆盖或移动根目录之外的文件；检查模式发现指定旧路径仍存在即失败。

所有自测、完成前复核和验收临时材料都必须位于目标 IMPLEMENTATION 事件
`repository.worktree_root/.local/dc-loop/tmp/<operation-id>/`。操作目录由
`dc-context-loop/scripts/operation_workspace.py` 创建，不能使用验收 Agent 当前目录或项目根目录之外的系统临时目录。每个终态都要清理并验证；清理失败阻止完成声明，但不删除 Issue 评论、附件或本地索引。

凡会创建临时文件的测试或脚本，都必须由 `operation_workspace.py exec` 启动；该入口负责注入
`TMPDIR`、`TMP`、`TEMP`、`PYTHONPYCACHEPREFIX` 和 `DC_LOOP_OPERATION_WORKSPACE`，直接运行测试入口不得作为有效证据。

## 需求处理

收到新信息时判断它属于 REQ、SPEC、IMPLEMENTATION 或 ACCEPTANCE，并发布对应的当前内容或完成事实。只有形成独立业务结果时才新建 REQ。

## 状态推进

```text
REQ DRAFT → CONFIRMED → 覆盖预检 → 编码与自测 → 完成前复核 → 实现计划 READY → 验证 → SATISFIED
             ↑              ↑              ↑
          新需求快照      新实现交付       新验收动作
```

实现计划只有在自测前覆盖预检、自测后程序化完成复核和 Agent 语义完成复核均通过后才能 READY。随后 `dc-implementation-execution` 发布一个新的 `IMP-*` 完成交付事实并将控制权交回 `dc-context-loop`。总协调器检查定义、commit 和门禁，再等待用户明确的验收指令；只有获得授权，才调用 `dc-acceptance-verification`。不能把 READY 自动解释为验收通过，也不能在没有授权时连续发布验收事件。

场景和矩阵作为一份完整 SPEC 一起生成，并在一次人工确认后同时进入 `CONFIRMED`；确认前不可进入实现或验证。SPEC 事件 YAML 先通过 Schema 校验，再由 `render_spec_draft.py` 生成单独、完整的 SPEC 草案 Markdown；草案、场景文件、矩阵文件和正式事件必须使用同一份 SPEC 数据，确认前标准文件保持 `DRAFT`。`READY` 只代表实现完成，不代表已验收。

Issue intake 按关键动作触发，而不是每轮固定触发：首次处理、REQ/SPEC/实现方案设计前、正式验收前和用户显式刷新时各自独立完整读取；验收失败后重新进入对应设计或实现方案动作时再次读取。普通交互、节点内部澄清和事件发布前校验复用当前上下文；发布前只做内容展示、引用、Schema、附件、重复 ID 和 Git 校验，发布后不自动重读 Issue。

## RUN、ART 与裁决

正式验收过程在本地完成：`dc-acceptance-verification` 形成 RUN/ART，随后 `dc-acceptance-closure` 审查并裁决。中间过程不发布 Issue 启动或进度评论；收口后由 `dc-context-loop` 发布唯一一条 `ACCEPTANCE` 结论事件。

`测试证据.md` 只描述本次验收动作，并在顶层保存本次使用的完整 `git_commit`。RUN 不保存逐条代码版本；每次新的实现交付都单独产生本次验收材料。

有效验收 RUN 必须是 `PASSED`、有 ART，并匹配当前三个定义摘要。正式 RUN 同时使用 `check_refs` 和 `assertion_refs` 明确目标；两者都为空的 RUN 是 REQ 级辅助执行，只能被正式 RUN 通过 `supporting_run_refs` 引用。只有必需阻断 CHK 的全部 AST 都被有效 PASSED 正式 RUN 覆盖，该 CHK 才算通过。TDD RED/GREEN 是实现过程，不属于正式验收证据；完成实现并提交后，聚焦单元验证使用 `unit_verification`。

验收报告的 `scenario_results` 只保存已经成立的场景裁决：

```yaml
scenario_results:
  - scenario_ref: SCN-001
    status: PASS
    reason: 面向审查者的裁决摘要
    run_refs: [RUN-001]
```

只有当前必需阻断 CHK 的全部 AST 都被有效证据覆盖时，SCN 才显示 `PASS`；当前失败显示“未通过”，当前阻塞显示“已阻塞”，其余显示“待验证”。这些展示结果由工作台直接派生，不能通过手工填写报告绕过 CHK/AST 覆盖。已保存裁决的 `reason` 始终必填且不能为空；`SATISFIED` 报告必须为全部 SCN 保存 `PASS` 裁决，`NOT_SATISFIED` 报告允许 `scenario_results: []`。

派生视图：

```bash
python3 <kit-dir>/dc-proof-resources/scripts/render_delivery_review.py docs/交付证明
python3 <kit-dir>/dc-proof-resources/scripts/render_delivery_review.py --check docs/交付证明
```
