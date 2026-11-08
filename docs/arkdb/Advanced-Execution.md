# 预处理与高级执行

通过 `requireMySqlFeatures(connection)` 获取 MySQL 专用功能。使用某项功能前应检查对应成员是否存在；执行时连接必须处于 `Ready`，并且没有其他操作正在进行。

本页内容：[类型化预处理](#类型化预处理)、[命名参数](#命名参数)、[批处理与受限-insert](#批处理与受限-insert)、[只读服务端游标](#只读服务端游标)、[长参数](#长参数)、[存储过程](#存储过程)、[文本多语句](#文本多语句)、[共同边界](#共同边界)。

## 类型化预处理

`mysqlFeatures.prepared` 提供三种入口：

| 操作 | 用途 |
| --- | --- |
| `execute(sql, parameters, options?)` | 准备并执行一次语句，读取结果后自动关闭 |
| `executeStream(sql, parameters, options, sink)` | 使用二进制协议参数并按块读取结果 |
| `prepare(sql)` | 返回绑定当前连接的 `MySqlPreparedStatement` |

参数使用 `MySqlParameter` 和明确的 `MySqlParameterType`。支持 NULL、布尔、32/64 位整数、无符号 64 位整数、浮点、精确小数、文本、二进制、日期时间、时间和 JSON 文本。Int64/UInt64 使用 `bigint`；DECIMAL、时间和 JSON 使用经过校验的字符串；Binary 会复制 `Uint8Array`。值不会插入 SQL 文本。

`quoteMySqlIdentifier(parts)` 只引用可信的标识符段，`mysqlPlaceholders(count)` 生成位置参数占位符。两者都不代替值绑定。快速开始中的 `selectBoundValue()` 展示了这三者的组合。

`ConnectionConfig.preparedCacheSize` 可设为 `1..256`，为 `execute` 和 `executeStream` 启用连接内的最近最少使用（LRU）缓存；未设置或设为 `0` 时关闭。通过 `prepare()` 创建的语句不进入缓存。执行其他连接操作、断开连接或重置会话后，缓存中的语句会失效。

## 命名参数

`mysqlFeatures.named` 接受 `MySqlNamedParameter`，将可执行 SQL 中的 `:name` 转成位置占位符，再通过预处理二进制协议绑定。名称区分大小写，必须匹配 `[A-Za-z_][A-Za-z0-9_]*`；输入名称不能重复，SQL 中重复使用同一名称会按出现顺序重复绑定。

每次调用都会读取当前 `@@SESSION.sql_mode`，再按实际模式处理引号、反斜杠和普通注释。SQL 中不能混用可执行的 `?`，也不能包含 MySQL 版本注释（如 `/*! ... */`、`/*M! ... */`）或优化器 hint（`/*+ ... */`）；无论参数是否位于注释内，这些可执行注释都会导致校验失败。缺失、重复或未使用的参数也会报错。命名参数只绑定值，标识符仍使用 `quoteMySqlIdentifier()`。

## 批处理与受限 INSERT

`mysqlFeatures.batch.execute(sql, rows, options?)` 复用一条预处理语句，依次执行各组参数。默认最多 1000 组，累计结果最多 32 MiB。遇到错误后停止，`MySqlBatchError` 会保留已经完成的结果和失败位置。非空批处理要求会话事务状态已知，并且不能在已有事务中执行；批处理本身不会自动开启、提交或回滚事务。

`mysqlFeatures.insertRows.execute(tableParts, columns, rows, options?)` 只生成 `INSERT INTO ... VALUES (...)`。表名和列名会按标识符引用，值使用类型化参数；接口不接受原始 SQL、表达式、`INSERT IGNORE`、`REPLACE` 或 upsert 后缀。驱动会按 16 MiB 数据包上限和 65535 个参数的上限自动分组，并保留已经完成的结果。

与普通批处理不同，`insertRows` 可以在手动事务或事务回调中运行。完成一个分组只表示服务器已执行该语句，不表示事务已经提交。

## 只读服务端游标

`mysqlFeatures.cursors.open(sql, parameters, options?)` 使用专用预处理语句请求只读服务端游标。`MySqlCursorOptions.fetchRows` 默认 200，范围 `1..10000`；`maxBufferedBytes` 默认 32 MiB。继承的 `maxRows` 和 `maxResultBytes` 在全部 FETCH 调用之间累计。

返回的 `MySqlCursor` 提供列信息、`done`、`fetch()` 和可重复调用的 `close()`。游标打开期间会独占连接，不能穿插查询、`ping()`、会话重置或把连接交还连接池。返回行数少于 `fetchRows` 并不代表读取结束；只有服务器的最后一行状态才能证明结果已经读完。

`done` 只表示游标已经结束并释放连接所有权，不证明服务器结果已经完整读完。除了服务器报告最后一行，累计 `maxRows` 或 `maxResultBytes` 恰好用尽以及显式 `close()` 也会结束游标；预算结束时，本次允许的行会返回，但仍可能有未读取的服务器行。

如果服务器没有建立游标，驱动会直接报错，不会改为一次性读取。响应损坏或无法恢复协议同步时，连接会被关闭。

## 长参数

`mysqlFeatures.longData` 用于向显式 `MySqlPreparedStatement` 上传较大的文本或二进制参数。每个参数使用独立的 `MySqlByteSource`；同一个一次性数据源不能绑定到多个参数位置。

`MySqlLongDataOptions` 默认每块 65536 字节、总计最多 67108864 字节、上传超时 30000 毫秒。数据源按顺序读取并关闭；上传失败时不会执行语句。若无法确认连接仍与服务器同步，连接会被关闭。

## 存储过程

`mysqlFeatures.procedures.call(procedureParts, arguments, options?)` 使用预处理二进制协议调用存储过程。`MySqlProcedureArgument` 明确 `In`、`Out` 和 `InOut` 方向；纯 OUT 使用类型化 NULL 占位符。

`MySqlProcedureResult` 按服务器返回顺序保留全部结果，`outResultIndex` 标识 OUT 结果，`outValues` 按参数声明顺序提供输出值。驱动使用 `SERVER_PS_OUT_PARAMS` 识别输出结果，不创建会话变量，也不会改用文本 `CALL`。OUT 结果被截断、行数未知或字段不匹配时会报错；普通结果集仍可能返回 `truncated = true`，调用方应逐个检查 `results`。

## 文本多语句

`ConnectionConfig.multipleStatements` 默认 `false`。只有完全由应用拥有的文本脚本才应启用；它不是参数绑定、转义或 SQL 解析器。驱动把完整字符串作为一次 `COM_QUERY` 发送，不按分号拆分；已有结果集数量、字节和同步排空预算覆盖整个脚本。

任一语句返回错误都会使整个调用失败，不返回部分成功对象。已经执行的写入不会自动回滚。预处理、命名参数、游标、存储过程、长参数和 `insertRows` 不受该选项影响。

## 共同边界

- 同一连接一次只能执行一个操作；所有调用都应依次 `await`。
- 预校验失败不会发命令；已派发操作的响应丢失可能产生 `Unknown` 结果，不能自动重试写入。
- 高级能力仍受 `QueryOptions` 的结果、结果集和同步排空预算约束。
- `mysqlFeatures.deadlines`、`mysqlFeatures.session` 和 `mysqlFeatures.transactions` 分别在[取消与超时](Cancellation-and-Timeouts.md)、[连接配置与 TLS](Connections.md)和[事务](Transactions.md)中说明。
- 驱动不内置连接池。应用自行管理连接池时，必须在重置或归还连接前关闭游标和显式预处理语句。
