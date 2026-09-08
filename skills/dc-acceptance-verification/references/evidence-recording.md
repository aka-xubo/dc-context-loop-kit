# Evidence Recording Contract

测试执行事实只写入当前 REQ 根目录的 `测试证据.md`，不回填已确认矩阵。

## 验收代码提交

一次测试证据只绑定一个完整 Git commit。顶层 `git_commit` 是本轮所有 RUN 的共同代码基线，RUN 不再重复保存代码版本。

目标提交变化时，当前 RUN/ART 不得继续参与验收。重新填写 `git_commit`，清空当前轮次证据，并在新提交上重新执行全部必需阻断 CHK。旧轮次由 Git 历史追溯，不混入当前文件。

## RUN

每次正式验证追加一个 RUN：

```yaml
test_evidence:
  requirement_ref: {requirement_id: REQ-001}
  git_commit: 0123456789abcdef0123456789abcdef01234567
  definition_digests: {requirement: "...", scenarios: "...", matrix: "..."}
  runs:
    - id: RUN-001
      check_refs: [CHK-001]
      assertion_refs: [AST-001]
      supporting_run_refs: []
      execution_type: unit
      purpose: feature_verification
      scope: focused
      command: go test ./internal/project -run TestCreateProject -count=1 -v
      environment: local-test
      started_at: "2026-08-04T09:00:00+09:00"
      exit_code: 0
      result: PASSED
      external_verification: null
      failure_reason: null
      artifact_refs: [ART-001]
      definition_digests: {requirement: "...", scenarios: "...", matrix: "..."}
```

执行类型 `execution_type`：`unit | api | ui | e2e | app_start | cleanup`。

测试目的 `purpose`：`feature_verification | regression | test_data_management`。

覆盖范围 `scope`：`focused | module | impacted | full`。

允许 result：`PASSED | FAILED | BLOCKED`。

- `git_commit` 使用完整的 40 位或 64 位小写十六进制 Git commit ID；存在 RUN 时不能为空。
- `check_refs`、`assertion_refs`、`supporting_run_refs` 和 `artifact_refs` 始终是列表。
- 正式 RUN 必须同时填写 `check_refs` 与 `assertion_refs`；`assertion_refs` 明确声明本次 RUN 实际尝试验证的 AST。
- `check_refs: []` 且 `assertion_refs: []` 才是 REQ 级辅助 RUN。辅助 RUN 不归属 CHK、不产生 AST 覆盖，也不能继续引用其他辅助 RUN。
- 正式 RUN 可以用 `supporting_run_refs` 引用必要的辅助 RUN；被引用的辅助 RUN 必须在同一提交上 `PASSED`、有 ART、定义摘要有效。
- environment、started_at 和 command 非空。
- external_verification 始终存在；非外部 RUN 为 null。
- TDD RED/GREEN 只属于实现过程，不写入正式测试证据。
- RUN 必须同时填写 `execution_type`、`purpose` 和 `scope`；三者正交组合，旧 `phase` 字段会被拒绝。
- 实现完成并提交后的聚焦单元验证可记录为 `execution_type: unit`、`purpose: feature_verification`、`scope: focused`；跨功能范围的回归可记录为 `purpose: regression` 并按实际入口和范围填写其余两个字段。
- PASSED RUN 的退出码为 0。
- CHK 只有在其全部 AST 都被有效 PASSED 正式 RUN 覆盖时才算通过；构建、类型检查、全量回归、清理等辅助 RUN 不得为了参与验收而虚构 CHK/AST 归属。
- 有效 PASSED 正式 RUN 的每个 `assertion_refs` 都必须在其 `artifact_refs` 指向的 ART 中出现一条 AST 级 `assertion_results`，包含非空 `expected`、`observed`、`status: PASSED` 和 `evidence_locator`；仅在 RUN 中声明 `assertion_refs` 不构成证据覆盖。
- 矩阵中 `assertion_type: predicate` 的 AST 还必须在 `evaluation.observations` 提供 predicate 所引用的所有事实值。validator 重算 predicate；结果为真才可写 `PASSED`，为假必须写 `FAILED`。语义 AST 不要求 `evaluation`。
- CHK 可以声明 `evidence_requirements.required_artifact_types`。RUN 只有同时覆盖 AST 并提供这些类型的 ART 时，才能用于该 CHK；涉及视觉状态的 CHK 可要求 `screenshot`。
- 当前证据只保留当前证明所需的 RUN/ART。未解决的 FAILED/BLOCKED RUN 可以保留以说明当前阻断；后续 RUN 已完整覆盖其所有 CHK/AST 后，旧 RUN 及不再引用的 ART 必须从当前文件移除，历史通过 Git 追溯。
- 禁止在 RUN 内增加 `code_revision`、`git_commit` 或其他逐 RUN 版本字段。

