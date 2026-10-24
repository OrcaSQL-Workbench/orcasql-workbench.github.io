# 查询、结果与流式读取

在已连接的 MySQL 会话上调用 `query(sql)`。同一连接同时只执行一个操作，驱动不会把重叠调用自动排队。

本页适用于 MySQL 1.0.2。`sql` 必须来自应用可信逻辑；当前没有参数绑定和预处理语句，不要拼接不可信的用户输入。

## 普通查询与类型

`query()` 返回 `QueryResult`。每行是数组，`columns[i]` 描述 `rows[rowIndex][i]`。

BIGINT 使用 `bigint`，DECIMAL 和时间值保留字符串，二进制使用 `Uint8Array`，SQL NULL 是 `null`。不要为方便显示而先把精确值转成 `number`。

下面按原有类型格式化一行：

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
