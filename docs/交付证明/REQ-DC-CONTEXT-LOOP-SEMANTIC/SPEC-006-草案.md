# SPEC-006 草案：交付版本防错、场景结构统一与验收仓库定位

## 路由判断

- Issue：HTW-1671（`7ae49575-945b-474c-baf7-3908c95ac006`）
- 当前需求：`REQ-DC-CONTEXT-LOOP-SEMANTIC`
- 需求变化判断：`SPEC_CHANGE`
- 基础规格：`SPEC-005`
- 原因：业务目标和范围不变，但实现交付的版本绑定、SPEC 草案的人类可读结构和独立验收的代码定位方式需要增加可观察约束。

## 本次新增的 3 个相互独立验收场景

本次不是一个包含三个步骤的场景，而是 3 个不存在相互业务关联、可以分别裁决的独立 SCN：

| SCN | 标题 | 独立裁决的业务结果 |
|---|---|---|
| `SCN-013` | 实现事件绑定真实 Git commit | 交付证明绑定真实、完整且与当前 HEAD 一致的代码版本 |
| `SCN-014` | SPEC 草案统一展示独立验收场景 | 负责人能逐一识别和审查每个独立 SCN，不被模糊并列说明误导 |
| `SCN-015` | 实现事件提供验收前代码仓库定位 | 验收 Agent 能根据路径和 commit 直接读取正确实现内容，不必全盘检索或提前执行业务验收 |

## 本次新增验收场景

### SCN-013 实现事件绑定真实 Git commit

**业务结果**：实现和验收能够使用可验证的真实代码版本，避免错误或不存在的 commit 进入交付证明。

| Given | When | Then | 交付面 |
|---|---|---|---|
| Agent 已完成代码实现并准备发布 IMPLEMENTATION 事件；本地实现仓库存在当前 HEAD commit；事件需要记录完整 Git commit | Agent 生成或校验 IMPLEMENTATION/ACCEPTANCE 事件 | `THEN-029` 事件中的 `git_commit` 是完整 40 位 SHA 且在目标 Git 仓库真实存在；`THEN-030` 与当前 HEAD 一致，不一致时拒绝；`THEN-031` 生成前检查没有未处理 tracked 修改 | skill |

### SCN-014 SPEC 草案统一展示独立验收场景

**业务结果**：负责人能够快速看出本次新增的每个独立验收场景，并分别审查其业务结果、条件、动作和结果。

| Given | When | Then | 交付面 |
|---|---|---|---|
| SPEC 草案包含多个互不关联的新验收场景；草案同时包含本次变更说明和人类可读表格 | 负责人打开本地 SPEC 草案进行审查 | `THEN-032` 明确说明新增数量并逐一列出 SCN ID/标题；`THEN-033` 每个 SCN 使用统一层级和结构；`THEN-034` 概览、详情、CHK/AST 表格和 YAML 不把独立 SCN 合并为模糊说明 | skill |

### SCN-015 实现事件提供验收前代码仓库定位

**业务结果**：验收 Agent 能够根据 IMPLEMENTATION 事件提供的仓库根目录或工作树路径和 Git commit，直接读取正确的实现内容，而不需要全盘检索或提前执行业务验收。

| Given | When | Then | 交付面 |
|---|---|---|---|
| IMPLEMENTATION 事件绑定本地 Git commit；验收 Agent 可能运行在独立工作树或线上 Agent 环境 | 验收 Agent 接收事件并准备定位代码 | `THEN-035` 记录本地仓库根目录或工作树路径；`THEN-036` 摘要展示代码路径、Git 根目录和 commit；`THEN-037` 使用路径和 commit 读取并核对正确实现内容，且不在此步骤执行业务验收 | skill |

## 检查责任

| CHK | 场景 | 类型 | 验证责任 | 必需 | 阻断 |
|---|---|---|---|---|---|
| `CHK-013` | `SCN-013` | unit | 使用真实和伪造 Git commit 事件验证存在性、当前 HEAD 一致性、完整 SHA 和工作区状态门禁。 | 是 | 是 |
| `CHK-014` | `SCN-014` | unit | 生成包含多个独立 SCN 的完整和增量 SPEC 草案，检查数量、统一标题层级、逐场景详情和跨表格/YAML 一致性。 | 是 | 是 |
| `CHK-015` | `SCN-015` | unit | 使用带仓库根目录或工作树路径和 Git commit 的 IMPLEMENTATION 事件，检查 Agent 能直接读取正确实现内容；不执行业务验收或降级全盘检索。 | 是 | 是 |

## 原子断言

