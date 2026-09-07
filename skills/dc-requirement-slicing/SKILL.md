---
name: dc-requirement-slicing
description: 判断输入是新增 REQ、修改当前定义，还是纯实现变化。
---

# Requirement Slicing

先读取全部当前 `REQ-*/需求.md`、来源材料和依赖关系。当前文件保存完整定义，Issue 评论时间线保存历史。

输出必须包含：`decision`、`target_requirement_id`、`reason`、`affected_scopes`。

判定顺序：

1. 先判断业务目标、业务结果、范围、约束或失败规则是否变化：
   - 形成独立验收、交付和回滚的业务结果：`NEW_REQUIREMENT`；
   - 同一业务责任的承诺发生变化：`REQUIREMENT_CHANGE`，重新整理并发布当前完整 REQ。
2. 业务承诺不变，但场景、参与者、条件、动作、结果、CHK、AST、验证责任或验证方式变化：`SPEC_CHANGE`，由 `dc-acceptance-design` 相对最新已确认 SPEC 整理并发布增量；仅在需要重建基线时发布完整 SPEC。
3. REQ 和 SPEC 都不变，只改变实现、测试或环境，且验收裁决不变：`IMPLEMENTATION_ONLY`，不改 REQ/SPEC。
4. 新输入可由当前 REQ 和 SPEC 完整推出，且没有实现变更：`NO_REQUIREMENT_CHANGE`。

`SPEC_CHANGE` 是验收定义变化，不要求删除或覆盖旧 SPEC 事件；已确认 SPEC 变化时默认发布新的增量，引用基础 SPEC 并只记录新增、修改、删除。只有业务承诺变化才发布 REQ。

“以前没明确、现在明确”本身不是新 REQ 或 SPEC_CHANGE 的充分理由；必须说明它是否改变了现有业务承诺或 SCN/CHK 的可观察裁决。

## 业务依赖

依赖描述当前 REQ 成立所需的业务前置事实，不按内部或外部分类型。每条依赖包含当前 REQ 内稳定的 `DEP-*` ID、完整 `description` 和可选 `related_requirement_id`。关联 REQ 只用于检索展示，可以不存在于当前工作区；不要读取或复制其场景、摘要、状态或验收结论，也不因其变化自动重开当前 REQ。

```yaml
dependencies:
  - id: DEP-PROJECT-001
    description: 项目操作人是当前登录账号所代表的用户
    related_requirement_id: REQ-USER-AUTH
```

没有业务依赖时使用 `dependencies: []`。不要为了复用代码、表、模块或服务接口而创建 DEP；这些属于实现计划或验证环境配置。

依赖描述属于当前 REQ 定义。新增、删除或改变依赖事实时，按当前 REQ 的语义变化处理；只改变可选关联 REQ 且依赖事实和验证责任不变时，不改变验收契约。

## 草案与发布

需求草案使用统一 REQ 模型，至少包含 `issue_no`、`title`、`statement`、`business_outcomes`、`scope`、`constraints`、`dependencies`、`open_questions` 和 `release_notes`。负责人确认后，REQ 事件必须复用相同业务字段，事件 `reason` 必须等于草案 `release_notes`；调用 `prepare_event.py` 时通过 `--requirement-file` 执行逐字段漂移校验。草案状态、确认信息以及事件 ID、时间、作者、附件地址等技术元数据不参与比较。