## 外部验证

`external_verification` 只记录 CHK 已声明的外部边界验证。`provider` 使用稳定的小写标识，可取 `feishu`、`wecom`、`alipay` 等任意外部系统；模式固定为 `stub | contract | real_test_app` 且必须与 CHK 精确一致。普通内部行为 RUN 即使使用 Stub，也记录 `external_verification: null`。

- stub 提供 `stub_ref`。
- contract 提供 `contract_ref`。
- real_test_app 提供 endpoint_host 和至少一个 ART；非 BLOCKED RUN 还提供脱敏 app_fingerprint。
- 缺少真实环境记录 BLOCKED，不得降级或伪造 fingerprint。
- 不保存 Token、Secret、授权码或完整个人身份数据。

## ART

ART 的 `type` 只描述证据内容，只允许以下四种值：

- `command_output`：命令的退出码、stdout、stderr 和测试明细。
- `api_exchange`：真实 API 请求与响应，包括目标、脱敏输入、状态码和输出。
- `state_observation`：数据库、缓存、消息、文件或运行日志中的实际系统状态。
- `screenshot`：用户可见的视觉事实，并附带视口、路由、采集时间和脱敏状态。

一个 ART 只有一种类型，一条 RUN 可以关联多个 ART。`unit`、`api`、`ui` 或 `e2e` CHK 不要求同名 ART；例如，API RUN 可以同时用 `api_exchange` 证明接口响应，并用 `state_observation` 证明数据库副作用。完整旅程按实际证据组合已有类型，不创建 `e2e` 专用 ART 类型。

```yaml
artifacts:
  - id: ART-001
    type: command_output
    location: docs/交付证明/REQ-001/artifacts/RUN-001.txt
    assertion_results:
      - assertion_id: AST-001
        expected: 聚焦测试全部通过
        observed: 命令退出码为 0，输出显示 3 个测试通过
        status: PASSED
        evidence_locator: line:12

  - id: ART-003
    type: state_observation
    location: docs/交付证明/REQ-001/artifacts/member-count.txt
    assertion_results:
      - assertion_id: AST-003
        expected: 新增成员后成员数等于原成员数加一
        observed: 原成员数为 2，新增后成员数为 3
        status: PASSED
        evidence_locator: observed:3
        evaluation:
          observations:
            input.member_count: 2
            result.member_count: 3

  - id: ART-002
    type: screenshot
    location: docs/交付证明/REQ-001/artifacts/RUN-001.png
    assertion_results:
      - assertion_id: AST-002
        expected: 移动端登录入口可见且无横向溢出
        observed: 390x844 视口中入口可见，页面宽度未溢出
        status: PASSED
        evidence_locator: screenshot
    capture:
      viewport: 390x844
      route: /login
      captured_at: "2026-08-04T09:05:00+09:00"
      redacted: true
```

文本 ART 的 `evidence_locator` 使用 `line:<正整数>`；`output:<正整数>`、`request:<正整数>`、`response:<正整数>` 和 `observed:<正整数>` 也按对应文本行定位。截图 ART 使用 `screenshot`。定位指向的行必须存在，且原始附件必须保存足以审阅该行的执行输出、交互或状态查询结果。

ART 文件必须存在且可读取，内容必须符合其类型并能定位 `observed` 的依据。一个“结果：PASS”汇总不能同时证明多条 AST。清理命令使用 `command_output`，清理后的状态使用 `state_observation`。敏感信息必须脱敏。代码引用不属于 ART，写入 `实现计划.md`。

测试与生产代码引用写入 `实现计划.md`；RUN/ART 写入 `测试证据.md`；证据充分性和最终裁决写入 `验收报告.md`。

## 场景裁决

`scenario_results` 只记录已经被全部阻断 CHK 证明的场景，每条记录固定为 `status: PASS`，并包含非空 `reason` 和至少一个 `run_refs`。未通过的报告可以使用空数组；工作台直接从当前 CHK/RUN/ART 派生“待验证、未通过、已阻塞或 PASS”。
