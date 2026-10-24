# 公共接口与错误处理

这页按 MySQL 1.0.2 的公共入口整理。所有导入都来自 `@arkdb/mysql`，不从包内目录导入，也不要求消费应用导入 `@arkdb/core`。

按需查阅：[工厂与连接](#工厂与连接)、[可选能力](#可选能力)、[元数据与服务器指标](#元数据与服务器指标)、[类型化错误](#类型化错误)、[日志](#日志)、[其他导出](#其他导出)。版本来源见[兼容性与升级](Compatibility-and-Upgrading.md)。

## 工厂与连接

普通 MySQL 应用可以继续使用非泛型的 `DbDriverFactory` 和带完整 MySQL 方法的 `DbConnection`：

| 工厂方法或属性 | 用途 |
| --- | --- |
| `createConnection(config: ConnectionConfig, password: string): DbConnection` | 创建连接，不自动连接 |
| `createMetadataProvider(connection): MetadataProvider` | 借用连接读取元数据 |
| `createExecutionController(controlConnection): DbExecutionController` | 使用调用方管理的控制连接取消查询 |
| `createServerMetricsProvider(connection): ServerMetricsProvider` | 借用连接读取 MySQL 指标 |
| `driverId`、`capabilities` | 驱动标识与能力信息 |

`MySqlDriverFactory` 是具体实现；它的 `createConnection` 返回 `MySqlConnection`，Provider 创建方法返回对应的具体 MySQL 类。也可以使用 `createMySqlConnection(config, password)`。使用接口类型接收工厂时，按接口返回类型编写调用方。

| `DbConnection` 方法或属性 | 类型 |
| --- | --- |
| `connect()`、`ping()`、`close()` | `Promise<void>` |
| `query(sql: string)` | `Promise<QueryResult>` |
| `queryStream(sql: string, options: QueryOptions, sink: QueryResultSink)` | `Promise<QueryExecutionSummary>` |
| `changeContext(context: DatabaseContext)` | `Promise<void>` |
| `setAutocommit(enabled: boolean)`、`commit()`、`rollback()` | `Promise<DatabaseSessionStatus>` |
| `state` | 只读 `ConnectionState` |
| `serverInfo` | 只读 `ServerInfo` |
| `sessionStatus` | 只读 `DatabaseSessionStatus` |
| `features` | 可选的 `DbConnectionFeatures` |

同一连接的操作由调用方串行化。失败不代表可以安全重试；会话标记只在明确已知时使用。`ConnectionState` 包括 `Idle`、`Connecting`、`Authenticating`、`Ready`、`Querying`、`Closed` 和 `Error`。

配置与校验在[配置参考](Configuration-Reference.md)，值和返回字段在[数据类型与结果](Data-Types-and-Results.md)。

## 可选能力

可移植的 `CoreDbConnection` 只要求连接、查询、关闭、生命周期和服务器信息。扩展能力从 `features` 获取；没有对应接口就表示不支持，不能用一个成功的空操作代替。

| 成员 | 接口和主要操作 |
| --- | --- |
| `features.streaming` | `DbStreamingConnection.queryStream(sql, options, sink)` |
| `features.health` | `DbConnectionHealth.ping()` |
| `features.context` | `DbContextController.changeContext(context)` 和 `contextPolicy` |
| `features.transactions` | `DbTransactionController.begin()`、`commit()`、`rollback()` 和 `sessionStatus` |
| `features.cancellation` | `CoreDbExecutionController.cancel(): Promise<QueryCancellationResult>` |
| `features.metadata` | `CoreMetadataProvider`，含可支持的对象种类 |
| `features.metrics` | `readMetrics(): Promise<ServerMetricsSnapshot>` |

MySQL 句柄式 `DbExecutionController.cancel(connectionHandle: string)` 返回 `Promise<void>`；可移植取消接口不收句柄，绑定当前连接上的执行。两者都有 `isInterruptionError(error: ArkDbError): boolean`，但控制连接的所有权不同。完整用法见[取消与超时](Cancellation-and-Timeouts.md)。

写通用集成时，使用泛型 `CoreDbDriverFactory<TOptions, TConnection>.create(options)`。MySQL 的参数是 `MySqlConnectionOptions(config, password)`；`MySqlDriverFactory` 同时实现这条创建路径和原有的 `createConnection`。

`DbDriverRegistry.register(factory)` 保留类型并返回工厂句柄；`describe(driverId)` 返回 `DbDriverDescriptor`，`driverIds()` 列出已注册标识。重复注册会报错。发现一个标识不等于可以把任意配置对象交给它。

`DatabaseContext`、`DatabaseContextPolicy` 和 `ContextChangeMode` 描述上下文变更规则。不同驱动可以要求重连或拒绝某种变更，不需要模拟 MySQL 的 `USE`。

## 元数据与服务器指标

方法签名、结果模型和示例集中在[元数据与服务器指标](Metadata-and-Metrics.md)。

`MySqlMetadataProvider`、`MySqlExecutionController` 和 `MySqlServerMetricsProvider` 是具体实现，普通调用方优先通过工厂或连接能力取得它们。Provider 借用连接，不能与该连接上的其他操作并发执行。

`DriverCapabilities` 保留 MySQL 的能力信息，`CoreDriverCapabilities` 是通用类型。能力标记用于发现，不会让 SQL 跨引擎可移植，也不能替代实际接口是否存在的检查。

## 类型化错误

使用 `ArkDbError`、`ArkDbErrorKind` 和服务器错误码判断错误，不匹配英文消息。错误字段、分类和展示示例见[错误与日志](Errors-and-Logging.md)。

`code` 是兼容的可选数值字段；`nativeCode` 可以保留数值或文本标识，SQLSTATE 独立保存在 `sqlState`。

## 日志

`Logger`、`LogLevel`、`LogSink`、`LogTag` 和 `LOG_DOMAIN` 用于驱动日志，设置与脱敏要求见[日志说明](Errors-and-Logging.md#日志设置)。

## 其他导出

| 类别 | 查阅位置 |
| --- | --- |
| `ConnectionConfig`、`SslConfig`、`SslMode`、`ConnectionConfigField`、`ConnectionValidationIssue`、`QueryOptions` 和时间上限 | [配置参考](Configuration-Reference.md) |
| `SqlValue`、`ColumnDef`、`QueryResult`、`DbValueKind`、流式事件/汇总、`DatabaseSessionStatus` 及对应 `Core...` 类型 | [数据类型与结果](Data-Types-and-Results.md) |
| `ServerInfo`、`MySqlServerInfo`、`ServerFamily`、`MySqlColumnDef`、`MySqlQueryResult` | [列与服务器信息](Data-Types-and-Results.md#列与服务器信息) |
| `QueryResultSink`、`CoreQueryResultSink`、`QueryTruncation` | [流式读取](Streaming.md)和[结果参考](Data-Types-and-Results.md#流式事件与汇总) |
| `CancellationOutcome`、`ConnectionReuse`、`QueryCancellationResult` | [取消结果](Cancellation-and-Timeouts.md#取消结果与连接复用) |
| 元数据、通用指标与 MySQL 指标类型、`ServerMetricsModel` 及指标上限常量 | [元数据与服务器指标](Metadata-and-Metrics.md) |

`ConnectionDeadline`、`SystemConnectionTimerPort`、`ConnectionTimerPort` 和 `connectionCleanupError` 是连接截止时间与清理的底层辅助接口；`estimateSqlValueBytes`、`estimateSqlRowBytes`、`estimateSqlRowsBytes` 是结果预算估算辅助函数。它们不提供应用层连接池、语句计时器或自动 Worker 管理。一般应用不需要直接使用这些辅助接口。

完整导出可对照同版 [公共入口](https://github.com/OrcaSQL-Workbench/ArkDB/blob/f532d0c37adf4dbba7a1a313679f0024822ed752/mysql/Index.ets)；辅助接口的实现和扩展约定在 [core 公共入口](https://github.com/OrcaSQL-Workbench/ArkDB/blob/f532d0c37adf4dbba7a1a313679f0024822ed752/core/Index.ets)与[共享契约说明](https://github.com/OrcaSQL-Workbench/ArkDB/blob/f532d0c37adf4dbba7a1a313679f0024822ed752/docs/driver-contracts.md)中。
