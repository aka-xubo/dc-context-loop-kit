[DP:SPEC] SPEC-001 当前验收规格

## 关联需求

REQ-DELIVERY-PROOF-REQ-CONSISTENCY

## 发布说明

根据已确认 REQ 设计完整验收场景、检查责任和可观察断言，等待负责人一次性确认场景与矩阵

## 验收场景

| SCN | 标题 | 业务结果 | Given | When | Then | 交付面 |
|---|---|---|---|---|---|---|
| `SCN-001` | 交付证明不再维护 Issue 级本地索引 | 交付证明目录不再生成、刷新或依赖按 Issue No 命名的独立本地索引文件 | 当前工作区包含 docs/交付证明 及多个 REQ 目录；项目交付证明刷新与校验入口可被执行 | 执行项目交付证明的标准刷新与一致性校验流程 | THEN-001 流程不会生成或刷新 docs/交付证明/<ISSUE-KEY>.md 形式的 Issue 级本地索引；THEN-002 交付证明的标准生成与校验路径不再包含 Issue 级索引的生成、归档或一致性检查入口 | 本地交付证明目录, 交付证明生成与校验脚本 |
| `SCN-002` | 需求清单直接显示 REQ 关联的 Issue No | 审核者可以从需求清单直接确认每个 REQ 关联的 Issue No | 每个当前 REQ 都通过结构化 issue_no 字段声明一个唯一且格式合法的 Issue No；项目中存在多个 REQ 目录 | 生成项目级需求清单.md | THEN-003 需求清单包含 Issue No 列；THEN-004 每个 REQ 行展示与其结构化定义一致的 Issue No，并链接到该 REQ 的审核工作台；THEN-005 Issue No 缺失、格式非法或同一 REQ 存在歧义关联时，项目校验失败并指出对应 REQ | docs/交付证明/需求清单.md, REQ 需求定义文件 |
| `SCN-003` | REQ 草案与正式 REQ comment 保持一致 | 负责人确认的 REQ 草案与发布到 Issue 的正式 REQ comment 表达同一份需求内容 | 存在一份结构化 REQ 草案和待发布 REQ 事件；事件由统一的 REQ 渲染与校验入口生成 | 对草案和正式 comment 的规范化内容执行一致性校验 | THEN-006 标题、需求陈述、业务结果、范围、约束、依赖、Issue 关联、未决事项和发布说明在草案与正式 comment 中逐项一致；THEN-007 只有状态和明确声明的发布技术元数据可以不同，业务内容差异不能被忽略或覆盖；THEN-008 草案与正式 comment 的业务内容发生漂移时，发布前校验失败并定位差异字段 | REQ 草案文件, Issue REQ comment, REQ 事件校验与渲染入口 |
| `SCN-004` | 删除项目级 HTML 后仍可审查各 REQ | 删除项目级需求清单 HTML 后，审核者仍可通过 Markdown 清单和各 REQ 审核工作台完成需求审查 | 当前工作区包含需求清单和多个 REQ 目录；交付证明派生视图生成流程可被执行 | 生成交付证明派生视图 | THEN-009 流程不生成 docs/交付证明/需求清单.html，且任何工作台不再依赖该文件；THEN-010 流程仍生成内容完整且可校验的 docs/交付证明/需求清单.md；THEN-011 每个 REQ 目录下的审核工作台.html 仍可生成并链接到该 REQ 的需求、场景、矩阵和证据材料 | docs/交付证明/需求清单.md, docs/交付证明/<REQ-ID>/审核工作台.html |

## 检查责任

| CHK | 场景 | 类型 | 责任 | 必需 | 阻断 |
|---|---|---|---|---|---|
| `CHK-001` | SCN-001 | unit | 检查交付证明生成与校验代码不再创建或维护 Issue 级本地索引 | 是 | 是 |
| `CHK-002` | SCN-002 | unit | 检查 REQ 的 Issue No 关联字段、格式校验和需求清单渲染 | 是 | 是 |
| `CHK-003` | SCN-003 | unit | 检查 REQ 草案、事件 YAML 和正式 comment 的规范化内容一致性及漂移阻断 | 是 | 是 |
| `CHK-004` | SCN-004 | unit | 检查项目级 HTML 清单移除后的派生视图输出和 REQ 审核工作台保留 | 是 | 是 |

## 原子断言

| AST | CHK | 结果引用 | 类型 | 描述 |
|---|---|---|---|---|
| `AST-001` | CHK-001 | SCN-001.THEN-001 | semantic | 标准交付证明刷新流程执行后不存在新生成或被更新的 docs/交付证明/<ISSUE-KEY>.md 文件 |
| `AST-002` | CHK-001 | SCN-001.THEN-002 | semantic | 生成器、校验器、模板和文档中不再存在 Issue 级索引的生成、归档或一致性检查入口 |
| `AST-003` | CHK-002 | SCN-002.THEN-003 | semantic | 生成的需求清单 Markdown 表头包含 Issue No 列 |
| `AST-004` | CHK-002 | SCN-002.THEN-004 | semantic | 需求清单每一行的 Issue No 与对应 REQ 结构化定义完全一致，并保留审核工作台链接 |
| `AST-005` | CHK-002 | SCN-002.THEN-005 | semantic | Issue No 缺失、格式非法或关联不唯一的 REQ 会使项目校验失败，并在输出中定位 REQ 标识 |
| `AST-006` | CHK-003 | SCN-003.THEN-006 | semantic | REQ 草案与正式 comment 的标题、需求陈述、业务结果、范围、约束、依赖、Issue 关联、未决事项和发布说明逐项相等 |
| `AST-007` | CHK-003 | SCN-003.THEN-007 | semantic | 一致性比较只允许状态和显式声明的发布技术元数据不同，不能把业务字段差异归类为元数据 |
| `AST-008` | CHK-003 | SCN-003.THEN-008 | semantic | 任一业务字段漂移都会在发布前被确定性校验拒绝，并报告字段路径或差异位置 |
| `AST-009` | CHK-004 | SCN-004.THEN-009 | semantic | 派生视图生成后不存在需求清单.html，且仓库内不再有指向该文件的工作台或模板链接 |
| `AST-010` | CHK-004 | SCN-004.THEN-010 | semantic | 派生视图生成后需求清单.md 存在、内容可读且通过项目级校验 |
| `AST-011` | CHK-004 | SCN-004.THEN-011 | semantic | 每个 REQ 目录下的审核工作台.html 仍然存在或可重新生成，并能链接到该 REQ 的需求、场景、矩阵和证据材料 |

## 未决事项

- 无

## 机器事件附件

- event_id：`EVT-HTW-1739-SPEC-001`
- YAML 附件：`SPEC-001-事件.yaml`
- 解析方式：从 Issue comment 附件下载并解析该 YAML；评论正文不内嵌机器 YAML。