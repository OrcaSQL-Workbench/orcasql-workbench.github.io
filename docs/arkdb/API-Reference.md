# 公共接口与错误处理

唯一受支持的包导入入口是 `@arkdb/mysql`。完整导出以 [`mysql/Index.ets`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/508adf42a6d7d485fe38c84cdf5c91322adf6e6d/mysql/Index.ets)为准，不依赖内部目录结构。没有 Workbench 命名的兼容别名。

## 工厂与连接

| 接口 | 用途 |
| --- | --- |
| `MySqlDriverFactory.createConnection(config, password)` | 创建 `DbConnection`，不自动连接 |
| `createMetadataProvider(connection)` | 借用已打开的连接读取元数据 |
| `createExecutionController(controlConnection)` | 在独立控制连接上提供取消原语 |
| `createServerMetricsProvider(connection)` | 借用已打开的连接读取服务器指标 |
| `driverId`、`capabilities` | 标识驱动及其能力，不表示 SQL 跨引擎可移植 |

[`DbConnection`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/508adf42a6d7d485fe38c84cdf5c91322adf6e6d/mysql/src/main/ets/core/connection/DbConnection.ets)提供：

| 方法或属性 | 返回类型 |
| --- | --- |
| `connect()`、`ping()`、`close()` | `Promise<void>` |
| `query(sql)` | `Promise<QueryResult>` |
| `queryStream(sql, options, sink)` | `Promise<QueryExecutionSummary>` |
| `changeContext(context)` | `Promise<void>` |
| `setAutocommit(enabled)`、`commit()`、`rollback()` | `Promise<DatabaseSessionStatus>` |
| `state` | 只读 `ConnectionState` |
| `serverInfo` | 只读 `ServerInfo` |
| `sessionStatus` | 只读 `DatabaseSessionStatus` |

`ConnectionConfig` 和 `SslConfig` 的字段见[连接配置与 TLS](Connections.md)；`QueryOptions`、`QueryResultSink` 和结果类型见[查询、结果与流式读取](Queries.md)。

## 元数据与服务器指标

Provider 借用现有连接，不负责创建、关闭或调度。与这条连接上的其他命令串行执行：

```typescript
import {
  DatabaseContext, DbConnection, DbObjectInfo, DbObjectKind,
  MySqlDriverFactory, ServerMetricsCategory, ServerOverviewSnapshot
} from '@arkdb/mysql';

export async function listTables(connection: DbConnection, database: string): Promise<DbObjectInfo[]> {
  const context = new DatabaseContext();
  context.schema = database;
  return await new MySqlDriverFactory().createMetadataProvider(connection)
    .listObjects(context, DbObjectKind.Table);
}

export async function readMetrics(connection: DbConnection):
  Promise<ServerMetricsCategory<ServerOverviewSnapshot>> {
  return await new MySqlDriverFactory().createServerMetricsProvider(connection).readOverview();
}
```

元数据包括数据库对象、列、索引和外键等类型。服务器指标可能要求额外权限，并以明确的可用性和错误状态报告；不能把不可用当成零值。MariaDB 服务器指标不支持。

## 类型化错误

在抛错的线程内捕获 `ArkDbError`，根据 `kind`、可选服务器 `code` 和 `sqlState` 作决定，不匹配英文消息文本：

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

`ArkDbErrorKind` 包括 `Network`、`Tls`、`Auth`、`Protocol`、`Server`、`Timeout`、`Cancelled` 和 `Validation`。这里的函数只生成脱敏展示文本，不吞掉错误，也不负责重试或认定连接可复用。

服务器消息可能包含 SQL、用户名或业务数据，不要原样记录或放入跨线程 DTO。保留主要失败、回滚失败和关闭失败时，应分别保存，不用“清理成功”替代操作结果。

## 日志

`Logger.setLevel(LogLevel.OFF)` 可关闭驱动日志。自定义 `LogSink` 按线程显式启用；内置标识符令牌是假名化，不是匿名化。不要向任何 sink 传递密码、认证材料或敏感业务数据。

驱动日志不承担应用 UI、存储或 RPC 日志。文件日志是显式可选功能，文件位置、访问权限和保留策略由宿主负责。
