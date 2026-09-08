---
name: dc-acceptance-verification
description: 在实现计划 READY 后，由验收角色执行当前 CHK 的真实验证并记录可复核 RUN/ART。
---

# Acceptance Verification

## 节点职责

本技能是 ACCEPTANCE 节点内部的事实采集步骤。它在本地执行真实验证，生成 RUN、ART 和逐 AST 实际观察；不发布验收启动、进度或单独的验证评论，也不形成最终验收结论。验收入口先确定模式：指定 `IMP-*` 时为 `targeted` 单次验收，范围为该 IMP 的 `spec_refs` 展开的完整 CHK/AST；未指定 IMP 时为 `full` 全量验收，范围为当前有效 SPEC 的全部必需、阻断 CHK/AST。完成后把本地验收材料交给 `dc-acceptance-closure`。

入口要求：目标 REQ、场景和矩阵均为 `CONFIRMED`，实现计划为 `READY`，绑定唯一完整 `git_commit` 和 IMPLEMENTATION 事件提供的 `repository.worktree_root`/`git_toplevel`，并且已收到用户明确的验收指令。开始业务验收前，先依据实现事件的仓库路径和 commit 读取正确实现内容；这一步只做代码定位与版本核对，不替代任何 CHK/AST 验证，也不进行全盘仓库检索。IMPLEMENTATION READY 事件不是自动进入本技能的触发器；“继续”“可以”“来吧”等泛化指令不构成验收授权。验收者不修改生产实现或验收定义；发现定义无法裁决时停止执行，退回 `dc-acceptance-design`。

验收操作的临时根目录只能是目标 IMPLEMENTATION 事件的
`repository.worktree_root/.local/dc-loop/tmp/<operation-id>/`。验收 Agent 必须使用
`dc-context-loop/scripts/operation_workspace.py` 创建唯一目录，将验收脚本、测试脚本副本、矩阵副本、原始输出、缓存和临时工作树全部放入其中；不能根据自己的当前目录推断路径，也不能使用其外部的系统临时目录。无论验收成功、失败、阻塞还是中止，都必须在终态调用 `cleanup --terminal-status SUCCESS|FAILED|BLOCKED|INTERRUPTED` 并验证清理完成；清理失败时只能报告清理错误，不能形成完成声明。已发布的 Issue 评论、附件和单一本地交付证明索引不在清理范围内。

验收脚本和回归测试必须通过 `operation_workspace.py exec` 启动；直接运行含有临时文件逻辑的测试入口或依赖系统默认 `tempfile` 目录的命令视为无效执行。验收产出的原始输出、RUN/ART 草稿和缓存只能保存在该 operation workspace。

## 线上证据发布协议

验收证据的持久化顺序固定为“生成原始证据 → 上传 Issue 评论/附件 → 线上读取确认 → 生成最终 ACCEPTANCE 事件 → cleanup”。验收者不得把本地路径、测试退出码或人工摘要当作线上证据定位。

上传时必须将以下材料作为同一验收操作的一部分提交到当前 Issue：

- 原始命令输出、请求响应、状态观察或视觉证据文件；
- 包含 RUN、ART 和逐 AST 结果的结构化验收材料；
- 最终 ACCEPTANCE 评论及其机器 YAML 附件。

上传每个材料后，必须通过 Issue API/CLI 下载或读取并比对内容，记录线上评论 ID、附件 ID、文件名和可访问定位。任一上传或读取失败都必须停止收口，报告 `BLOCKED` 或 `INCOMPLETE`，不得继续 cleanup，也不得生成 `SATISFIED`。

线上读取确认完成后，才允许执行：

```bash
python3 <kit-dir>/dc-context-loop/scripts/operation_workspace.py cleanup \\
  --worktree-root <repository.worktree_root> \\
  --operation-id <operation-id> \\
  --terminal-status SUCCESS
```

cleanup 只删除本地临时材料，不删除或覆盖 Issue 评论、附件和历史事件。若 cleanup 失败，验收结果只能报告清理阻塞，不能宣称验收操作完成。

每个正式 RUN 同时填写 `check_refs` 和 `assertion_refs`。每个 `PASSED` AST 必须在关联 ART 中保存非空 `expected`、`observed`、`status: PASSED` 和可解析、可定位的 `evidence_locator`。先保存原始命令输出、请求响应或状态查询结果，再填写 ART 摘要；不得以“全部通过”、测试名或截图代替逐 AST 实际观察。

每个 RUN 还必须同时填写三个正交字段：`execution_type`（`unit | api | ui | e2e | app_start | cleanup`）、`purpose`（`feature_verification | regression | test_data_management`）和 `scope`（`focused | module | impacted | full`）。旧 `phase` 不再接受，也不从命令或摘要推断回填。`purpose: regression` 只说明执行目的；除非该 RUN 通过 `check_refs`、`assertion_refs` 和 ART 提供直接观察，否则不能产生 AST 覆盖。

对 `assertion_type: predicate` 的 AST，ART 还必须保存 `evaluation.observations`，键名与矩阵 predicate 的 `fact` 一致。由 validator 重算结果：计算为真只能记 `PASSED`，计算为假只能记 `FAILED`；无法获得事实值则记录 `BLOCKED` 或退回验收设计。`expected`、`observed` 和 `evidence_locator` 仍然必须填写，便于人复核事实来源。

按观察对象选择 ART：

- 接口请求和响应使用 `api_exchange`。
- 数据库、缓存、消息、文件、日志或 handler 执行探针的状态使用 `state_observation`。
- 命令执行明细使用 `command_output`。
- 用户可见视觉事实使用 `screenshot`；它不能替代接口或状态证据。

API CHK 中，“请求被拒绝”“未建立当前用户上下文”“受保护业务动作未执行”是三个独立观察：分别记录响应、handler/context 探针，以及目标业务状态。只请求读取型 `/me` 端点或仅比较无关用户数量，不能证明业务写动作未执行。涉及副作用的 API CHK 应在矩阵中要求 `api_exchange` 和 `state_observation`。

外部边界必须精确匹配 CHK 的 `external_verification`；`real_test_app` 缺少可用环境时记录 `BLOCKED`，不得用 stub 降级。无法为某个 AST 形成直接观察时，该 AST 不得记为 `PASSED`。

所有本地验证完成或出现无法继续的真实阻塞后，停止新增 RUN/ART，调用 `dc-acceptance-closure` 审查当前材料。验证技能负责采集事实，不负责把失败归因到实现或定义；Issue 时间线只在 closure 完成后由总协调器发布一条最终 `ACCEPTANCE` 事件。
