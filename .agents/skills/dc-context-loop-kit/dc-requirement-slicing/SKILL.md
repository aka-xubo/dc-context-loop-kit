---
name: dc-requirement-slicing
description: 判断输入是新增 REQ、修改当前定义，还是纯实现变化。
---

# Requirement Slicing

先读取全部当前 `REQ-*/需求.md`、来源材料和依赖关系。当前文件保存完整定义，Issue 评论时间线保存历史。

输出必须包含：`decision`、`target_requirement_id`、`reason`、`affected_scopes`。

判定顺序：

1. 只改变实现、测试或环境，且验收裁决不变：`IMPLEMENTATION_ONLY`，不改 REQ/SCN/CHK。
2. 新输入可由当前验收契约推出：`NO_REQUIREMENT_CHANGE`。
3. 改变现有 DRAFT 的同一业务责任：重新整理并发布一份当前完整 REQ。
4. 改变已确认或已验收 REQ/SCN/CHK 的语义：重新整理并发布一份当前完整 REQ；由总协调器根据最新时间线决定后续 SPEC 和验收动作。
5. 只有形成独立验收、交付和回滚的业务结果：`NEW_REQUIREMENT`。

“以前没明确、现在明确”本身不是新 REQ 或新定义的充分理由；必须说明它是否改变了现有 SCN/CHK 的可观察裁决。

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
