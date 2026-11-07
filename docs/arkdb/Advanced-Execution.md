# 预处理与高级执行

MySQL 1.1.0 把数据库特有的高级执行能力放在可选的 `mysqlFeatures` 容器中。使用 `requireMySqlFeatures(connection)` 取得容器，再分别检查需要的成员；容器存在不代表每个可选能力都存在。发现能力不会联网，执行仍要求连接处于 Ready 且没有其他命令占用。

本页内容：[类型化预处理](#类型化预处理)、[命名参数](#命名参数)、[批处理与受限-insert](#批处理与受限-insert)、[只读服务端游标](#只读服务端游标)、[长参数](#长参数)、[存储过程](#存储过程)、[文本多语句](#文本多语句)、[共同边界](#共同边界)。

## 类型化预处理

`mysqlFeatures.prepared` 提供三种入口：

| 操作 | 用途 |
| --- | --- |
| `execute(sql, parameters, options?)` | 一次 PREPARE、EXECUTE、结果消费和 CLOSE |
| `executeStream(sql, parameters, options, sink)` | 使用二进制协议参数并按块读取结果 |
| `prepare(sql)` | 返回绑定当前物理会话的显式 `MySqlPreparedStatement` |

参数使用 `MySqlParameter` 和明确的 `MySqlParameterType`。支持 NULL、布尔、32/64 位整数、无符号 64 位整数、浮点、精确小数、文本、二进制、日期时间、时间和 JSON 文本。Int64/UInt64 使用 `bigint`；DECIMAL、时间和 JSON 使用经过校验的字符串；Binary 会复制 `Uint8Array`。值不会插入 SQL 文本。

`quoteMySqlIdentifier(parts)` 只引用可信的标识符段，`mysqlPlaceholders(count)` 生成位置参数占位符。两者都不代替值绑定。快速开始中的 `selectBoundValue()` 展示了这三者的组合。

`ConnectionConfig.preparedCacheSize` 可设为 `1..256`，为一次性 `execute`/`executeStream` 启用连接私有的精确 SQL LRU；未设置或 `0` 时关闭。显式 statement 不进入缓存。任何成功取得命令所有权的非缓存操作都会终止当前复用上下文；断线、会话重置和物理连接退役也会使句柄失效。

## 命名参数

`mysqlFeatures.named` 接受 `MySqlNamedParameter`，将可执行 SQL 中的 `:name` 转成位置占位符，再通过预处理二进制协议绑定。名称区分大小写，必须匹配 `[A-Za-z_][A-Za-z0-9_]*`；输入名称不能重复，SQL 中重复使用同一名称会按出现顺序重复绑定。

每次调用都会在同一命令所有权中读取当前 `@@SESSION.sql_mode`，再按实际模式处理引号、反斜杠和注释。可执行的 `?`、版本注释、优化器 hint、缺失或未使用参数都会被拒绝。命名参数只绑定值，标识符仍使用 `quoteMySqlIdentifier()`。

## 批处理与受限 INSERT

`mysqlFeatures.batch.execute(sql, rows, options?)` 复用一条内部预处理 statement，逐项串行执行参数行。默认最多 1000 项、累计缓冲 32 MiB；遇到首个失败停止，并通过 `MySqlBatchError` 保留已经完成的结果、失败索引和执行结果。它不会自动开启、提交或回滚事务。

`mysqlFeatures.insertRows.execute(tableParts, columns, rows, options?)` 只生成受限的 `INSERT INTO ... VALUES (...)`。表和列按标识符引用，值只能是类型化参数；接口不接受原始 SQL、表达式、`INSERT IGNORE`、`REPLACE` 或 upsert 后缀。驱动按 16 MiB packet 上限和 65535 参数上限分组，并保留部分完成结果。

受限 INSERT 可以在调用方拥有的手动事务或事务回调中运行。完成一个分组只表示服务器完成，不等于事务已经持久提交；未知结果不会自动重试。

## 只读服务端游标

`mysqlFeatures.cursors.open(sql, parameters, options?)` 使用专用预处理 statement 请求只读服务端游标。`MySqlCursorOptions.fetchRows` 默认 200，范围 `1..10000`；`maxBufferedBytes` 默认 32 MiB。继承的 `maxRows` 和 `maxResultBytes` 在全部 FETCH 调用之间累计。

返回的 `MySqlCursor` 提供执行时列信息、`done`、`fetch()` 和幂等 `close()`。游标从 PREPARE/EXECUTE 到结束期间持续占用连接，不能穿插查询、ping、会话重置或把连接交还连接池。短批次不等于结束；只有服务器的最后一行状态才能证明服务器结果已经耗尽。

`done` 只表示游标已经结束并释放连接所有权，不证明服务器结果已经完整读完。除了服务器报告最后一行，累计 `maxRows` 或 `maxResultBytes` 恰好用尽以及显式 `close()` 也会结束游标；预算结束时，本次允许的行会返回，但仍可能有未读取的服务器行。

服务器未建立游标而返回普通缓冲结果时，驱动不会静默退回一次性读取。无法确认同步、响应损坏或预算清理失败会使物理连接退役。

## 长参数

`mysqlFeatures.longData` 在显式 `MySqlPreparedStatement` 上上传文本或二进制长参数。每个参数由独立的 `MySqlByteSource` 提供；同一个一次性 source 不能绑定到多个参数索引。

`MySqlLongDataOptions` 默认每块 65536 字节、累计 67108864 字节、上传超时 30000 毫秒。source 按顺序读取和关闭；上传失败时不会发送 EXECUTE。能够确认同步的失败会重置 statement，写入结果不确定时会退役物理连接。连接关闭或上传超时也不会重放 source 或 SQL。

## 存储过程

`mysqlFeatures.procedures.call(procedureParts, arguments, options?)` 使用预处理二进制协议调用存储过程。`MySqlProcedureArgument` 明确 `In`、`Out` 和 `InOut` 方向；纯 OUT 使用类型化 NULL 占位符。

`MySqlProcedureResult` 按 wire 顺序保留全部结果，`outResultIndex` 标识 OUT 结果，`outValues` 按声明顺序提供输出值。驱动使用 `SERVER_PS_OUT_PARAMS` 识别输出结果，不创建 session 变量，也不退回文本 `CALL`。结果截断或输出形状不匹配会在完整排空后失败。

## 文本多语句

`ConnectionConfig.multipleStatements` 默认 `false`。只有完全由应用拥有的文本脚本才应启用；它不是参数绑定、转义或 SQL 解析器。驱动把完整字符串作为一次 `COM_QUERY` 发送，不按分号拆分；已有结果集数量、字节和同步排空预算覆盖整个脚本。

任何后续语句返回 ERR 都会使整个缓冲调用失败，不返回部分成功对象。已完成的写入不会自动回滚或重放。预处理、命名参数、游标、存储过程、长参数和受限 INSERT 保持各自的单语句协议。

## 共同边界

- 同一物理连接只有一个命令所有者，没有隐藏队列；所有操作必须串行 `await`。
- 预校验失败不会发命令；已派发操作的响应丢失可能产生 `Unknown` 结果，不能自动重试写入。
- 高级能力仍受 `QueryOptions` 的结果、结果集和同步排空预算约束。
- `mysqlFeatures.deadlines`、`mysqlFeatures.session` 和 `mysqlFeatures.transactions` 分别在[取消与超时](Cancellation-and-Timeouts.md)、[连接配置与 TLS](Connections.md)和[事务](Transactions.md)中说明。
- 当前没有连接池；如果应用自行实现租约，必须在重置或归还物理连接前关闭所有游标和显式 statement。
