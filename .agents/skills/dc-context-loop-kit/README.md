# Deep Crew Context Loop Kit

这是一个可复制、可独立分发的 Deep Crew 上下文循环技能包。包内技能全部使用 `dc-` 前缀。

## 入口

- `dc-context-loop`：在首次处理、REQ/SPEC/实现方案设计前、正式验收前或用户显式刷新时读取 Issue 完整评论时间线，结合本地材料和用户最新消息，由模型总结上下文、判断需求变化并协调循环；普通交互和事件发布前校验复用当前上下文。

## 节点技能

- `dc-grilling`：当前对话中的按需澄清。
- `dc-requirement-slicing`：需求归类与切片。
- `dc-acceptance-design`：SCN、CHK、AST 验收规格设计。
- `dc-implementation-execution`：本地实现与开发检查。
- `dc-acceptance-verification`：本地 RUN/ART 验证。
- `dc-acceptance-closure`：本地证据审查与验收结论。
- `dc-issue-intake`：读取实时 Issue、全部评论和必要附件。

## 共享资源

交付证明资源按调用关系归属到 `dc-context-loop` 协调层或对应节点技能：各技能目录内的 `contracts/`、`templates/`、`references/` 和 `scripts/` 是唯一规范来源。复制整个 `dc-context-loop-kit` 时保持目录结构不变，节点技能中的相对引用即可继续工作。

## 使用方式

Issue 评论时间线保存协作历史；本地文件保存当前完整定义和本次验收材料。需要平台发布动作时，按当前环境提供的 Issue CLI 和权限执行。
