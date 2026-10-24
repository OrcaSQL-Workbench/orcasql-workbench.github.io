# 数据类型与结果

这页说明 MySQL 1.0.2 的结果字段，以及同一个 HAR 中可移植契约的区别。普通读取示例见[查询指南](Queries.md)，版本来源见[兼容性与升级](Compatibility-and-Upgrading.md)。

本页内容：[SqlValue](#sqlvalue)、[列与服务器信息](#列与服务器信息)、[QueryResult](#queryresult)、[流式事件与汇总](#流式事件与汇总)、[MySQL 与 Core 类型](#mysql-类型与-core-类型)。

## SqlValue

MySQL 的 `SqlValue` 是 `string | number | bigint | Uint8Array | null`。

| SQL 值 | 结果表示 | 使用时注意 |
| --- | --- | --- |
| NULL | `null` | 不是字符串 `"NULL"` |
| BIGINT | `bigint` | 不要转成可能丢失精度的 `number` |
| DECIMAL | `string` | 保留精确十进制表示 |
| 日期、时间值 | `string` | 不自动转换成应用时区下的日期对象 |
| 二进制 | `Uint8Array` | 由应用决定显示和传输方式 |

`JSON.stringify` 不能直接序列化 `bigint`。发送 Worker 消息或准备 JSON 时，要为精确值和二进制定好格式，不要先做一次隐含的有损转换。

## 列与服务器信息

`columns[i]` 对应行数组的第 i 项。`ColumnDef` 包含列名、来源、`nativeTypeId`、`nativeTypeName`、`valueKind` 和可空标记。`DbValueKind` 表达逻辑类型，不替代实际值的检查。

MySQL 的 `ColumnDef` 是 `MySqlColumnDef` 的兼容名称，还保留 `table`、`type`、`charset`、`columnLength`、`flags`、`decimals` 等 MySQL 字段。不要把这些字段要求加到所有驱动的可移植列类型上。

`ServerInfo` 是 `MySqlServerInfo` 的兼容名称；连接上还可以读取版本、TLS 状态和不透明 `connectionHandle`。`ServerFamily.PostgreSQL` 是保留枚举值，不表示已实现 PostgreSQL 驱动。

## QueryResult

| 字段 | 用途 |
| --- | --- |
| `columns` | 列定义 |
| `rows` | 与列定义对齐的二维值数组 |
| `affectedRows` | 受影响行数 |
| `lastInsertId`、`warningCount` | MySQL 兼容类型中的插入标识与警告数 |
| `loadedBytes`、`executionTimeMs` | 驱动估算的已加载字节数和执行时间 |
| `truncated`、`truncationReason` | 是否截断及原因 |
| `additionalResults` | 后续结果集 |
| `statusKnown`、`autocommit`、`inTransaction` | 会话状态及其是否已知 |

先检查截断和 `statusKnown`。已加载的行不一定是完整结果，`autocommit` 或 `inTransaction` 的默认值也不能证明服务器当前状态。

## 流式事件与汇总

| 类型 | 主要字段 |
| --- | --- |
| `QueryResultMeta` | `resultIndex`、`columns`、`hasRows` |
| `QueryRowChunk` | `resultIndex`、`rowOffset`、`encodedBytes`、`rows` |
| `QueryTruncation` | `resultIndex`、`loadedRowCount`、`loadedBytes`、`reason` |
| `QueryResultSummary` | 当前结果集的行数、加载量、受影响行数、插入标识、警告数、截断信息和状态 |
| `QueryExecutionSummary` | 全部结果集数量、行数/加载量、耗时、`statusKnown`、`truncationInterrupted`、`synchronizationDeadlineMs` 和状态 |

`rowCountKnown` 用于判断行数是否已知。汇总中的 `status` 是 `DatabaseSessionStatus`；检查 `known` 后再用其中的事务标记。`QueryResultSink` 的回调签名与用法见[流式读取](Streaming.md)。

## MySQL 类型与 Core 类型

MySQL 保留原有公开类型和默认值，便于已有应用升级；可移植契约不凭空补出服务器未报告的值。

| MySQL 名称 | 可移植名称 |
| --- | --- |
| `SqlValue` | `CoreSqlValue`，还允许布尔值 |
| `DatabaseSessionStatus` | `CoreDatabaseSessionStatus` |
| `QueryResultMeta`、`QueryRowChunk` | `CoreQueryResultMeta`、`CoreQueryRowChunk` |
| `QueryResultSummary`、`QueryExecutionSummary` | `CoreQueryResultSummary`、`CoreQueryExecutionSummary` |
| `QueryResultSink` | `CoreQueryResultSink` |

MySQL 的插入标识和警告数保留零默认值；可移植流式汇总可以不提供未报告的字段。例如 EOF 行终止符未报告插入标识时，不能根据 MySQL 兼容结果的零值推断服务器实际报告了零。

`MySqlQueryResult` 与 `QueryResult` 是同一 MySQL 结果类的具体名称和兼容名称。可移植的连接、工厂、Provider 与取消接口在[公共接口参考](API-Reference.md#可选能力)中。

## 估算辅助函数

`estimateSqlValueBytes(value)`、`estimateSqlRowBytes(row)` 和 `estimateSqlRowsBytes(rows)` 返回预算用的字节估算。它们不测量运行时对象占用，也不是把结果序列化后的真实大小。

完整字段可对照同版[结果契约](https://github.com/OrcaSQL-Workbench/ArkDB/blob/f532d0c37adf4dbba7a1a313679f0024822ed752/core/src/main/ets/model/QueryStream.ets)和 [MySQL 适配类型](https://github.com/OrcaSQL-Workbench/ArkDB/blob/f532d0c37adf4dbba7a1a313679f0024822ed752/mysql/src/main/ets/mysql/model/MySqlQueryStream.ets)。
