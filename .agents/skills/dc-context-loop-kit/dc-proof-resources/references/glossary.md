# Delivery Proof Glossary

## 层级

```text
REQ（唯一顶层业务实体）
└── SCN（包含业务结果的原子验收场景）
    └── CHK（验证责任）
        └── AST（可执行断言）
            ├── RUN（一次执行事实）
            └── ART（可读取证据）
```

REQ、SCN、CHK 都保存当前完整定义。每个 SCN 的 `business_result` 定义一个必须成立且可独立裁决的业务结果；`given / when / then` 说明该结果在什么条件、动作下如何被观察。每条 Then 使用场景内稳定 ID，AST 通过 `outcome_refs` 显式映射这些结果。历史由 Issue 评论时间线提供，文件只承载当前内容。

正式 RUN 通过 `check_refs` 指明验证目标 CHK，通过 `assertion_refs` 指明本次实际尝试验证的 AST，并通过 `artifact_refs` 关联可读取证据。`check_refs` 与 `assertion_refs` 同时为空的 RUN 是 REQ 级辅助执行，不属于任何 CHK；正式 RUN 可通过 `supporting_run_refs` 引用它。有效 PASSED 正式 RUN 只覆盖它明确引用的 AST；CHK 的全部 AST 都被覆盖后，CHK 才算通过。

ART 不只是文件链接。ART 类型固定为 `command_output`、`api_exchange`、`state_observation` 和 `screenshot`；分别证明命令结果、接口交互、系统状态和视觉事实。一个 ART 只有一种类型，一条 RUN 可以关联多个 ART。用于验收覆盖的 ART 必须为每个相关 AST 保存 `assertion_results`，记录 `expected`、`observed`、`status` 和可定位的 `evidence_locator`。视觉类 CHK 可以在 `evidence_requirements.required_artifact_types` 中要求 `screenshot`；截图是视觉事实的补充证据，不替代接口、系统状态或命令输出证据。

## 状态

| 对象 | 状态 |
|---|---|
| REQ | `DRAFT / CONFIRMED / SATISFIED` |
| 完整 SPEC（场景集合 + 验收矩阵） | `DRAFT / CONFIRMED` |
| 实现计划 | `PLANNED / IN_PROGRESS / READY` |
| RUN | `PASSED / FAILED / BLOCKED` |
| 验收报告 | `SATISFIED / NOT_SATISFIED` |

`READY` 只表示实现具备验证条件；`SATISFIED` 只能由当前定义上的完整验收证据产生。

实现计划在制定前必须完成需求、场景、矩阵、项目规范、代码结构和运行前置条件的上下文盘点。影响业务行为、安全、数据兼容性、不可逆迁移或验收方式的未决问题必须先与人确认；计划为 `READY` 时不得遗留 `open_questions` 或 blocker。

## 持续循环

- 需求或验收定义调整时，发布新的完整 REQ 或 SPEC 内容；总协调器根据最新评论判断后续节点。
- 实现每次完成都发布独立的 `IMP-*`；验收每次执行都发布独立的 `ACC-*`。
- 纯实现变化不改变业务定义；新的实现交付在自己的 commit 上单独验证。
- 测试证据只描述本次验收动作，Issue 评论时间线保留各次动作的顺序。

## 摘要与依赖

REQ、场景、矩阵摘要只用于校验验收材料是否对应当前完整定义。

业务依赖记录当前 REQ 成立所需的前置事实。每条依赖拥有当前 REQ 内的 `DEP-*` ID、完整描述和可选关联 REQ；关联 REQ 只用于检索展示，不参与验收，也不要求存在于当前工作区。

验收矩阵中的 CHK 通过 `dependency_ids` 引用 DEP。每条 DEP 必须由至少一个必需阻断 CHK 在当前 REQ 的业务场景中直接证明。系统不读取或递归解析其他 REQ 的材料和状态。

项目级 `需求清单.md/html` 是从 REQ 目录生成的检索视图。
