# 事务

事务使用专用连接，并在这条连接上串行执行。表也必须支持事务；驱动提供提交和回滚接口，不会改变 MySQL 本身的事务语义。

连接提供 `setAutocommit`、`commit` 和 `rollback`；`mysqlFeatures.transactions` 还提供带隔离级别、只读设置、一致性快照和保存点的回调事务。方法签名见[公共接口](API-Reference.md)。

需要同时了解事务、查询取消和语句超时的关系时，可先看[事务、取消与超时](Transactions-and-Cancellation.md)。

## 提交与回滚示例

下面的示例使用回调事务。调用前，连接必须处于 `Ready`，会话状态必须已知，不能已经位于事务中，并且 `autocommit` 必须为 `true`。回调成功时提交；回调失败时，驱动会在连接状态允许的情况下尝试回滚。将代码保存为 `src\main\ets\sample\TransactionExample.ets`，由 Worker 调用。

```typescript
import {
  ArkDbError, ConnectionConfig, MySqlDriverFactory, MySqlSession,
  MySqlTransactionIsolation, MySqlTransactionOptions, requireMySqlFeatures
} from '@arkdb/mysql';

export class TransactionAndCloseFailure extends Error {
  transactionFailure: Object;
  closeFailure: Object;

  constructor(transactionFailure: Object, closeFailure: Object) {
    super('Transaction and connection close both failed.');
    this.transactionFailure = transactionFailure;
    this.closeFailure = closeFailure;
  }
}

export async function runTransaction(config: ConnectionConfig, password: string,
  trustedStatements: string[]): Promise<void> {
  const connectionConfig = config.clone();
  const errors = connectionConfig.validate();
  if (errors.length > 0) throw errors[0];
  const connection = new MySqlDriverFactory().createConnection(connectionConfig, password);
  let transactionFailure: Object | null = null;
  let closeFailure: Object | null = null;
  try {
    await connection.connect();
    const transactions = requireMySqlFeatures(connection).transactions;
    if (transactions === undefined) {
      throw ArkDbError.unsupported('Transaction callbacks are unavailable.');
    }
    const options = new MySqlTransactionOptions();
    options.isolation = MySqlTransactionIsolation.ReadCommitted;
    await transactions.run(options, async (session: MySqlSession): Promise<void> => {
      await session.savepoint('application_work');
      for (const sql of trustedStatements) await session.query(sql);
      await session.releaseSavepoint('application_work');
    });
  } catch (error) {
    transactionFailure = error as Object;
  }
  try { await connection.close(); } catch (error) { closeFailure = error as Object; }
  if (transactionFailure !== null && closeFailure !== null) {
    throw new TransactionAndCloseFailure(transactionFailure, closeFailure);
  }
  if (transactionFailure !== null) throw transactionFailure as Error;
  if (closeFailure !== null) throw closeFailure as Error;
}
```

`trustedStatements` 只能包含应用控制的 SQL，不要把用户输入直接放入该数组。事务回调不提供根连接上的预处理、批处理、命名参数或嵌套事务入口；需要绑定外部行值时，使用回调会话提供的 `session.mysqlFeatures.insertRows`。

## 调用示例

本例使用独立测试数据库中专门为教程准备的 InnoDB 表，不使用业务表。在数据库管理工具中执行下面的准备 SQL 一次；表已存在时先核对用途，不自动删除或覆盖：

```sql
CREATE TABLE arkdb_sample_accounts (
  id INT PRIMARY KEY,
  balance INT NOT NULL
) ENGINE=InnoDB;
INSERT INTO arkdb_sample_accounts (id, balance) VALUES (1, 100), (2, 100);
```

账号需要创建表及查询、更新测试数据的权限。准备语句不属于下面的事务，不把 DDL 写成可回滚操作。配置中 `defaultSchema` 应为准备该表的数据库，填写位置见[连接信息示例](Connections.md#定义连接信息并调用)。

在 `TransactionExample.ets` 中继续添加：

[//]: # (arkdb-example: transaction-call)
```typescript
export async function transferSampleBalance(config: ConnectionConfig, password: string): Promise<void> {
  await runTransaction(config, password, [
    'UPDATE arkdb_sample_accounts SET balance = balance - 10 WHERE id = 1',
    'UPDATE arkdb_sample_accounts SET balance = balance + 10 WHERE id = 2'
  ]);
}
```

从初始数据首次成功执行后，用新连接查询 `SELECT id, balance FROM arkdb_sample_accounts ORDER BY id`，余额应分别为 `90`、`110`。重复执行会再次转移，不要把该示例当作幂等操作。

在隔离测试中验证回滚时，可以将第二条语句改为引用不存在的列，使其产生普通 SQL 错误。函数应抛错；驱动会在会话仍同步且 Ready 时尝试回滚，并保留原始、回滚、取消和清理失败。另行查询实际余额，不能仅凭抛错就断言已回滚。不要用提交响应丢失来模拟“必定回滚”的场景。

教程表会保留在测试数据库中。确认不再需要且确实是本次创建的教程表后，由操作者显式清理，不在示例中自动删除。

## 查看会话状态

`setAutocommit`、`commit` 和 `rollback` 返回 `DatabaseSessionStatus`。只有 `known` 为 `true` 时，才能使用其中的自动提交和事务标记；查询结果对应检查 `statusKnown`。`MySqlSession` 只在事务回调执行期间有效。不要把它保存到回调外，并在回调返回前 `await` 完成所有会话操作。

`MySqlTransactionOptions` 可选择 `ReadCommitted`、`RepeatableRead`、`Serializable`、`ReadUncommitted` 或服务器默认隔离级别，还可设置 `readOnly` 和 `consistentSnapshot`。事务特征在 `START TRANSACTION` 前设置，不改变调用方原有 autocommit 设置。

普通 SQL 错误后，连接可能还开着，但会话状态已失效。需要继续使用时，先确认生命周期和会话状态；不要只根据“没有断线”判断事务仍处于原来的状态。

## 回滚不能解决的情况

MySQL DDL 可能隐式提交，非事务型表和外部副作用不受回滚保护。

如果提交响应丢失，后续回滚即使成功，也不能证明之前的提交没有发生。保留原始错误，按业务自己的核对流程确认实际结果，不自动重放写入。相关排查见[断线或超时后能否重试写入](Troubleshooting.md#断线或超时后能否重试写入)。
