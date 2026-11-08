# 总览架构与源码导读

ArkDB 是 HarmonyOS 应用中的 ArkTS 数据库驱动。它负责建立连接、编码 MySQL 命令和解析结果；SQL 执行与数据存储仍由远端 MySQL 服务器完成。

下图对应 [`@arkdb/mysql` 1.1.0 源码](https://github.com/OrcaSQL-Workbench/ArkDB/tree/mysql-v1.1.0)。图中的 `core` 与 `mysql` 是源码目录；应用安装的仍是一个自包含的 `@arkdb/mysql` HAR。

## 总览图

网站在此处提供缩放、节点查找、关系与源码查看以及图片导出，也可以[独立打开交互图](https://orcasql-workbench.github.io/arkdb/architecture/explore/)。Wiki、打印和禁用 JavaScript 时保留静态图。

![ArkDB 总览架构：宿主通过公共工厂和 MySqlConnection 调用命令、协议分帧与 TCP/TLS；core 提供共享契约，取消使用独立控制会话。](assets/arkdb-architecture.svg)

[打开 SVG 原图](assets/arkdb-architecture.svg)可缩放阅读。绿色箭头是主要调用链路，粉色箭头是握手与认证，紫色虚线表示源码依赖；调用的响应沿原链路反向返回。共享核心不是单独的进程或网络服务，图中只汇总绘制一条依赖线。

取消控制会话复用下方的命令、协议和传输实现，但有自己的连接与 socket，并不和正在执行查询的会话共用一条 TCP/TLS 连接。图中的 Worker 由宿主选择、创建和清理，不是驱动自动开启的后台服务。

## 模块分工与源码入口

| 模块 | 负责什么 | 源码入口 |
| --- | --- | --- |
| 公共入口与工厂 | 从包入口导出连接、查询和高级功能接口；工厂负责创建连接、元数据接口和指标接口。 | [`mysql/Index.ets`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/Index.ets)、[`MySqlDriverFactory`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/driver/MySqlDriverFactory.ets) |
| 共享核心 `core` | 定义连接、结果、错误、超时和日志等公共能力，不包含 MySQL 协议细节。 | [`core/Index.ets`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/core/Index.ets)、[`DbConnection`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/core/src/main/ets/connection/DbConnection.ets) |
| 连接与生命周期 | `MySqlConnection` 提供公开接口；`MySqlConnectionLifecycle` 管理连接、认证、会话状态、取消和关闭。 | [`MySqlConnection`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/MySqlConnection.ets)、[`MySqlConnectionLifecycle`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/connection/MySqlConnectionLifecycle.ets) |
| 命令调度与高级功能 | `MySqlCommandGate` 保证同一连接一次只执行一个操作；预处理、游标、批处理和长参数等功能分别实现。 | [`MySqlCommandGate`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/execution/MySqlCommandGate.ets)、[`MySqlFeatureFacades`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/connection/MySqlFeatureFacades.ets) |
| 握手与认证 | 读取服务器握手、协商能力、升级 TLS，并处理 MySQL 认证插件。 | [`MySqlConnectionLifecycle`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/connection/MySqlConnectionLifecycle.ets)、[`HandshakeResponse`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/auth/HandshakeResponse.ets) |
| 命令与结果 | 文本查询和预处理查询共用结果预算、截断处理和类型转换。 | [`Query.ets`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/command/Query.ets)、[`ResultStream`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/command/ResultStream.ets)、[`PreparedExecutor`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/features/prepared/PreparedExecutor.ets) |
| 协议与传输 | `PacketChannel` 处理 MySQL 数据包；`TcpTransport` 使用 HarmonyOS NetworkKit 建立 TCP/TLS 连接并收发字节。 | [`PacketChannel`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/protocol/PacketChannel.ets)、[`TcpTransport`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/transport/TcpTransport.ets) |
| 元数据与指标 | 元数据和指标接口借用现有连接执行查询。 | [`MySqlMetadataProvider`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/features/metadata/MySqlMetadataProvider.ets)、[`MySqlServerMetricsProvider`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/features/metrics/MySqlServerMetricsProvider.ets) |
| 查询取消 | 使用独立控制连接发送 `KILL QUERY`，避免与正在读取结果的连接共用命令通道。 | [`MySqlControlConnectionFactory`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/connection/MySqlControlConnectionFactory.ets)、[`MySqlExecutionController`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/mysql/src/main/ets/mysql/execution/MySqlExecutionController.ets) |

## 建立连接时发生什么

`MySqlDriverFactory.create()` 或 `createConnection()` 只创建连接对象；真正的网络操作从 `connect()` 开始。

1. `ConnectionDeadline` 为 TCP 建连、握手、可选 TLS、认证及初始会话设置提供同一个剩余时间预算，不是每一步重新开始计时。
2. 连接读取服务器握手，取得能力、认证插件和连接 ID。需要 TLS 时，先通过 `PacketChannel` 发送 `SSLRequest`，再由 `TcpTransport` 原地升级已有 TCP socket，随后发送认证响应。
3. 认证成功后设置字符集、默认数据库、自动提交和可选会话参数，随后连接进入 `Ready`。连接失败时不会自动重连或重放命令。

TLS 是否启用以及是否验证服务器身份取决于连接配置，具体策略见[连接配置与 TLS](Connections.md)。

## 查询与结果怎样流动

主链路是 `MySqlConnection → 命令实现 → PacketChannel → TcpTransport → MySQL`。服务器返回的字节会先重组成 MySQL 数据包，再解析为列、行和执行状态。

`query()` 与 `queryStream()` 共用结果解析流程。`query()` 收集有界结果，`queryStream()` 按 `onResultStart → onRows → onResultEnd` 的顺序把数据交给应用。预处理、命名参数、批处理、存储过程和只读游标也使用相同的结果预算与类型转换规则。

读取达到行数或字节上限，不等于服务器已经停止执行。解析器会按排空预算继续同步协议，或经截断回调请求取消；无法恢复同步时不能把连接当作可复用。`BIGINT` 映射为 `bigint`，`DECIMAL` 和日期时间保留字符串，二进制值保留 `Uint8Array`，避免在驱动层擅自丢失精度或解释时区。

事务同样通过当前连接发送命令。事务回调结束后，会话对象立即失效；驱动会等待回调中的操作完成，再提交或回滚。读取事务状态前应先检查 `known` 或 `statusKnown`。

继续阅读[查询、结果与流式读取](Queries.md)、[有界流式读取](Streaming.md)和[事务](Transactions.md)。

## 为什么取消需要另一条连接

查询会话正在等待服务器结果，不能同时塞入另一个普通命令。连接级 `features.cancellation.cancel()` 因而在当前执行处于 `Querying` 时创建独立控制会话，等待原查询完成派发，并再次核对执行序号后，才发送针对该连接 ID 的 `KILL QUERY`。

控制请求未结束时，原连接拒绝开始下一条命令；关闭也要等待控制清理。取消返回 `Requested` 只说明请求被接受，仍要等待原操作，并检查 `ConnectionReuse`。如果取消已派发但结果无法确认，实现会关闭并永久停用目标连接，避免延迟到达的 `KILL QUERY` 误伤后续查询，而不是自动重试 SQL。

取消、超时与服务端执行结果的区别见[取消与超时](Cancellation-and-Timeouts.md)。

## 源码目录与安装包

源码仓库将公共契约放在 `core`，将 MySQL 实现放在 `mysql`。构建时两部分会一起编译到一个 `@arkdb/mysql` HAR 中，因此应用只需安装这一个包。

`CoreDbConnection` 等类型用于需要通用连接抽象的集成；预处理、游标和存储过程等 MySQL 专用能力仍通过 `mysqlFeatures` 提供。

应用仍负责凭据、Worker 消息、连接串行使用和关闭。线程边界见 [Worker 集成](Worker-Integration.md)，接口说明见[公共接口与错误处理](API-Reference.md)。
