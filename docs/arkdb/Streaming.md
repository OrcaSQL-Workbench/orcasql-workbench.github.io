# 有界流式读取

结果较多时，用 `queryStream(sql, options, sink)` 逐块处理，不必把全部行保存在内存里。下面的 MySQL 1.0.2 示例只统计行数。

## 按块处理结果

```typescript
import {
  ArkDbError, DbStreamingConnection, QueryExecutionSummary, QueryOptions,
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

export async function countBoundedRows(connection: DbStreamingConnection, trustedSql: string,
  sink: CountingSink): Promise<QueryExecutionSummary> {
  const options = new QueryOptions();
  options.maxRows = 10000;
  options.maxResultBytes = 4 * 1024 * 1024;
  const summary = await connection.queryStream(trustedSql, options, sink);
  if (!summary.statusKnown) throw ArkDbError.protocol('The session status is unknown.');
  return summary;
}
```

每次执行使用新的 sink，或由应用明确重置状态。`trustedSql` 来自可信的应用逻辑，不是待拼接的用户输入。

## 回调顺序

每个结果集依次经过 `onResultStart`、零个或多个 `onRows`、`onResultEnd`。行和列的字段说明见[流式事件与汇总](Data-Types-and-Results.md#流式事件与汇总)。

驱动会等待回调完成，但这不等于暂停套接字收包。接收队列也有上限；回调长期不返回可能使队列溢出并关闭连接。把每次处理的工作量控制在可完成的范围内，不要等待 UI 对每行逐一确认。

## 设置预算

按应用需要设置行数、块大小、结果大小和排空预算，字段统一在[配置参考](Configuration-Reference.md#queryoptions)中。字节数是驱动的估算，不是整个应用堆内存的测量值。

上例的 10,000 行和 4 MiB 是本次读取的选择，不是驱动默认值。

## 处理截断

达到行数上限不代表服务器查询已取消。未实现可选的 `onTruncation` 时，驱动会在预算内排空剩余协议数据，尝试恢复同步。预算耗尽会失败关闭，不会返回一个假装完整的结果。

如果接入 `onTruncation(truncation): Promise<boolean>`，返回值用于报告中断处理是否成功；不要只发出取消请求就返回成功。取消还必须等待原操作结束，见[取消指南](Cancellation-and-Timeouts.md)。

同时检查每个 `QueryResultSummary` 的截断标记和最终 `QueryExecutionSummary.statusKnown`。会话状态未知时，不要按正常空闲连接继续使用。
