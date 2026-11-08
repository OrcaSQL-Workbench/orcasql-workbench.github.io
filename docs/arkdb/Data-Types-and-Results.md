# 数据类型与结果

本页说明查询结果中的值类型、列信息和执行状态。普通读取示例见[查询指南](Queries.md)。

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

### 读取并格式化值的示例

准备[连接公共模块](Connections.md#定义连接信息并调用)和[查询页的 `ResultFormatting.ets`](Queries.md#普通查询与类型)，将下面的独立模块保存为 `src\main\ets\sample\ValueExample.ets`。由 Worker 传入实际连接配置和本次密码调用，不需要写入数据库。

[//]: # (arkdb-example: values-read)
```typescript
import { ArkDbError, ConnectionConfig, DbConnection } from '@arkdb/mysql';
import { withConnection } from './ConnectionExample';
import { displayRow } from './ResultFormatting';

export async function readValueExamples(config: ConnectionConfig, password: string): Promise<string[]> {
  const output: string[] = [];
  await withConnection(config, password, async (connection: DbConnection): Promise<void> => {
    const result = await connection.query(
      'SELECT NULL AS sql_null, CAST(9007199254740993 AS UNSIGNED) AS exact_bigint, ' +
      "CAST(12.34 AS DECIMAL(10,2)) AS exact_decimal, CAST('AB' AS BINARY) AS binary_value"
    );
    if (result.truncated || result.rows.length !== 1) {
      throw ArkDbError.protocol('Expected one complete sample row.');
    }
    output.push(result.columns.map((column): string => column.name).join(' | '));
    output.push(displayRow(result, 0).join(' | '));
  });
  return output;
}
```

运行后应得到：

```text
sql_null | exact_bigint | exact_decimal | binary_value
NULL | 9007199254740993 | 12.34 | 0x4142
```

第一项的原始值是 `null`，不是字符串；BIGINT 的原始值是 `bigint`，小数仍为字符串，二进制仍为 `Uint8Array`。`displayRow()` 只在展示边界进行转换。需要继续计算时，保留原始值和类型，不从展示文字反推数据。

## 列与服务器信息

`columns[i]` 对应行数组的第 i 项。`ColumnDef` 包含列名、来源、`nativeTypeId`、`nativeTypeName`、`valueKind` 和可空标记。`DbValueKind` 表达逻辑类型，不替代实际值的检查。

MySQL 的 `ColumnDef` 是 `MySqlColumnDef` 的兼容名称，还提供 `table`、`type`、`charset`、`columnLength`、`flags`、`decimals` 等 MySQL 专用字段。通用列类型不保证包含这些字段。

`ServerInfo` 是 `MySqlServerInfo` 的兼容名称；连接上还可以读取服务器版本、TLS 状态和不透明的 `connectionHandle`。

## QueryResult

| 字段 | 用途 |
| --- | --- |
| `columns` | 列定义 |
| `rows` | 与列定义对齐的二维值数组 |
| `affectedRows` | 保留兼容性的数值受影响行数，超出安全整数范围时可能丢失精度 |
| `affectedRowsExact` | 服务器报告 OK 受影响行数时的可选精确 `bigint` |
| `lastInsertId`、`warningCount` | MySQL 兼容类型中的插入标识与警告数 |
| `loadedBytes`、`executionTimeMs` | 驱动估算的已加载字节数和执行时间 |
| `truncated`、`truncationReason` | 是否截断及原因 |
| `additionalResults` | 后续结果集 |
| `statusKnown`、`autocommit`、`inTransaction` | 会话状态及其是否已知 |

先检查截断和 `statusKnown`。已加载的行不一定是完整结果，`autocommit` 或 `inTransaction` 的默认值也不能证明服务器当前状态。

`mapMySqlRows(result, mapper)` 按位置投影缓冲结果，不更改原始值类型。mapper 收到原始行、列数组和零基行号；重复列名仍按位置区分，异常按原身份传播。

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

MySQL 类型保留兼容字段和默认值；通用类型中，服务器未返回的字段可能为 `undefined`。

| MySQL 名称 | 通用名称 |
| --- | --- |
| `SqlValue` | `CoreSqlValue`，还允许布尔值 |
| `DatabaseSessionStatus` | `CoreDatabaseSessionStatus` |
| `QueryResultMeta`、`QueryRowChunk` | `CoreQueryResultMeta`、`CoreQueryRowChunk` |
| `QueryResultSummary`、`QueryExecutionSummary` | `CoreQueryResultSummary`、`CoreQueryExecutionSummary` |
| `QueryResultSink` | `CoreQueryResultSink` |

MySQL 的插入标识和警告数保留零默认值；通用流式汇总可能省略服务器未报告的字段。例如 EOF 行终止符未报告插入标识时，不能根据 MySQL 兼容结果的零值推断服务器实际报告了零。

`MySqlQueryResult` 与 `QueryResult` 指向同一个 MySQL 结果类。通用连接、工厂、元数据和取消接口见[公共接口参考](API-Reference.md#可选能力)。

## 估算辅助函数

`estimateSqlValueBytes(value)`、`estimateSqlRowBytes(row)` 和 `estimateSqlRowsBytes(rows)` 返回预算用的字节估算。它们不测量运行时对象占用，也不是把结果序列化后的真实大小。

完整字段见 1.1.0 的[通用结果定义](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/core/src/main/ets/model/QueryStream.ets)和 [MySQL 结果定义](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/model/MySqlQueryStream.ets)。