| AST | CHK | 结果引用 | 类型 | 断言描述 |
|---|---|---|---|---|
| `AST-028` | `CHK-013` | `SCN-013.THEN-029` | semantic | 事件只接受完整且真实存在于目标 Git 仓库的 commit；格式正确但不存在的 SHA 被拒绝。 |
| `AST-029` | `CHK-013` | `SCN-013.THEN-030` | semantic | 事件 commit 与目标仓库当前 HEAD 不一致时，工具拒绝生成可发布评论。 |
| `AST-030` | `CHK-013` | `SCN-013.THEN-031` | semantic | 目标仓库存在未处理 tracked 修改时，流程拒绝固定交付版本或明确报告版本漂移。 |
| `AST-031` | `CHK-014` | `SCN-014.THEN-032` | semantic | 草案明确声明新增场景数量，并逐一列出每个独立 SCN 的 ID 和标题。 |
| `AST-032` | `CHK-014` | `SCN-014.THEN-033` | semantic | 每个新增 SCN 以相同标题层级和字段结构单独展示，不能合并成一段综合说明。 |
| `AST-033` | `CHK-014` | `SCN-014.THEN-034` | semantic | 概览、详细表格、CHK/AST 映射和 YAML 中的 SCN 数量、ID、标题及引用一致。 |
| `AST-034` | `CHK-015` | `SCN-015.THEN-035` | semantic | IMPLEMENTATION 事件包含本地仓库根目录或工作树路径，提供直接定位入口。 |
| `AST-035` | `CHK-015` | `SCN-015.THEN-036` | semantic | IMPLEMENTATION 评论同时展示代码路径、Git 根目录和绑定 commit。 |
| `AST-036` | `CHK-015` | `SCN-015.THEN-037` | semantic | 验收 Agent 使用事件提供的仓库路径和 Git commit 读取并核对正确实现内容；该定位步骤不执行业务验收。 |

## 本次增量摘要

| 操作 | SCN | CHK | AST |
|---|---|---|---|
| 新增 | `SCN-013`、`SCN-014`、`SCN-015` | `CHK-013`、`CHK-014`、`CHK-015` | `AST-028` 至 `AST-036` |
| 修改 | 无 | 无 | 无 |
| 删除 | 无 | 无 | 无 |

## 已确认的增量 SPEC

已于 2026-08-31 在 HTW-1671 Issue 评论中确认并发布，评论 ID：`6bce61a9-cba3-471a-8033-7972a589648b`。

