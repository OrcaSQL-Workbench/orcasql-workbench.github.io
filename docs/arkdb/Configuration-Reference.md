# 配置参考

本页列出连接和查询选项的字段、默认值与限制。示例见[连接配置与 TLS](Connections.md)、[预处理与高级执行](Advanced-Execution.md)和[有界流式读取](Streaming.md)。

本页内容：[ConnectionConfig](#connectionconfig)、[MySqlSessionOptions](#mysqlsessionoptions)、[SslConfig](#sslconfig)、[QueryOptions](#queryoptions)、[高级执行选项](#高级执行选项)。

## ConnectionConfig

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `host` | `string` | 空字符串 | 必填；验证 TLS 身份时应匹配服务器证书 |
| `port` | `number` | `3306` | 1 到 65535 的整数 |
| `user` | `string` | 空字符串 | 必填 |
| `defaultSchema` | `string`，可选 | 未设置 | 认证时选中的默认数据库 |
| `ssl` | `SslConfig` | 新的 `SslConfig` | TLS 策略与证书设置 |
| `session` | `MySqlSessionOptions`，可选 | 未设置 | 连接和重置后应用的时区、SQL mode |
| `multipleStatements` | `boolean` | `false` | 明确启用完全可信的文本多语句 |
| `preparedCacheSize` | `number`，可选 | 未设置 | `0..256`；0/未设置关闭私有预处理缓存 |
| `connectTimeoutMs` | `number` | `10000` | 正整数，单位毫秒；覆盖打开连接的总时间 |
| `autocommit` | `boolean` | `true` | 请求的初始自动提交状态 |

密码不在配置中，单独传给 `createConnection(config, password)` 或 `MySqlConnectionOptions`。

主机、端口、默认数据库、账号、CA 路径和密码的传入方式见[完整连接示例](Connections.md#定义连接信息并调用)。从 UI 收集设置时，可参考 [Worker 请求字段及映射](Worker-Integration.md#连接检查的请求与响应示例)。

| 方法 | 返回 | 作用 |
| --- | --- | --- |
| `validate()` | `ArkDbError[]` | 检查配置，不打开连接 |
| `validateIssues()` | `ConnectionValidationIssue[]` | 在错误之外提供字段定位 |
| `clone()` | `ConnectionConfig` | 复制配置，嵌套 TLS 配置也独立复制 |

`ConnectionValidationIssue` 包含 `field`、`error` 和可选 `invalidValue`。`ConnectionConfigField` 包括 `Host`、`Port`、`User`、`ConnectTimeoutMs`、`ClientCredentials`、`TlsVersions`、`Session`、`SessionTimeZone`、`SessionSqlMode`、`MultipleStatements` 和 `PreparedCacheSize`。

客户端字符集固定为 `utf8mb4`。SQL mode 通过 `session.sqlMode` 设置。

## MySqlSessionOptions

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `timeZone` | 未设置 | 连接和重置后请求的 MySQL 会话时区；由服务器验证 |
| `sqlMode` | 未设置 | 连接和重置后请求的 SQL mode；空字符串表示显式清空 |

已设置的字段必须是有效字符串。值会按原样发送给服务器，不会自动去除空格、规范化 SQL mode 或校正时区名。初始化在 `connect()` 完成前执行，并计入连接超时。`clone()` 会复制会话选项。

## SslConfig

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `mode` | `SslMode` | `PREFERRED` | TLS 策略 |
| `caCertPath` | `string`，可选 | 未设置 | CA PEM 路径；未设置时使用平台信任策略 |
| `clientCertPath` | `string`，可选 | 未设置 | 客户端证书，与私钥成对设置 |
| `clientKeyPath` | `string`，可选 | 未设置 | 客户端私钥 |
| `tlsVersions` | `string[]`，可选 | 未设置 | 可选值 `TLSv1.2`、`TLSv1.3` |
| `cipherSuites` | `string`，可选 | 未设置 | 显式指定密码套件 |

`SslConfig.clone()` 返回独立副本。所有证书路径都必须能被运行中的 HarmonyOS 应用读取。

| 模式 | 策略 |
| --- | --- |
| `DISABLED` | 明文 TCP |
| `PREFERRED` | 服务器提供 TLS 时协商，否则允许明文；兼容性默认值 |
| `REQUIRED` | 要求加密，不提供验证模式的身份保证 |
| `VERIFY_CA` | 要求 TLS 并验证证书链 |
| `VERIFY_IDENTITY` | 验证证书链与主机名；新接入建议使用 |

## QueryOptions

| 字段 | 默认值 | 单位与限制 | 实际作用 |
| --- | --- | --- | --- |
| `maxRows` | `0` | 非负整数；0 不限行数 | 已加载的行数上限，其他预算仍生效 |
| `maxChunkRows` | `200` | 正整数，行 | 每次行块的行数上限 |
| `maxChunkBytes` | `262144` | 正整数，字节 | 每次行块的估算字节预算 |
| `maxResultBytes` | `33554432` | 正整数，字节 | 已解码结果的估算字节预算 |
| `maxResultSets` | `64` | 正整数，个 | 结果集数量上限 |
| `maxDrainBytes` | `33554432` | 正整数，字节 | 截断后为恢复协议同步而排空的字节预算 |
| `maxDrainTimeMs` | `5000` | 1 到 `60000` 的整数，毫秒 | 排空时间预算 |
| `statementTimeoutMs` | `0` | 0 到 `86400000` 的整数，毫秒 | 只校验数值；驱动不会启动语句取消计时器 |

`QueryOptions.clone()` 返回选项副本。数值不合法时，查询会报告 `Validation` 错误。

`MAX_QUERY_DRAIN_TIME_MS` 为 `60000`，`MAX_STATEMENT_TIMEOUT_MS` 为 `86400000`。字节预算按驱动估算，不等于应用总内存；估算辅助函数见[结果参考](Data-Types-and-Results.md#估算辅助函数)。

需要驱动拥有取消计时器时，使用 `mysqlFeatures.deadlines` 和 `MySqlDeadlineOptions`；`statementTimeoutMs` 仍不会启动计时器。详见[取消与超时](Cancellation-and-Timeouts.md)。

## 高级执行选项

| 类型 | 主要默认值 | 用途 |
| --- | --- | --- |
| `MySqlDeadlineOptions` | `timeoutMs = 0`、`cancellationGraceMs = 2000` | 文本或预处理执行的截止时间、取消和清理 |
| `MySqlCursorOptions` | `fetchRows = 200`、`maxBufferedBytes = 33554432` | 只读服务端游标批次和累计结果预算 |
| `MySqlBatchOptions` | `maxItems = 1000`、`maxBufferedBytes = 33554432` | 预处理批处理 |
| `MySqlInsertRowsOptions` | 继承 batch，并设 `maxPacketBytes = 16777216` | 受限多行 INSERT 分组 |
| `MySqlLongDataOptions` | `chunkBytes = 65536`、`maxTotalBytes = 67108864`、`uploadTimeoutMs = 30000` | 预处理长文本/二进制参数 |
| `MySqlTransactionOptions` | 默认隔离、`readOnly` 未设置、`consistentSnapshot = false` | 回调事务属性 |

这些类型都提供 `validate()` 和 `clone()`，但选项结构不同：

- `MySqlDeadlineOptions`、`MySqlBatchOptions`、`MySqlInsertRowsOptions` 和 `MySqlLongDataOptions` 通过 `queryOptions` 设置结果预算。
- `MySqlCursorOptions` 直接继承 `QueryOptions`，`maxRows`、`maxResultBytes` 等字段直接设置在游标选项上。
- `MySqlTransactionOptions` 只包含事务属性，没有 `queryOptions`。

各功能的用法见[预处理与高级执行](Advanced-Execution.md)、[事务](Transactions.md)和[取消与超时](Cancellation-and-Timeouts.md)。
