# 公共接口与错误处理

所有公开类型都从 `@arkdb/mysql` 导入。应用不应导入包内路径，也无需直接依赖 `@arkdb/core`。

按需查阅：[工厂与连接](#工厂与连接)、[可选能力](#可选能力)、[元数据与服务器指标](#元数据与服务器指标)、[类型化错误](#类型化错误)、[日志](#日志)、[其他导出](#其他导出)。版本来源见[兼容性与升级](Compatibility-and-Upgrading.md)。

## 工厂与连接

一般应用使用 `MySqlDriverFactory` 创建 `DbConnection`：

| 工厂方法或属性 | 用途 |
| --- | --- |
| `createConnection(config: ConnectionConfig, password: string): DbConnection` | 创建连接，不自动连接 |
| `createMetadataProvider(connection): MetadataProvider` | 借用连接读取元数据 |
| `createExecutionController(controlConnection): DbExecutionController` | 使用调用方管理的控制连接取消查询 |
| `createServerMetricsProvider(connection): ServerMetricsProvider` | 借用连接读取 MySQL 指标 |
| `driverId`、`capabilities` | 驱动标识与能力信息 |

`MySqlDriverFactory.createConnection()` 返回 `MySqlConnection`。也可以使用便捷函数 `createMySqlConnection(config, password)`。元数据和指标接口借用已有连接，不负责连接和关闭。

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
| `mysqlFeatures` | MySQL 专用功能入口 |

同一连接的操作由调用方串行化。失败不代表可以安全重试；会话标记只在明确已知时使用。`ConnectionState` 包括 `Idle`、`Connecting`、`Authenticating`、`Ready`、`Querying`、`Closed` 和 `Error`。

配置与校验在[配置参考](Configuration-Reference.md)，值和返回字段在[数据类型与结果](Data-Types-and-Results.md)。

可运行示例见[连接配置与 TLS](Connections.md)、[查询、结果与流式读取](Queries.md)、[事务](Transactions.md)和[取消与超时](Cancellation-and-Timeouts.md)。

## 可选能力

`CoreDbConnection` 用于需要通用连接抽象的集成。可选功能从 `features` 获取；成员不存在表示该连接未提供该功能。

| 成员 | 接口和主要操作 |
| --- | --- |
| `features.streaming` | `DbStreamingConnection.queryStream(sql, options, sink)` |
| `features.health` | `DbConnectionHealth.ping()` |
| `features.context` | `DbContextController.changeContext(context)` 和 `contextPolicy` |
| `features.transactions` | `DbTransactionController.begin()`、`commit()`、`rollback()` 和 `sessionStatus` |
| `features.cancellation` | `CoreDbExecutionController.cancel(): Promise<QueryCancellationResult>` |
| `features.metadata` | `CoreMetadataProvider`，含可支持的对象种类 |
| `features.metrics` | `readMetrics(): Promise<ServerMetricsSnapshot>` |

MySQL 句柄式 `DbExecutionController.cancel(connectionHandle: string)` 返回 `Promise<void>`；通用取消接口不接收句柄，而是绑定当前连接上的执行。两者都有 `isInterruptionError(error: ArkDbError): boolean`，但控制连接的管理方式不同。完整用法见[取消与超时](Cancellation-and-Timeouts.md)。

编写通用集成时，可使用 `CoreDbDriverFactory<TOptions, TConnection>.create(options)`。MySQL 对应的参数类型是 `MySqlConnectionOptions(config, password)`。

`DbDriverRegistry.register(factory)` 注册驱动工厂；`describe(driverId)` 返回 `DbDriverDescriptor`，`driverIds()` 列出已注册标识。重复注册会报错。

`DatabaseContext`、`DatabaseContextPolicy` 和 `ContextChangeMode` 描述数据库上下文及其切换规则。

### MySQL 专属可选能力

使用 `requireMySqlFeatures(connection)` 获取 MySQL 专用功能。连接未提供该入口时会抛出 `Unsupported`；使用具体功能前仍应检查对应成员。

| `mysqlFeatures` 成员 | 主要接口 |
| --- | --- |
| `prepared` | `prepare`、类型化 `execute`、`executeStream` |
| `named` | 按当前 SQL mode 解析 `:name` 并进行类型化绑定 |
| `batch` | 串行预处理批处理，保留部分完成结果 |
| `insertRows` | 受限多行 INSERT，不接受原始 SQL 后缀 |
| `cursors` | 只读服务端游标 `open`、`fetch`、`close` |
| `longData` | 在显式预处理语句上上传长文本或二进制参数 |
| `procedures` | 二进制存储过程调用及 OUT/INOUT 结果 |
| `deadlines` | 带取消处理的文本查询/预处理语句截止时间 |
| `session` | `COM_RESET_CONNECTION` 会话重置 |
| `transactions` | 带隔离级别、只读、一致性快照和保存点的回调事务 |

接口、默认值和使用限制见[预处理与高级执行](Advanced-Execution.md)、[事务](Transactions.md)和[取消与超时](Cancellation-and-Timeouts.md)。

### 执行观察

`MySqlDriverFactory.create(new MySqlConnectionOptions(config, password, extensions))` 可以通过 `MySqlConnectionExtensions.executionObserver` 接收执行生命周期事件。事件包含类型、连接内序号、会话代次、命令类别、单调时刻和耗时，不包含 SQL、参数、凭据、服务器地址、账号、数据库、结果或错误内容。

执行观察只适用于传入 `extensions` 的 `create()` 调用。通过 `createConnection()`、`createMySqlConnection()` 或构造函数创建的连接不会启用观察。观察者抛错时会被移除，但不会中断当前数据库操作。

## 元数据与服务器指标

方法签名、结果模型和示例集中在[元数据与服务器指标](Metadata-and-Metrics.md)。

`MySqlMetadataProvider`、`MySqlExecutionController` 和 `MySqlServerMetricsProvider` 是具体实现。元数据和指标接口借用连接，不能与该连接上的其他操作并发执行。

`DriverCapabilities` 提供 MySQL 能力信息，`CoreDriverCapabilities` 是通用类型。能力标记用于发现功能，不能替代对实际接口成员的检查。

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
| `MySqlParameter`、`MySqlParameterType`、预处理、命名参数、游标、批处理、长参数和存储过程类型 | [预处理与高级执行](Advanced-Execution.md) |
| `MySqlTransactionIsolation`、`MySqlTransactionOptions`、`MySqlSession` | [事务](Transactions.md) |
| `MySqlDeadlineOptions`、`MySqlExecutionOutcome`、`MySqlOperationError` | [取消与超时](Cancellation-and-Timeouts.md)和[错误处理](Errors-and-Logging.md) |
| `MySqlConnectionOptions`、`MySqlConnectionExtensions`、`MySqlExecutionObserver` | 本页[执行观察](#执行观察) |
| 元数据、通用指标与 MySQL 指标类型、`ServerMetricsModel` 及指标上限常量 | [元数据与服务器指标](Metadata-and-Metrics.md) |

`ConnectionDeadline`、`SystemConnectionTimerPort`、`ConnectionTimerPort` 和 `connectionCleanupError` 是连接截止时间与清理的底层接口；一般应用无需直接使用。`estimateSqlValueBytes`、`estimateSqlRowBytes` 和 `estimateSqlRowsBytes` 用于估算结果预算。

完整导出列表见 [1.1.0 包入口](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/Index.ets)。
