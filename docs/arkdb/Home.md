# ArkDB 开发者手册

ArkDB 是供 HarmonyOS 应用使用的原生 ArkTS 数据库驱动。把驱动 HAR 加入项目后，就可以在应用里连接 MySQL，不需要安装 OrcaSQL Workbench，也不需要 Node.js、WebView 或原生 MySQL 客户端。

这份手册介绍 **MySQL 1.0.2 工程预览版**。第一次接入请从[下载与快速接入](Getting-Started.md)开始；已有应用需要安排线程和消息传递时，看 [Worker 集成](Worker-Integration.md)。

## 当前提供什么

| 项目 | 说明 |
| --- | --- |
| 驱动 | `@arkdb/mysql`，一个包含共享核心代码的 HAR，不需要另外安装 core |
| 目标平台 | HarmonyOS 6.1.1 / API 24，tablet 和 2in1 |
| 下载 | [MySQL 1.0.2 Release](https://github.com/OrcaSQL-Workbench/ArkDB/releases/tag/mysql-v1.0.2) |
| MySQL | 文本协议查询、TLS、流式结果、事务、元数据、取消和服务器指标 |
| MariaDB | 实验性支持；不支持 MariaDB 服务器指标 |

当前没有 PostgreSQL 驱动、参数绑定、预处理语句、连接池或自动管理的 Worker。工程预览也不代表已经通过目标设备与服务器的兼容性验收，详见[兼容性与升级](Compatibility-and-Upgrading.md)。

## 按任务阅读

### 开始使用

- [下载与快速接入](Getting-Started.md)：下载、校验和安装 HAR，完成第一次查询。
- [Worker 集成](Worker-Integration.md)：注册 Worker，传递消息，安排连接与页面的生命周期。

### MySQL 使用指南

- [连接配置与 TLS](Connections.md)：设置连接，使用系统信任或自定义证书。
- [查询、结果与流式读取](Queries.md)：读取普通查询结果，保留数值精度，处理多个结果集。
- [有界流式读取](Streaming.md)：逐块处理结果，限制内存占用，处理截断。
- [事务](Transactions.md)：提交、回滚，以及同时保留操作和清理错误。
- [取消与超时](Cancellation-and-Timeouts.md)：取消正在执行的查询，区分取消请求和实际执行结果。
- [元数据与服务器指标](Metadata-and-Metrics.md)：读取对象结构和监控数据。

### 参考

- [公共接口与错误处理](API-Reference.md)：查找工厂、连接、Provider 和可选能力接口。
- [配置参考](Configuration-Reference.md)：连接、TLS 和查询选项的默认值及限制。
- [数据类型与结果](Data-Types-and-Results.md)：值类型、列信息、结果集和会话状态。
- [错误与日志](Errors-and-Logging.md)：错误分类、服务器错误码和日志设置。
- [兼容性与升级](Compatibility-and-Upgrading.md)：版本、平台要求、已知限制和 HAR 升级。

### 故障排查

[故障排查与问题反馈](Troubleshooting.md)按安装、Worker、连接、证书和查询现象列出检查方法。

### 贡献与维护

需要自行编译驱动或维护发行时，再看[构建、示例与发行](Building-and-Releasing.md)。普通应用接入不需要这些步骤。

## 接入前的边界

- 应用负责 Worker、同一连接上的调用串行化、凭据保管和连接清理。驱动不会自动重连或重放 SQL。
- 新接入请明确设置 TLS 策略。默认的 `PREFERRED` 允许回退到明文，不能当作服务器身份验证。
- 当前没有参数绑定接口，不要把不可信输入拼进 SQL。
- 连接断开、等待超时或取消请求返回，都不能单独证明写入没有发生。

## 源码、示例与反馈

[ArkDB 仓库](https://github.com/OrcaSQL-Workbench/ArkDB)维护驱动源码和发行包；[Worker 示例](https://github.com/OrcaSQL-Workbench/ArkDB/tree/f532d0c37adf4dbba7a1a313679f0024822ed752/examples/mysql-client)展示一个完整应用的接入方式。Workbench 本身的使用方法在[用户文档](https://orcasql-workbench.github.io/docs/)中。

驱动问题请提交到 [ArkDB Issues](https://github.com/OrcaSQL-Workbench/ArkDB/issues)。需要准备哪些信息，见[问题反馈](Troubleshooting.md#提交问题时附上什么)。不要提交密码、私钥或客户数据。
