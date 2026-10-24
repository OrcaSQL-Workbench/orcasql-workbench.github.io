# 元数据与服务器指标

MySQL 1.0.2 的 Provider 借用已经打开的连接，不负责创建、关闭或调度。它们的操作要与这条连接上的其他命令串行执行。

## 读取对象和指标

下面分别列出表和读取服务器概览。将代码保存为 `src\main\ets\sample\MetadataExample.ets`，两个函数均借用已经打开的连接：

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

## 列出表和字段的调用示例

下面是 `MetadataExample.ets` 的同文件续写。使用已存在且账号可见的数据库与表；这里的 `tableName` 是传给元数据 API 的对象名，不是拼接到 SQL 中的用户输入。

[//]: # (arkdb-example: metadata-columns)
```typescript
import { ColumnInfo, ConnectionConfig, ServerMetricsAvailability } from '@arkdb/mysql';
import { withConnection } from './ConnectionExample';

export async function listTableColumns(connection: DbConnection, database: string,
  tableName: string): Promise<ColumnInfo[]> {
  const context = new DatabaseContext();
  context.schema = database;
  return await new MySqlDriverFactory().createMetadataProvider(connection)
    .listColumns(context, tableName);
}

export async function inspectSampleTable(config: ConnectionConfig, password: string,
  database: string, tableName: string): Promise<string[]> {
  const output: string[] = [];
  await withConnection(config, password, async (connection: DbConnection): Promise<void> => {
    const tables = await listTables(connection, database);
    output.push('Visible tables: ' + tables.length.toString());
    for (const table of tables) output.push(table.name);
    const columns = await listTableColumns(connection, database, tableName);
    output.push('Visible columns: ' + columns.length.toString());
    for (const column of columns) {
      output.push(column.name + ' | ' + column.nativeTypeName);
    }
  });
  return output;
}
```

Worker 调用时传入实际数据库名和表名，例如[事务教程准备的](Transactions.md#调用示例) `arkdb_sample_accounts`。返回行数和类型名取决于服务器及账号可见性，不提供虚构的固定输出。不要用查询页已关闭会话中的临时表作为本例输入。

## 读取指标并检查可用性

继续在同一文件添加：

[//]: # (arkdb-example: metrics-availability)
```typescript
export async function readOverviewText(config: ConnectionConfig, password: string): Promise<string> {
  let text: string = '';
  await withConnection(config, password, async (connection: DbConnection): Promise<void> => {
    const category = await readMetrics(connection);
    const data = category.data;
    if (category.availability !== ServerMetricsAvailability.Available || data === null) {
      text = 'Metrics unavailable: ' + category.availability +
        ', kind=' + String(category.errorKind) +
        ', code=' + String(category.errorCode) +
        ', SQLSTATE=' + String(category.errorSqlState);
      return;
    }
    text = 'Connected threads: ' + data.threadsConnected.value.toString() +
      '\nRunning threads: ' + data.threadsRunning.value.toString();
  });
  return text;
}
```

Worker 使用实际配置和密码调用 `readOverviewText()`。计数是 `bigint`，直接转换为展示字符串，不先转成 `number`。示例只展示 `Available` 的数据；包括 `Empty` 在内的其他状态明确显示状态，不伪装成计数为零。调用本身抛错或连接关闭失败仍作为失败处理。

## 元数据方法

`MetadataProvider` 和 `MySqlMetadataProvider` 提供以下查询：

| 方法 | 返回 |
| --- | --- |
| `listCatalogs()` | `Promise<CatalogInfo[]>` |
| `listSchemas(catalog: string)` | `Promise<SchemaInfo[]>` |
| `listObjects(context: DatabaseContext, kind: DbObjectKind)` | `Promise<DbObjectInfo[]>` |
| `listColumns(context: DatabaseContext, objectName: string)` | `Promise<ColumnInfo[]>` |
| `listIndexes(context: DatabaseContext, objectName: string)` | `Promise<IndexInfo[]>` |
| `listForeignKeys(context: DatabaseContext, objectName: string)` | `Promise<ForeignKeyInfo[]>` |

列、索引与外键由 `ColumnInfo`、`IndexInfo`、`IndexColumnInfo`、`ForeignKeyInfo` 和 `ForeignKeyColumnInfo` 表达。对象种类使用 `DbObjectKind`。

可移植的 `CoreMetadataProvider` 另有 `supportedObjectKinds`。MySQL 也通过 `features.metadata` 提供元数据能力。MySQL 的 catalog/schema 是别名，不能据此推断其他驱动也是如此。

## 服务器指标方法

`MySqlMetricsProvider`，以及兼容名称 `ServerMetricsProvider`，提供：

| 方法 | `ServerMetricsCategory<T>` 中的 `T` |
| --- | --- |
| `readOverview()` | `ServerOverviewSnapshot` |
| `listProcesses(limit: number)` | `ServerProcessSnapshot` |
| `readInnoDb()` | `InnoDbSnapshot` |
| `readQueryActivity()` | `QueryActivitySnapshot` |
| `readReplication()` | `ReplicationSnapshot` |

这些方法都返回 Promise。先检查 `availability`（`ServerMetricsAvailability`），再读取 `data`。`data` 可能是 `null`；权限不足、Performance Schema 未启用或数据源不支持，不能当成指标为零。

`errorKind`、`errorCode` 和 `errorSqlState` 描述不可用的原因；分类使用 `ServerMetricsErrorKind`。

通用的 `features.metrics.readMetrics()` 返回 `ServerMetricsSnapshot`，以 `MetricMeasurement` 和 `MetricKind` 表达命名指标，不要求其他驱动实现 InnoDB 或复制线程模型。

## 更细的模型和上限

MySQL 指标模型还包括 `MetricGauge`、`MetricCounter`、`ServerProcessInfo`、`QueryActivitySnapshot`、`ReplicationChannelInfo`、`ReplicationSnapshot`、`ReplicationIoRunning` 和 `ReplicationSqlRunning`。`ServerMetricsModel.validate()` 返回模型校验错误。

`MAX_METRICS_PROCESS_ROWS`、`MAX_METRICS_REPLICATION_CHANNELS`、`MAX_METRICS_UNSIGNED_64`、`MAX_PROCESS_COMMAND_UTF8_BYTES`、`MAX_PROCESS_STATE_UTF8_BYTES` 和 `MAX_REPLICATION_CHANNEL_NAME_UTF8_BYTES` 定义模型上限，不代表服务器本身的容量。

完整字段在同版 [MySQL 指标定义](https://github.com/OrcaSQL-Workbench/ArkDB/blob/f532d0c37adf4dbba7a1a313679f0024822ed752/mysql/src/main/ets/mysql/metrics/MySqlServerMetrics.ets)中。需要构造这些模型或做通用集成时，再查[公共接口](API-Reference.md)；普通展示优先使用 Provider 返回的数据和可用性状态。
