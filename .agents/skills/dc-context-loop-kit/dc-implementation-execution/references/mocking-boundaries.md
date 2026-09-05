# Mocking Boundaries

## 允许替换的边界

以下外部边界只有在已确认 CHK 明确要求 `external_verification` 且模式为 `stub` 或 `contract` 时允许替换；`real_test_app` 禁止替换：

- 第三方支付、短信、邮件和外部 API。
- 时间、随机数和其他非确定性来源。
- 文件系统等会造成不安全或不可重复副作用的外部边界。

## 不允许 Mock 的对象

- 当前被测业务服务或领域行为。
- 项目内部可真实运行的协作者。
- 为当前验收场景提供关键结论的核心路径。
- 接口测试中的 Repository 或真实持久化层。

边界替身必须保存请求和响应证据，但 Mock 调用次数不能替代最终业务结果断言。若 CHK 只验证内部业务行为，Stub 只是测试实现手段，矩阵应保持 `external_verification: null`。

## 外部验证字段与模式

`external_verification.provider` 是稳定的小写外部系统标识，不限定为飞书。企业微信、钉钉、支付宝等系统分别使用自己的 provider 值；不要为每个 provider 增加新的字段或分类。

`external_verification` 只出现在需要证明外部边界的 CHK/RUN 上；普通内部行为验证即使使用 Stub，也不填写该字段。

- `stub`：本地替身，只证明平台如何处理外部边界返回的业务结果。
- `contract`：依据官方协议、Schema 或固定样本验证适配器契约，但不连接真实外部系统。
- `real_test_app`：使用非生产测试应用连接官方服务地址执行真实请求。

三种模式精确匹配且互不替代。矩阵要求 `real_test_app` 时，`stub` 或 `contract` 只能作为补充证据，不能满足该检查。
