# 查询、结果与流式读取

一条连接同时只执行一个操作。驱动不替应用建立并发队列；查询、事务、元数据、指标和取消控制命令都要遵守各自的连接串行化约束。

## 普通查询与类型

`await connection.query(sql)` 返回 `QueryResult`。它内部使用有界流式实现，不是无限制收集器。`columns[i]` 描述每行的 `rows[rowIndex][i]`：

| SQL 值 | 公共结果中的值 |
| --- | --- |
| SQL NULL | `null`，不是字符串 `"NULL"` |
| BIGINT | `bigint` |
| DECIMAL、时间值 | 字符串 |
| 二进制值 | `Uint8Array` |

不要用 `number` 替代精确的 BIGINT 或 DECIMAL。JSON 不能直接序列化 `bigint`；跨 Worker 的消息格式和类型转换需要由应用明确设计。

```typescript
import { SqlValue } from '@arkdb/mysql';

export function displayCell(value: SqlValue): string {
  if (value === null) return 'NULL';
  if (value instanceof Uint8Array) {
    return '0x' + Array.from(value).map((byte: number): string =>
      byte.toString(16).padStart(2, '0')).join('');
  }
  return value.toString();
}
```

显示前检查 `truncated` 和 `truncationReason`，不能把已加载行当成完整结果。`additionalResults` 保存后续结果集；`affectedRows`、`lastInsertId`、`warningCount`、`autocommit` 和 `inTransaction` 提供执行与会话信息。把整个结果拼成大字符串会重新引入内存压力。

当前不支持预处理语句或参数绑定。这里的 `sql` 必须来自应用可信逻辑；不要拼接不可信的用户输入。

## 有界流式读取

需要控制已加载结果时，使用 `queryStream(sql, options, sink)`。下面的示例只累计行数，不保留全部行：

```typescript
import {
  ArkDbError, DbConnection, QueryExecutionSummary, QueryOptions,
  QueryResultMeta, QueryResultSink, QueryResultSummary, QueryRowChunk
} from '@arkdb/mysql';

export class CountingSink implements QueryResultSink {
  loadedRows: number = 0;
  truncated: boolean = false;

  async onResultStart(_meta: QueryResultMeta): Promise<void> {}
  async onRows(chunk: QueryRowChunk): Promise<void> {
    this.loadedRows += chunk.rows.length;
  }
  async onResultEnd(summary: QueryResultSummary): Promise<void> {
    this.truncated = this.truncated || summary.truncated;
  }
}

export async function countBoundedRows(connection: DbConnection, trustedSql: string,
  sink: CountingSink): Promise<QueryExecutionSummary> {
  const options = new QueryOptions();
  options.maxRows = 10000;
  options.maxResultBytes = 4 * 1024 * 1024;
  const summary = await connection.queryStream(trustedSql, options, sink);
  if (!summary.statusKnown) throw ArkDbError.protocol('The session status is unknown.');
  return summary;
}
```

每次执行使用新的 sink，或由应用明确重置统计值。回调被逐个等待，但这不暂停套接字收包；独立的接收队列仍然有界，溢出会关闭失败，不能让 sink 无限等待。

## QueryOptions 默认值

| 选项 | 默认值 | 意义 |
| --- | --- | --- |
| `maxRows` | `0` | 不设行数上限，其他预算仍有效 |
| `maxChunkRows` | `200` | 单次回调的最大行数 |
| `maxChunkBytes` | `262144` | 单块字节预算 |
| `maxResultBytes` | `33554432` | 已解码结果的字节预算 |
| `maxResultSets` | `64` | 结果集数量安全限制 |
| `maxDrainBytes` | `33554432` | 截断后为同步协议而排空的字节预算 |
| `maxDrainTimeMs` | `5000` | 排空时间预算 |
| `statementTimeoutMs` | `0` | 仅校验数值，底层驱动不启动语句取消定时器 |

字节数是驱动估算，不是应用总堆内存。达到行数上限不等于服务器执行被取消；没有实现可选 `onTruncation` 时，会按预算排空剩余协议数据以尝试恢复同步。排空或传输预算耗尽时失败关闭，不能伪装成完整成功。

检查每个 `QueryResultSummary` 的截断状态，以及最终 `QueryExecutionSummary.statusKnown`。未知状态不应当作连接可复用的证明。取消与截止时间的宿主职责见[事务、取消与超时](Transactions-and-Cancellation.md)。

接口依据：[QueryStream](https://github.com/OrcaSQL-Workbench/ArkDB/blob/508adf42a6d7d485fe38c84cdf5c91322adf6e6d/mysql/src/main/ets/core/model/QueryStream.ets)及[包指南](https://github.com/OrcaSQL-Workbench/ArkDB/blob/508adf42a6d7d485fe38c84cdf5c91322adf6e6d/mysql/README.md)。
