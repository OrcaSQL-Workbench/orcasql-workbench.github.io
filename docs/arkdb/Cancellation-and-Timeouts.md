# 取消与超时

“不再等待”“已发送取消请求”和“服务器执行已经结束”是三件不同的事。MySQL 1.0.2 提供取消接口；语句截止时间、等待原操作和必要的强制清理由应用安排。

## 取消当前查询

优先使用连接的 `features.cancellation`。MySQL 实现会为它管理独立控制连接及清理，不需要应用另外传入控制连接。

下面用有限时长的只读 `SLEEP(10)` 演示。查询一开始就绑定拒绝处理，取消后仍等待原查询；查询错误和控制错误分别保留。保存为 `src\main\ets\sample\CancellationExample.ets`。

```typescript
import { ArkDbError, ConnectionState, DbConnection } from '@arkdb/mysql';

export class CancellationFailure extends Error {
  queryFailure: Object | null;
  controlFailure: Object | null;

  constructor(query: Object | null, control: Object | null) {
    super('Query or cancellation failed; the execution outcome must be checked.');
    this.queryFailure = query;
    this.controlFailure = control;
  }
}

export class QueryObservation {
  failure: Object | null = null;
}

export async function demonstrateCancellation(queryConnection: DbConnection): Promise<string> {
  if (queryConnection.state !== ConnectionState.Ready) throw ArkDbError.validation('Connection is not ready.');
  const controller = queryConnection.features?.cancellation;
  if (controller === undefined) throw ArkDbError.unsupported('Cancellation is not available.');
  const query = new QueryObservation();
  let controlFailure: Object | null = null;
  const observed = queryConnection.query('SELECT SLEEP(10)').then(
    (): void => {},
    (error: Object): void => { query.failure = error; }
  );
  try {
    await controller.cancel();
  } catch (error) {
    controlFailure = error as Object;
  }
  await observed;
  const queryFailure = query.failure;
  const interrupted = queryFailure instanceof ArkDbError && controller.isInterruptionError(queryFailure);
  if (controlFailure !== null || (queryFailure !== null && !interrupted)) {
    throw new CancellationFailure(queryFailure, controlFailure);
  }
  return interrupted ? 'interrupted' : 'completed before cancellation took effect';
}
```

查询先正常完成也是合法结果，不能要求每次取消都产生中断错误。控制账号需要具备取消目标查询的权限，控制命令与目标查询必须在同一服务器上。

### 从 Worker 调用

准备[连接示例中的公共模块](Connections.md#定义连接信息并调用)，再在同一个 `CancellationExample.ets` 中添加：

[//]: # (arkdb-example: cancellation-call)
```typescript
import { ConnectionConfig } from '@arkdb/mysql';
import { withConnection } from './ConnectionExample';

export async function runCancellationExample(config: ConnectionConfig, password: string): Promise<string> {
  let outcome: string = '';
  await withConnection(config, password, async (connection: DbConnection): Promise<void> => {
    outcome = await demonstrateCancellation(connection);
  });
  return outcome;
}
```

Worker 将实际配置和本次密码传给 `runCancellationExample()`。可能正常返回 `interrupted`，也可能返回 `completed before cancellation took effect`；不要为追求固定输出而把正常完成改成取消成功。控制、查询或关闭失败时抛错，按失败响应处理。

## 取消结果与连接复用

`cancel()` 返回 `QueryCancellationResult`：

| 字段 | 含义 |
| --- | --- |
| `outcome` | `Requested` 表示请求已接受，`NotRunning` 表示没有正在执行的操作 |
| `connectionReuse` | `NotReady`、`Ready`、`AwaitingCompletion`、`RequiresSynchronization` 或 `Closed`，描述连接可复用状态 |

`Requested` 不是服务器中断成功的证明。等待原操作结束后，再检查连接和会话状态；请求未结束时不要在目标连接上发下一条命令。

如果已发出的 MySQL `KILL` 超时或结果丢失，目标连接会关闭并永久停用，避免延迟到达的控制命令影响后面的查询。此时创建新的连接实例，不要重新打开旧实例，更不要自动重放写入。

## 连接截止时间和语句截止时间

| 设置或做法 | 能做到什么 |
| --- | --- |
| `ConnectionConfig.connectTimeoutMs` | 限制打开连接的总时间 |
| `QueryOptions.statementTimeoutMs` | 校验数值，不会启动语句取消计时器 |
| `Promise.race` | 改变调用方等待时间，不停止服务器执行 |
| 应用计时器配合取消接口 | 发起取消后，仍要等待原操作并处理清理 |
| 关闭套接字或强制终止 Worker | 不能证明服务器已停止，也不能证明写入没有发生 |

需要语句截止时间时，由应用拥有计时器、取消、原操作收尾和必要的强制清理。不要让一个超时 Promise 对上层声称“取消成功”。

## 兼容的句柄式接口

`MySqlDriverFactory.createExecutionController(controlConnection)` 仍可用，返回的 MySQL `DbExecutionController.cancel(connectionHandle)` 接受不透明句柄。这个较低层的接口不会替应用创建或关闭控制连接。

如果选择它，应用要自行管理两条独立连接、权限、操作串行化和执行时序。不要把控制命令排到正在查询的连接后面，也不要用用户输入拼接 `KILL QUERY`。

两套接口的类型区别见[公共接口参考](API-Reference.md#可选能力)。
