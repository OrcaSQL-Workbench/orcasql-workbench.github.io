# 事务、取消与超时

应用必须区分“调用不再等待”“连接被关闭”“取消命令已发送”和“原查询已确定结束”。这些不是同一个状态，尤其不能据此推断写入一定没有发生。

## 事务

使用专用连接和事务型表。可在连接前将 `ConnectionConfig.autocommit` 设为 `false`，或在已连接会话上等待 `setAutocommit(false)`。通过 `commit()`、`rollback()` 和 `sessionStatus` 管理状态。

| 阶段 | 应用职责 |
| --- | --- |
| 执行前 | 校验配置，打开专用连接，明确自动提交策略 |
| 执行中 | 串行等待应用拥有的 SQL，不混入其他调用方的命令 |
| 成功路径 | 等待 `commit()`，检查返回的 `DatabaseSessionStatus` |
| 失败路径 | 保留原始错误；连接处于 `ConnectionState.Ready` 时才尝试回滚，并单独保留回滚错误 |
| 结束时 | 总是尝试关闭，并单独保留关闭错误，不覆盖主要失败 |

完整的错误保留示例见[包指南的事务示例](https://github.com/OrcaSQL-Workbench/ArkDB/blob/508adf42a6d7d485fe38c84cdf5c91322adf6e6d/mysql/README.md#transactions)。

MySQL DDL 可能隐式提交，非事务型表和外部副作用不受回滚保护。如果提交响应丢失，即使随后尝试或成功执行回滚，也不能证明提交没有发生。不要自动重放写入。

## 取消使用独立控制连接

`MySqlDriverFactory.createExecutionController(controlConnection)` 提供取消原语，不会替应用打开或管理控制连接。

1. 打开两条独立连接，指向同一服务器；控制账号需具有取消目标查询的权限。
2. 启动查询时立即绑定拒绝处理，避免取消期间发生未处理的 Promise 拒绝。
3. 用控制连接上的 controller 调用 `cancel(queryConnection.serverInfo.connectionHandle)`，不要把取消排在查询连接自己的队列后面。
4. 同时等待取消命令和原查询结束，分别保留两条路径的失败。
5. 结合 `controller.isInterruptionError(error)`、查询结果和连接状态决定是否可复用；正常完成也可能是取消竞争的合法结果。

`connectionHandle` 是不透明句柄，不要拼接用户输入生成 `KILL QUERY`。取消失败可能意味着原查询仍在运行。完整的有限 `SLEEP(10)` 读查询演示见[包指南的取消示例](https://github.com/OrcaSQL-Workbench/ArkDB/blob/508adf42a6d7d485fe38c84cdf5c91322adf6e6d/mysql/README.md#cancellation-and-deadlines)。

原查询未结束前，不要在它的连接上发下一条命令。取消控制连接本身的其他操作也必须串行。

## 连接截止时间不等于语句超时

| 设置或操作 | 实际保证 |
| --- | --- |
| `ConnectionConfig.connectTimeoutMs` | 打开连接的总截止时间 |
| `QueryOptions.statementTimeoutMs` | 仅校验数值；驱动不启动语句取消定时器 |
| `Promise.race` | 仅改变调用方等待行为，不会停止服务器执行 |
| 应用自己的计时器和取消流程 | 由应用负责触发取消、等待原操作及清理 |
| 强制关闭套接字或 Worker | 不能证明服务器端取消成功，执行结果可能未知 |

生产语句截止时间需要宿主管理计时器、独立控制连接、原查询的收尾和必要的强制关闭。不要把一个超时 Promise 包装成已经取消成功。

## 何时不能安全复用

普通服务器 SQL 错误不一定破坏连接；传输或协议失败、未知会话状态、强制终止或结果不确定则不能按正常会话继续使用。保留操作与清理错误并将不确定状态传给上层，由业务决定如何核对，而不是自动重连重试。

取消竞争、真实设备上的 TLS 和连接复用仍需单独验收。本地模拟结果不构成线上服务器兼容性证据。
