# 事务

事务使用专用连接，并在这条连接上串行执行。表也必须支持事务；驱动提供提交和回滚接口，不会改变 MySQL 本身的事务语义。

MySQL 1.0.2 保留 `setAutocommit`、`commit`、`rollback`，也通过 `features.transactions` 提供 `begin`、`commit`、`rollback` 和会话状态。方法签名见[公共接口](API-Reference.md)。

## 提交与回滚示例

这个示例在连接前关闭自动提交。成功时提交，失败时尝试回滚，最后总会尝试关闭；三条路径的错误分别保留。

```typescript
import { ConnectionConfig, ConnectionState, MySqlDriverFactory } from '@arkdb/mysql';

export class TransactionFailure extends Error {
  primaryFailure: Object | null;
  rollbackFailure: Object | null;
  cleanupFailure: Object | null;
  rollbackAttempted: boolean;

  constructor(primary: Object | null, rollback: Object | null,
    cleanup: Object | null, attempted: boolean) {
    super('Transaction or cleanup failed; inspect the retained failures without logging secrets.');
    this.primaryFailure = primary;
    this.rollbackFailure = rollback;
    this.cleanupFailure = cleanup;
    this.rollbackAttempted = attempted;
  }
}

export async function runTransaction(config: ConnectionConfig, password: string,
  trustedStatements: string[]): Promise<void> {
  const options = config.clone();
  options.autocommit = false;
  const errors = options.validate();
  if (errors.length > 0) throw errors[0];
  const connection = new MySqlDriverFactory().createConnection(options, password);
  let primary: Object | null = null;
  let rollback: Object | null = null;
  let cleanup: Object | null = null;
  let rollbackAttempted = false;
  try {
    await connection.connect();
    for (const sql of trustedStatements) await connection.query(sql);
    await connection.commit();
  } catch (error) {
    primary = error as Object;
    if (connection.state === ConnectionState.Ready) {
      rollbackAttempted = true;
      try { await connection.rollback(); } catch (error) { rollback = error as Object; }
    }
  } finally {
    try { await connection.close(); } catch (error) { cleanup = error as Object; }
  }
  if (primary !== null || rollback !== null || cleanup !== null) {
    throw new TransactionFailure(primary, rollback, cleanup, rollbackAttempted);
  }
}
```

`trustedStatements` 只能包含应用拥有的可信 SQL。当前没有参数绑定，不要把这个数组当作用户输入接口。

## 查看会话状态

`setAutocommit`、`commit` 和 `rollback` 返回 `DatabaseSessionStatus`。只有 `known` 明确为真时，才使用其中的自动提交和事务标记；查询结果对应检查 `statusKnown`。

普通 SQL 错误后，连接可能还开着，但会话状态已失效。需要继续使用时，先确认生命周期和会话状态；不要只根据“没有断线”判断事务仍处于原来的状态。

## 回滚不能解决的情况

MySQL DDL 可能隐式提交，非事务型表和外部副作用不受回滚保护。

如果提交响应丢失，后续回滚即使成功，也不能证明之前的提交没有发生。保留原始错误，按业务自己的核对流程确认实际结果，不自动重放写入。相关排查见[断线或超时后能否重试写入](Troubleshooting.md#断线或超时后能否重试写入)。
