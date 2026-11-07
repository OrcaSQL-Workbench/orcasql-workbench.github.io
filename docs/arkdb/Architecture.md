# 总览架构与源码导读

ArkDB 是 HarmonyOS 应用里的 ArkTS 数据库驱动，不是本地数据库引擎。它在设备上管理连接、编码命令和解码结果；SQL 的执行与数据存储仍在远端 MySQL。当前只有 MySQL 实现，不需要 Node.js、WebView 或原生 MySQL 客户端参与运行。

本页依据 MySQL 1.1.0 的 ArkDB 源码提交 [126f786](https://github.com/OrcaSQL-Workbench/ArkDB/tree/126f786f93416f7d6894d842bf85aa26c7accbe4) 绘制。图中的 `core` 与 `mysql` 是源码分层，应用安装的仍是一个包含共享核心代码的 `@arkdb/mysql` HAR；接入方式见[下载与快速接入](Getting-Started.md)。

## 总览图

网站在此处提供缩放、节点查找、关系与源码查看以及图片导出，也可以[独立打开交互图](https://orcasql-workbench.github.io/arkdb/architecture/explore/)。Wiki、打印和禁用 JavaScript 时保留静态图。

![ArkDB 总览架构：宿主通过公共工厂和 MySqlConnection 调用命令、协议分帧与 TCP/TLS；core 提供共享契约，取消使用独立控制会话。](assets/arkdb-architecture.svg)

[打开 SVG 原图](assets/arkdb-architecture.svg)可缩放阅读。绿色箭头是主要调用链路，粉色箭头是握手与认证，紫色虚线表示源码依赖；调用的响应沿原链路反向返回。共享核心不是单独的进程或网络服务，图中只汇总绘制一条依赖线。

取消控制会话复用下方的命令、协议和传输实现，但有自己的连接与 socket，并不和正在执行查询的会话共用一条 TCP/TLS 连接。图中的 Worker 由宿主选择、创建和清理，不是驱动自动开启的后台服务。

## 模块分工与源码入口

| 模块 | 负责什么 | 源码入口 |
| --- | --- | --- |
| 公共入口与工厂 | 从包根导出稳定的 MySQL 名称、1.1.0 高级能力及不同名称的 `Core...` 契约；工厂创建普通或带执行观察的连接和 Provider。 | [`mysql/Index.ets`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/Index.ets#L1-L110)、[`MySqlDriverFactory`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/driver/MySqlDriverFactory.ets#L21-L58) |
| 共享核心 `core` | 定义最小连接、可选 `features`、结果预算与错误模型、失败组合、连接时限和日志；不包含 MySQL 配置、SQL、认证或线协议。 | [`core/Index.ets`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/core/Index.ets#L1-L34)、[`DbConnection`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/core/src/main/ets/connection/DbConnection.ets#L11-L48) |
| 连接外观与生命周期 | `MySqlConnection` 保留公共/受保护接口并装配 generic/MySQL 能力；`MySqlConnectionLifecycle` 拥有连接、认证、会话重置、状态、取消和关闭流程。 | [`MySqlConnection`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/MySqlConnection.ets#L136-L217)、[`MySqlConnectionLifecycle`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/connection/MySqlConnectionLifecycle.ets#L71-L233) |
| 命令所有权与功能模块 | `MySqlCommandGate` 为每个物理会话提供单一 command owner、serial、generation 和阶段；feature facade 延迟解析 prepared、cursor、long-data、named、batch、insert 与 procedure 实现。 | [`MySqlCommandGate`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/execution/MySqlCommandGate.ets#L3-L126)、[`MySqlFeatureFacades`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/connection/MySqlFeatureFacades.ets#L44-L176) |
| 握手与认证 | 生命周期读取握手、协商能力、发送 `SSLRequest`、原地升级 TLS，并处理 `mysql_native_password` 与 `caching_sha2_password`。 | [`connectOwned()`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/connection/MySqlConnectionLifecycle.ets#L742-L850)、[`HandshakeResponse`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/auth/HandshakeResponse.ets#L5-L82) |
| 命令与结果 | 文本和预处理路径共用结果流、预算、排空与类型映射；prepared、游标和其他 feature 在自己的目录中拥有协议生命周期。 | [`Query.ets`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/command/Query.ets#L25-L35)、[`ResultStream`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/command/ResultStream.ets#L39-L119)、[`PreparedExecutor`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/features/prepared/PreparedExecutor.ets#L36-L126) |
| 协议与传输 | `PacketChannel` 管分帧、序号、大包和写入截止时间；`TcpTransport` 使用 HarmonyOS `@kit.NetworkKit` 管 TCP/TLS、有界接收和关闭。 | [`PacketChannel`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/protocol/PacketChannel.ets#L33-L154)、[`TcpTransport`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/transport/TcpTransport.ets#L63-L200) |
| 元数据与指标 | feature Provider 组织 MySQL 查询，并通过绑定连接的 `query()` 或 `queryStream()` 执行；它们不是另一套网络客户端。 | [`MySqlMetadataProvider`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/features/metadata/MySqlMetadataProvider.ets#L13-L78)、[`MySqlServerMetricsProvider`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/features/metrics/MySqlServerMetricsProvider.ets#L40-L96) |
| 取消控制 | 生命周期创建策略受限的独立控制连接并拥有取消收敛；低层 `MySqlExecutionController` 只发送经过验证的 `KILL QUERY`。 | [`MySqlControlConnectionFactory`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/connection/MySqlControlConnectionFactory.ets#L4-L20)、[`MySqlExecutionController`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/execution/MySqlExecutionController.ets#L9-L53) |

## 建立连接时发生什么

`MySqlDriverFactory.create()` 或 `createConnection()` 创建公共 `MySqlConnection` 外观，并在构造期装配 generic/MySQL feature facade；真正的网络操作从 `connect()` 委托给 lifecycle 后开始。

1. `ConnectionDeadline` 为 TCP 建连、握手、可选 TLS、认证及初始会话设置提供同一个剩余时间预算，不是每一步重新开始计时。
2. 连接读取服务器握手，取得能力、认证插件和连接 ID。需要 TLS 时，先通过 `PacketChannel` 发送 `SSLRequest`，再由 `TcpTransport` 原地升级已有 TCP socket，随后发送认证响应。
3. 认证成功后应用字符集、默认数据库、autocommit 和可选会话时区/SQL mode，随后连接进入 `Ready`。失败路径使会话状态失效，并中止传输；不会自动重连或重放命令。

TLS 是否启用及是否验证身份取决于配置，不由图中的 TLS 字样保证。具体策略见[连接配置与 TLS](Connections.md)；连接时限实现见 [`ConnectionDeadline`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/core/src/main/ets/connection/ConnectionDeadline.ets#L24-L89)。

## 查询与结果怎样流动

主链路是 `MySqlConnection → lifecycle / command gate → text 或 feature 模块 → PacketChannel → TcpTransport → MySQL`。返回时，字节先重组成协议包，再进入共享结果流或对应 feature 的二进制解码器，而不是把 socket 数据直接交给应用。

`query()` 与 `queryStream()` 共用 `command/ResultStream.ets`。前者使用缓冲 collector 收集结果；后者等待 `onResultStart → onRows → onResultEnd` 回调，由应用逐块消费。预处理、命名参数、批处理、存储过程和只读游标复用相同的预算、终止符与失败组合规则，但各自拥有明确的 statement/cursor 生命周期。MySQL 原生回调与通用 core 回调之间仍有[适配层](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/mysql/src/main/ets/mysql/model/MySqlQueryStream.ets#L66-L138)，并非两套网络实现。

读取达到行数或字节上限，不等于服务器已经停止执行。解析器会按排空预算继续同步协议，或经截断回调请求取消；无法恢复同步时不能把连接当作可复用。`BIGINT` 映射为 `bigint`，`DECIMAL` 和日期时间保留字符串，二进制值保留 `Uint8Array`，避免在驱动层擅自丢失精度或解释时区。

事务同样走这条命令链路。通用 begin/commit/rollback 和 MySQL 回调事务共享 command gate；回调 facade 在结束后失效，并在提交或回滚前等待 owned 取消与清理。连接从服务器响应更新会话状态；必须先确认 `known` / `statusKnown`，不能把无效状态中的默认值当作服务器事实。

继续阅读[查询、结果与流式读取](Queries.md)、[有界流式读取](Streaming.md)和[事务](Transactions.md)。

## 为什么取消需要另一条连接

查询会话正在等待服务器结果，不能同时塞入另一个普通命令。连接级 `features.cancellation.cancel()` 因而在当前执行处于 `Querying` 时创建独立控制会话，等待原查询完成派发，并再次核对执行序号后，才发送针对该连接 ID 的 `KILL QUERY`。

控制请求未结束时，原连接拒绝开始下一条命令；关闭也要等待控制清理。取消返回 `Requested` 只说明请求被接受，仍要等待原操作，并检查 `ConnectionReuse`。如果取消已派发但结果无法确认，实现会关闭并永久停用目标连接，避免延迟到达的 `KILL QUERY` 误伤后续查询，而不是自动重试 SQL。

取消、超时与服务端执行结果的区别见[取消与超时](Cancellation-and-Timeouts.md)。

## 源码分层不等于安装依赖

维护源码时，`mysql` 通过 `@arkdb/core` 的公共入口依赖共享核心。打包工具将依赖闭包中的源码各复制一次，通过 AST 改写模块引用，在临时交付模块里编译成一个 HAR，并移除交付包对开发态 core 包的外部依赖。实现见 [`deliveryPlan()`](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/tools/workspace/delivery-workspace.mjs#L14-L31) 和[交付工作区组装](https://github.com/OrcaSQL-Workbench/ArkDB/blob/126f786f93416f7d6894d842bf85aa26c7accbe4/tools/workspace/delivery-workspace.mjs#L114-L160)。`tools`、Node.js 与 DevEco 构建工具不参与驱动运行。

core 的最小连接只要求连接、查询、关闭及状态；流式、事务、元数据等是可选能力，不要求未来的适配器伪造不支持的方法。`@arkdb/mysql` 保留既有 MySQL 名称，并用 `CoreDbConnection` 等不同名称导出通用契约；MySQL 的预处理、游标和其他高级能力留在 adapter 内，不把数据库专属语义推入 core。有共享接口不代表已经实现 PostgreSQL 或连接池。

宿主仍负责凭据、同一连接的调用串行化、Worker 消息和连接清理。完整的线程边界见 [Worker 集成](Worker-Integration.md)，接口边界见[公共接口与错误处理](API-Reference.md)；需要修改驱动或增加实现时，再读[构建、示例与发行](Building-and-Releasing.md)。