```yaml
requirement_ref: REQ-DC-CONTEXT-LOOP-SEMANTIC
base_spec_ref: SPEC-005
changes:
  added:
    scenarios:
      - id: SCN-013
        title: 实现事件绑定真实 Git commit
        business_result: 实现和验收能够使用可验证的真实代码版本，避免错误或不存在的 commit 进入交付证明。
        given: [Agent 已完成代码实现并准备发布 IMPLEMENTATION 事件, 本地实现仓库存在当前 HEAD commit, 事件需要记录完整 Git commit]
        when: Agent 生成或校验 IMPLEMENTATION/ACCEPTANCE 事件
        then:
          - {id: THEN-029, statement: 事件中的 git_commit 是完整 40 位 SHA，并且在目标 Git 仓库中真实存在}
          - {id: THEN-030, statement: 事件中的 git_commit 与当前实现 HEAD 一致；不一致时事件工具拒绝生成或发布}
          - {id: THEN-031, statement: 事件生成前检查目标仓库没有未处理的 tracked 修改，避免代码版本与证明内容漂移}
        delivery_surfaces: [skill]
      - id: SCN-014
        title: SPEC 草案统一展示独立验收场景
        business_result: 负责人能够快速看出本次新增的每个独立验收场景，并分别审查其业务结果、条件、动作和结果。
        given: [SPEC 草案包含多个互不关联的新验收场景, 草案同时包含本次变更说明和人类可读表格]
        when: 负责人打开本地 SPEC 草案进行审查
        then:
          - {id: THEN-032, statement: 草案明确说明本次新增场景的数量，并逐一列出每个 SCN 的稳定 ID 和标题}
          - {id: THEN-033, statement: 每个新增 SCN 使用统一层级和统一结构展示 business_result、Given、When、Then 与交付面}
          - {id: THEN-034, statement: 场景概览、详细场景、CHK/AST 表格和 YAML 机器块之间不存在把多个独立 SCN 合并成模糊并列说明的表达}
        delivery_surfaces: [skill]
      - id: SCN-015
        title: 实现事件提供验收前代码仓库定位
        business_result: 验收 Agent 能够根据 IMPLEMENTATION 事件提供的仓库根目录或工作树路径和 Git commit，直接读取正确的实现内容，而不需要全盘检索或提前执行业务验收。
        given: [IMPLEMENTATION 事件绑定一个本地 Git commit, 验收 Agent 可能运行在独立工作树或线上 Agent 环境]
        when: 验收 Agent 接收 IMPLEMENTATION 事件并准备定位代码
        then:
          - {id: THEN-035, statement: IMPLEMENTATION 事件记录可直接访问的本地仓库根目录或工作树路径}
          - {id: THEN-036, statement: 实现评论的人类摘要展示代码路径、Git 根目录和绑定 commit}
          - {id: THEN-037, statement: 验收 Agent 使用事件路径和 Git commit 读取并核对正确的实现内容；该步骤只完成代码定位与版本核对，不执行业务验收}
        delivery_surfaces: [skill]
    checks:
      - {id: CHK-013, scenario_ids: [SCN-013], dependency_ids: [], verification_type: unit, responsibility: 使用真实和伪造 Git commit 事件验证存在性、当前 HEAD 一致性、完整 SHA 和工作区状态门禁。, required: true, blocking: true, evidence_requirements: {required_artifact_types: [command_output]}, external_verification: null}
      - {id: CHK-014, scenario_ids: [SCN-014], dependency_ids: [], verification_type: unit, responsibility: 生成包含多个独立 SCN 的完整和增量 SPEC 草案，检查数量、统一标题层级、逐场景详情和跨表格/YAML 一致性。, required: true, blocking: true, evidence_requirements: {required_artifact_types: [command_output]}, external_verification: null}
      - {id: CHK-015, scenario_ids: [SCN-015], dependency_ids: [], verification_type: unit, responsibility: 使用带仓库根目录或工作树路径和 Git commit 的 IMPLEMENTATION 事件，检查 Agent 能直接读取正确实现内容；不执行业务验收或降级全盘检索。, required: true, blocking: true, evidence_requirements: {required_artifact_types: [command_output]}, external_verification: null}
    assertions:
      - {id: AST-028, check_id: CHK-013, outcome_refs: [SCN-013.THEN-029], assertion_type: semantic, description: IMPLEMENTATION/ACCEPTANCE 事件只接受完整且真实存在于目标 Git 仓库的 commit；格式正确但不存在的 SHA 被拒绝。}
      - {id: AST-029, check_id: CHK-013, outcome_refs: [SCN-013.THEN-030], assertion_type: semantic, description: 事件 git_commit 与目标仓库当前 HEAD 不一致时，事件准备工具明确拒绝，不生成可发布评论。}
      - {id: AST-030, check_id: CHK-013, outcome_refs: [SCN-013.THEN-031], assertion_type: semantic, description: 目标仓库存在未处理 tracked 修改时，事件准备流程拒绝固定交付版本或明确报告版本漂移。}
      - {id: AST-031, check_id: CHK-014, outcome_refs: [SCN-014.THEN-032], assertion_type: semantic, description: SPEC 草案明确声明本次新增场景数量，并逐一列出每个独立 SCN 的稳定 ID 和标题。}
      - {id: AST-032, check_id: CHK-014, outcome_refs: [SCN-014.THEN-033], assertion_type: semantic, description: 每个新增 SCN 均以相同标题层级和字段结构单独展示，不能因场景无关联而合并为一段综合说明。}
      - {id: AST-033, check_id: CHK-014, outcome_refs: [SCN-014.THEN-034], assertion_type: semantic, description: 场景概览、详细表格、CHK/AST 映射和 YAML 机器块中的 SCN 数量、ID、标题及引用一致。}
      - {id: AST-034, check_id: CHK-015, outcome_refs: [SCN-015.THEN-035], assertion_type: semantic, description: IMPLEMENTATION 事件包含本地仓库根目录或工作树路径，验收 Agent 无需全盘搜索即可获得定位入口。}
      - {id: AST-035, check_id: CHK-015, outcome_refs: [SCN-015.THEN-036], assertion_type: semantic, description: IMPLEMENTATION 人类可读评论同时展示代码路径、Git 根目录和绑定 commit。}
      - {id: AST-036, check_id: CHK-015, outcome_refs: [SCN-015.THEN-037], assertion_type: semantic, description: 验收 Agent 使用事件提供的仓库路径和 Git commit 读取并核对正确实现内容；该定位步骤不执行业务验收。}
  modified: {scenarios: [], checks: [], assertions: []}
  removed: {scenarios: [], checks: [], assertions: []}
open_questions: []
```

## 后续节点

`SPEC-006` 已确认。下一责任节点为 IMPLEMENTATION；实现完成后应发布新的 `IMP-*` 事件。确认本身不代表实现完成或验收通过。
