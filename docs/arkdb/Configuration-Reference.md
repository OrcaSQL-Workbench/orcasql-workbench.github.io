# 配置参考

下面列出 MySQL 1.0.2 的字段、默认值和实际作用。示例用法见[连接与 TLS](Connections.md)及[流式读取](Streaming.md)，版本来源见[兼容性与升级](Compatibility-and-Upgrading.md)。

本页内容：[ConnectionConfig](#connectionconfig)、[SslConfig](#sslconfig)、[QueryOptions](#queryoptions)。

## ConnectionConfig

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `host` | `string` | 空字符串 | 必填；验证 TLS 身份时应匹配服务器证书 |
| `port` | `number` | `3306` | 1 到 65535 的安全整数 |
| `user` | `string` | 空字符串 | 必填 |
| `defaultSchema` | `string`，可选 | 未设置 | 认证时选中的默认数据库 |
| `ssl` | `SslConfig` | 新的 `SslConfig` | TLS 策略与证书设置 |
| `connectTimeoutMs` | `number` | `10000` | 正安全整数，单位毫秒；覆盖打开连接的总截止时间 |
| `autocommit` | `boolean` | `true` | 请求的初始自动提交状态 |

密码不在配置中，单独传给 `createConnection(config, password)` 或 `MySqlConnectionOptions`。

| 方法 | 返回 | 作用 |
| --- | --- | --- |
| `validate()` | `ArkDbError[]` | 检查配置，不打开连接 |
| `validateIssues()` | `ConnectionValidationIssue[]` | 在错误之外提供字段定位 |
| `clone()` | `ConnectionConfig` | 复制配置，嵌套 TLS 配置也独立复制 |

`ConnectionValidationIssue` 包含 `field`、`error` 和可选 `invalidValue`。`ConnectionConfigField` 包括 `Host`、`Port`、`User`、`ConnectTimeoutMs`、`ClientCredentials`、`TlsVersions`。

客户端使用 `utf8mb4`。公共配置不提供字符集、压缩、SQL mode、连接属性、引擎标签或未来选项袋，不要添加看似可用但会被忽略的字段。

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

需要取消执行时，按[取消与超时](Cancellation-and-Timeouts.md)安排计时器和原操作的收尾，不要依赖这个选项名称推断已发生取消。
