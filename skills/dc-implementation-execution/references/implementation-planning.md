# 实现计划制定

## 目标

实现计划是把已确认业务定义翻译成工程执行步骤的本地契约。它回答四个问题：

1. 当前代码和项目上下文是什么；
2. 哪些工程切片会实现哪些 CHK/AST；
3. 每个切片如何测试，哪些情况有明确豁免；
4. 应用何时具备交给验收角色执行 RUN/ART 的条件。

它不重新定义需求，不替代验收矩阵，也不产生新的业务状态。实现计划默认不需要人工审批；只有包含高风险实现决策时，才触发条件式人工门禁。

实现计划还必须保存完成前复核结果。复核发生在开发自测之后、固定 commit 和发布 `READY` 之前；自测前另有一次只检查计划覆盖的预检。程序复核负责确定性结构和 Git 事实，Agent 复核负责逐 AST 语义判断，两者均通过后才能发布 `IMP-*`。

当前计划必须用 `spec_ref` 明确绑定一份当前有效且已确认的完整 SPEC。确认了新 SPEC 后，不创建计划历史链：直接把 `实现计划.md` 更新到新的 `spec_ref`，恢复 `PLANNED`，重新规划受影响切片，并把旧预检、程序复核、语义复核及 reviewed assertions 全部重置为 `PENDING` 或空值。已有代码能否复用由新切片判断，但新计划必须重新覆盖当前矩阵的全部必需 AST。

## 上下文盘点

在创建第一个实现切片前，读取并记录：

- `需求.md`、`验收场景.md` 和 `验收矩阵.md`；
- `AGENTS.md`、README、构建/依赖清单和项目规范；
- 相关代码目录、入口、测试、配置、迁移、启动脚本和外部适配器；
- 本地运行、测试和真实外部旅程所需的环境前置条件。

`context_review.findings` 不写泛泛的“已阅读”，而写与计划有关的事实：

```yaml
- area: architecture
  observation: Go API 负责认证和持久化，Next.js 通过同源 /v1 代理访问 API。
  impact: 认证切片必须同时包含 API 中间件和 Web 代理就绪工作。
```

路径是审计索引，不是 ART；计划不能用“看过文件”替代正式验收证据。

## 人类可读视图

`实现计划.md` 的 YAML 机器块是唯一计划数据。每次创建或更新机器块后，用当前验收矩阵生成同文件的 Markdown 视图：

```bash
python3 <kit-dir>/dc-context-loop/scripts/render_implementation_plan.py \
  --plan-file docs/交付证明/<REQ-ID>/实现计划.md \
  --matrix-file docs/交付证明/<REQ-ID>/验收矩阵.md \
  --output-file docs/交付证明/<REQ-ID>/实现计划.md

python3 <kit-dir>/dc-context-loop/scripts/render_implementation_plan.py \
  --plan-file docs/交付证明/<REQ-ID>/实现计划.md \
  --matrix-file docs/交付证明/<REQ-ID>/验收矩阵.md \
  --check
```

视图结论先行展示状态、REQ、SPEC、目标、阻塞和完成复核，再按执行顺序展开切片，并从矩阵补充 AST 自然语言。`--check` 重新生成完整内容并逐字比较；计划机器块、矩阵或人类章节任一变化导致漂移时都失败。

计划处于 `PLANNED` 且旧复核已重置后，用当前完整 SPEC 事件执行覆盖预检：

```bash
python3 <kit-dir>/dc-context-loop/scripts/review_implementation.py \
  --phase preflight \
  --plan-file docs/交付证明/<REQ-ID>/实现计划.md \
  --matrix-file docs/交付证明/<REQ-ID>/验收矩阵.md \
  --spec-file <operation-workspace>/current-spec.yaml \
  --report-file <operation-workspace>/preflight.txt
```

预检通过后才把计划和切片推进到执行状态。`current-spec.yaml` 必须是总协调器提供并合并完成的当前完整 SPEC，不能直接使用未合并的增量事件。

## 交互判断

先尝试从当前仓库和已确认材料推导事实。

| 情况 | 处理 |
| --- | --- |
| 目录、函数拆分、测试命令等已有模式可确定 | 直接采用，记录 `repository` 或 `existing_pattern` 决策 |
| 多种工程方案都不改变外部行为 | 优先沿用项目模式；高风险时询问并记录 `human` 决策 |
| 会改变业务结果、边界、失败行为或验收观察面 | 停止受影响切片，返回需求或验收设计流程 |
| 会影响安全策略、数据兼容性、不可逆迁移、公开 API 或回滚 | 在本地 `human_gate` 声明风险类别，先询问负责人，未回答前保持 `PLANNED` |
| 只是环境暂时不可用 | 记录真实 blocker，不改写业务定义或伪造 READY |

提问应聚焦一个可决策问题，说明已知事实、候选方案、影响切片和不回答的后果。回答后把问题从 `open_questions` 移到 `decisions`，保留原问题、答案、来源和影响范围；同时将 `human_gate.status` 设为 `CONFIRMED` 并记录确认人、时间和决策引用。

## 切片设计

优先按业务行为做垂直切片，不按“先写所有模型、再写所有接口”做分层计划：

- `behavior_slice`：一个可观察行为或紧密的一组行为，必须关联其 CHK/AST；
- `engineering_slice`：迁移、依赖注入、配置、路由装配等前置工程工作，可没有 AST；
- `readiness_slice`：启动、入口、测试应用、数据和外部系统准备，可没有 AST。

每个切片要有明确 `objective`，列出生产代码和测试引用，写明依赖的其他切片。所有 AST 至少映射到一个切片；不确定归属时先解决计划问题，不要留空。

## 测试策略

顶层 `test_strategy.default` 默认为 `tdd`。不能按测试难度豁免。每条豁免都要写 `id`、`kind`、受影响 `assertion_refs`、具体理由和替代检查。TDD 的 RED/GREEN/REFACTOR 属于实现过程，不写入 `测试证据.md`。

## 状态和交付

`PLANNED`、`IN_PROGRESS`、`BLOCKED` 和切片状态只用于本地执行计划。`READY` 表示所有实现和应用前置条件完成、无 blocker、定义未变化且已固定完整 Git commit。

### 完成前复核记录

`implementation_plan.completion_review` 至少包含：

- `status: PASSED`；
- `performed_after_self_test: true`；
- `preflight.status: PASSED`，表示自测前覆盖预检已通过；
- `program.status: PASSED`、执行命令和报告定位；
- `semantic.status: PASSED`、逐 AST reviewed 结果、实现/测试定位和语义疑点。

程序检查不能从文件存在推断业务行为；Agent 不能用测试名称、退出码或“全部通过”代替逐 AST 语义判断。失败时记录原因并保持计划非 READY。

实现计划保存在本地，编码、调试、开发测试和阻塞过程不写入 Issue。`READY` 和完整 commit 成立后，节点协调器发布一个新的 `IMP-*` 完成交付事实，再把控制权交回 `dc-context-loop`，由总协调器决定是否进入正式验收。
