# 错误与日志

MySQL 1.0.2 使用 `ArkDbError` 表达驱动错误。在抛错的线程内捕获和分类，再把必要的脱敏信息传给 UI。版本来源见[兼容性与升级](Compatibility-and-Upgrading.md)。

本页内容：[错误字段](#错误字段)、[错误类别](#错误类别)、[展示错误](#展示错误)、[日志设置](#日志设置)。

## 错误字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `kind` | `ArkDbErrorKind` | 通用类别 |
| `message` | `string` | 错误消息，可能包含敏感信息 |
| `code` | `number`，可选 | 保留兼容性的数值错误码 |
| `nativeCode` | `number \| string`，可选 | 原生数值或文本错误标识 |
| `sqlState` | `string`，可选 | 独立的 SQLSTATE |

根据类别和错误码判断，不匹配英文消息。SQLSTATE、原生错误标识和数值兼容字段不是同一个东西。

`ArkDbError` 继承 `Error`。构造函数接受类别、消息、可选原生码和可选 SQLSTATE；静态方法有 `network`、`tls`、`auth`、`protocol`、`timeout`、`cancelled`、`validation`、`unsupported` 和 `server`。

同一个驱动 HAR 中使用同一个错误构造器，便于 `instanceof ArkDbError` 判断。不要跨 Worker 传递原始错误并期待保留相同身份。

## 错误类别

| 类别 | 含义 |
| --- | --- |
| `Network` | 网络或传输失败 |
| `Tls` | TLS 协商或验证失败 |
| `Auth` | 认证失败 |
| `Protocol` | 协议或同步失败 |
| `Server` | 服务器返回错误 |
| `Timeout` | 截止时间相关错误 |
| `Cancelled` | 操作被取消 |
| `Validation` | 输入或配置不合法 |
| `Unsupported` | 当前不支持 |

一个普通 SQL 错误不一定关闭连接，但可能使会话状态未知。是否复用要结合状态判断；`Timeout` 本身也不能证明服务器停止执行。

## 展示错误

这个函数只生成展示文字，不负责吞掉错误、重试操作或判断连接可复用。保存为 `src\main\ets\sample\ErrorFormatting.ets`：

```typescript
import { ArkDbError, ArkDbErrorKind } from '@arkdb/mysql';

export function publicErrorText(error: Object): string {
  if (!(error instanceof ArkDbError)) return 'Unexpected failure; no operation was replayed.';
  let text = 'Database error: ' + error.kind;
  if (error.code !== undefined) text += ', code=' + error.code;
  if (error.sqlState !== undefined) text += ', SQLSTATE=' + error.sqlState;
  if (error.kind === ArkDbErrorKind.Tls) text += '. Check hostname, trust chain, and certificate access.';
  if (error.kind === ArkDbErrorKind.Auth) text += '. Check the account and authentication settings.';
  return text;
}
```

服务器消息可能含 SQL、用户名和业务数据，不要直接记录或放进跨线程 DTO。操作错误、回滚错误、关闭错误应分别保存；完整做法见[事务示例](Transactions.md#提交与回滚示例)。

## 展示连接与清理错误

连接页的 `withConnection()` 会分别保留操作和关闭错误。在 `ErrorFormatting.ets` 中继续添加下面的函数，供 Worker 的失败响应使用：

[//]: # (arkdb-example: error-cleanup)
```typescript
import { ConnectionExampleFailure } from './ConnectionExample';

export function connectionErrorText(error: Object): string {
  if (!(error instanceof ConnectionExampleFailure)) return publicErrorText(error);
  const lines: string[] = [];
  if (error.primaryFailure !== null) {
    lines.push('Operation failed: ' + publicErrorText(error.primaryFailure));
  }
  if (error.cleanupFailure !== null) {
    lines.push('Cleanup failed: ' + publicErrorText(error.cleanupFailure));
  }
  return lines.join('\n');
}
```

调用方式见 [Worker 示例](Worker-Integration.md#连接检查的请求与响应示例)。操作与关闭同时失败时，两项都应出现在失败响应中；函数不展示原始 `message`，也不把错误变成成功。事务的回滚错误仍应按 `TransactionFailure` 的独立字段处理，不套用这个连接专用函数。

## 日志设置

`Logger.setLevel(LogLevel.OFF)` 关闭驱动日志。自定义 `LogSink` 需要按线程显式启用。

下面的独立配置片段在执行数据库操作的 Worker 内调用：

[//]: # (arkdb-example: logging-level)
```typescript
import { Logger, LogLevel } from '@arkdb/mysql';

export function disableDriverLogs(): void {
  Logger.setLevel(LogLevel.OFF);
}
```

它只关闭驱动日志，不关闭应用自己的错误响应或诊断；不能用来掩盖数据库操作失败。

`LOG_DOMAIN` 和 `LogTag` 用于识别驱动日志，`ArkDB.*` 标签不承担应用 UI、存储或 RPC 的日志职责。内置标识符令牌只是假名化，不是匿名化。

不要把密码、认证材料或敏感数据交给任何 sink。日志需要发给他人时，先按[问题反馈清单](Troubleshooting.md#提交问题时附上什么)脱敏。
