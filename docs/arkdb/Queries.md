# 查询、结果与流式读取

在已连接的 MySQL 会话上调用 `query(sql)`。同一连接同时只执行一个操作，驱动不会把重叠调用自动排队。

本页适用于 MySQL 1.0.2。`sql` 必须来自应用可信逻辑；当前没有参数绑定和预处理语句，不要拼接不可信的用户输入。

## CRUD 示例的准备

先按[连接示例](Connections.md#定义连接信息并调用)准备 `ConnectionExample.ets`，填写真实的主机、端口、测试数据库、账号和 TLS 设置。下面各操作放在同一个 `src\main\ets\sample\QueryExample.ets` 中，第一个代码块包含公共导入，其余为同文件续写。

各函数借用已经连接的会话，不自行连接或关闭。按“建表 → 插入 → 查询 → 更新 → 查询 → 删除 → 查询”的顺序，在同一连接上逐个 `await`。不要在步骤之间重连，也不要并发执行。

示例使用固定 SQL 和临时表，不修改已有业务表。测试数据库必须已存在，账号需要该数据库的 `CREATE TEMPORARY TABLES` 权限。临时表属于创建它的会话，会话关闭后移除；不需要删除数据库或服务器。

## 创建示例表

[//]: # (arkdb-example: crud-create)
```typescript
import { ArkDbError, ConnectionConfig, DbConnection, QueryResult } from '@arkdb/mysql';
import { withConnection } from './ConnectionExample';
import { displayRow } from './ResultFormatting';

export async function createSampleTable(connection: DbConnection): Promise<void> {
  await connection.query(
    'CREATE TEMPORARY TABLE arkdb_sample_inventory (' +
    'id INT PRIMARY KEY, name VARCHAR(50) NOT NULL, quantity INT NOT NULL)'
  );
}
```

`ResultFormatting.ets` 的内容见本页[普通查询与类型](#普通查询与类型)。创建成功后得到一张空表；不要在同一会话重复创建。需要从头演示时，结束旧会话后使用新的连接，而不是删除同名业务表。

## 插入数据

[//]: # (arkdb-example: crud-insert)
```typescript
export async function insertSampleRows(connection: DbConnection): Promise<QueryResult> {
  return await connection.query(
    "INSERT INTO arkdb_sample_inventory (id, name, quantity) " +
    "VALUES (1, 'banana', 150), (2, 'orange', 154)"
  );
}
```

在空的示例表上首次执行，预期 `result.affectedRows` 为 `2`。再次插入相同主键会失败，不能吞掉错误或自动重试。

## 查询数据

[//]: # (arkdb-example: crud-read)
```typescript
export async function readSampleRows(connection: DbConnection): Promise<QueryResult> {
  const result = await connection.query(
    'SELECT id, name, quantity FROM arkdb_sample_inventory ORDER BY id'
  );
  if (result.truncated) throw ArkDbError.validation('Sample query result was truncated.');
  return result;
}
```

插入后的预期数据：

| id | name | quantity |
| --- | --- | --- |
| 1 | banana | 150 |
| 2 | orange | 154 |

`columns[i]` 对应每行的 `rows[rowIndex][i]`，不是 `rows[rowIndex].name`。`ORDER BY id` 明确结果顺序。下面的调用示例通过 `displayRow()` 生成展示文字，不把原始结果对象发送给 UI。

## 更新数据

[//]: # (arkdb-example: crud-update)
```typescript
export async function updateSampleRow(connection: DbConnection): Promise<QueryResult> {
  return await connection.query(
    'UPDATE arkdb_sample_inventory SET quantity = 200 WHERE id = 1'
  );
}
```

按上述顺序首次执行，预期 `result.affectedRows` 为 `1`。再次查询时，`id = 1` 的数量应为 `200`，`id = 2` 仍为 `154`。这个受影响行数只描述本次样本操作，不保证重复更新仍返回相同值。

## 删除数据

[//]: # (arkdb-example: crud-delete)
```typescript
export async function deleteSampleRow(connection: DbConnection): Promise<QueryResult> {
  return await connection.query(
    'DELETE FROM arkdb_sample_inventory WHERE id = 2'
  );
}
```

按上述顺序首次执行，预期 `result.affectedRows` 为 `1`。再次查询应只剩 `1 | banana | 200`。`WHERE` 限定删除目标；不要将示例表名替换成业务表后直接运行。

## 串行调用与结果

仍在 `QueryExample.ets` 中添加下面的函数。由 Worker 使用实际配置和本次密码调用 `runCrudExample(config, password)`；配置的定义位置见[连接信息示例](Connections.md#定义连接信息并调用)。

[//]: # (arkdb-example: crud-call)
```typescript
function appendSampleRows(result: QueryResult, output: string[]): void {
  for (let index = 0; index < result.rows.length; index++) {
    output.push(displayRow(result, index).join(' | '));
  }
}

export async function runCrudExample(config: ConnectionConfig, password: string): Promise<string[]> {
  const options = config.clone();
  options.autocommit = true;
  const output: string[] = [];
  await withConnection(options, password, async (connection: DbConnection): Promise<void> => {
    await createSampleTable(connection);
    const inserted = await insertSampleRows(connection);
    output.push('Inserted rows: ' + inserted.affectedRows.toString());
    appendSampleRows(await readSampleRows(connection), output);
    const updated = await updateSampleRow(connection);
    output.push('Updated rows: ' + updated.affectedRows.toString());
    appendSampleRows(await readSampleRows(connection), output);
    const deleted = await deleteSampleRow(connection);
    output.push('Deleted rows: ' + deleted.affectedRows.toString());
    appendSampleRows(await readSampleRows(connection), output);
  });
  return output;
}
```

固定 SQL 对应的预期展示如下，不是实机运行记录：

```text
Inserted rows: 2
1 | banana | 150
2 | orange | 154
Updated rows: 1
1 | banana | 200
2 | orange | 154
Deleted rows: 1
1 | banana | 200
```

这些是自动提交的独立操作，不是一个事务。操作失败时不返回成功结果，`withConnection()` 仍会尝试关闭并保留操作与关闭错误。关闭失败不能描述成已完成清理；断线或响应丢失不能证明写入没有发生。需要原子提交时看[事务](Transactions.md)。

## 普通查询与类型

`query()` 返回 `QueryResult`。每行是数组，`columns[i]` 描述 `rows[rowIndex][i]`。

BIGINT 使用 `bigint`，DECIMAL 和时间值保留字符串，二进制使用 `Uint8Array`，SQL NULL 是 `null`。不要为方便显示而先把精确值转成 `number`。

下面按原有类型格式化一行，保存为 `src\main\ets\sample\ResultFormatting.ets`，供上面的查询示例导入：

```typescript
import { ArkDbError, QueryResult, SqlValue } from '@arkdb/mysql';

export function displayCell(value: SqlValue): string {
  if (value === null) return 'NULL';
  if (value instanceof Uint8Array) {
    return '0x' + Array.from(value).map((byte: number): string =>
      byte.toString(16).padStart(2, '0')).join('');
  }
  return value.toString();
}

export function displayRow(result: QueryResult, rowIndex: number): string[] {
  if (!Number.isSafeInteger(rowIndex) || rowIndex < 0 || rowIndex >= result.rows.length) {
    throw ArkDbError.validation('Row index is outside the loaded result.');
  }
  return result.rows[rowIndex].map(displayCell);
}
```

`QueryResult` 还带有受影响行数、插入标识、警告数、截断信息和后续结果集。字段定义见[数据类型与结果](Data-Types-and-Results.md#queryresult)。

读取前先检查 `truncated` 和 `truncationReason`，不要把已加载的行当作全部结果。只有 `statusKnown` 明确为真时，才能使用自动提交和事务状态。

## 有界流式读取

`query()` 内部也是有界读取，不是无限制收集器。需要控制选项，或不想在内存中保留全部行时，使用[有界流式读取](Streaming.md)的 `queryStream(sql, options, sink)`。

不要逐块读完后又把所有块拼成一个大数组或字符串，这会失去流式处理的意义。

## QueryOptions 默认值

行数、分块、结果字节数和截断后的排空预算，统一见 [QueryOptions 参考](Configuration-Reference.md#queryoptions)。

特别注意：`statementTimeoutMs` 只校验数值，底层驱动不会因此启动语句取消计时器。应用的截止时间与取消流程见[取消与超时](Cancellation-and-Timeouts.md)。

## 多个结果集

普通结果的后续结果集放在 `additionalResults`。流式接口按结果集依次调用 sink，因此一次执行可能收到多组开始、行块和结束事件。

分别检查每个结果集的截断状态。`lastInsertId` 为零不一定说明服务器实际报告了零；MySQL 兼容类型和可移植类型的差异见[结果类型说明](Data-Types-and-Results.md#mysql-类型与-core-类型)。
