# ArkDB 开发者手册

ArkDB 为 HarmonyOS 应用提供原生 ArkTS 数据库驱动，以不带界面的 Harmony Archive（HAR）分发。它不是独立运行的系统驱动，也不要求应用安装 OrcaSQL Workbench。运行时依赖 HarmonyOS 网络和加密 Kit，不依赖 Node.js、WebView 或原生 MySQL 客户端。

本手册面向将驱动接入自己应用的开发者。Workbench 的连接界面、编辑器和本地文件管理请阅读[用户文档](https://orcasql-workbench.github.io/docs/)。

## 当前提供什么

| 项目 | 当前状态 |
| --- | --- |
| MySQL | `@arkdb/mysql`，已提供可下载的工程预览 HAR |
| 平台 | HarmonyOS 6.1.1 / API 24，tablet 和 2in1；使用规范化 OHM URL 的字节码 HAR |
| 分发 | [GitHub Releases](https://github.com/OrcaSQL-Workbench/ArkDB/releases)；当前未发布到 OHPM |
| MariaDB | 实验性支持，不能视为已完成实机兼容性验证；服务器指标不支持 MariaDB |
| PostgreSQL、独立共享核心包 | 尚未实现 |
| 预处理语句、参数绑定、连接池、自动管理的 Worker | 尚未实现 |

MySQL 驱动提供文本协议查询、认证、TCP/TLS、有界流式结果、事务、元数据、取消原语和服务器指标。工程预览不等于生产认证；真实设备上的网络、TLS 和取消互操作证据仍未完成。应用需要自行确定目标设备、服务器版本和安全策略的验收范围。

## 按任务阅读

| 文档 | 回答的问题 |
| --- | --- |
| [下载与快速接入](Getting-Started.md) | 从哪里下载 HAR，如何校验、安装并完成首次查询 |
| [连接配置与 TLS](Connections.md) | 如何设置连接、明确 TLS 策略并提供证书 |
| [查询、结果与流式读取](Queries.md) | 如何保留 SQL 类型、限制结果并处理截断 |
| [事务、取消与超时](Transactions-and-Cancellation.md) | 如何管理提交、取消、截止时间和不确定结果 |
| [公共接口与错误处理](API-Reference.md) | 应使用哪些导出、方法、错误类别和 Provider |
| [构建、示例与发行](Building-and-Releasing.md) | 如何按驱动构建、运行 Worker 示例及准备发行 |

## 接入前的边界

- 应用拥有 Worker、命令串行化、凭据存储、证书文件访问和连接清理。驱动不会自动创建 Worker、排队并发请求、重连或重放 SQL。
- 新接入应明确选择 TLS 策略。默认 `PREFERRED` 允许回退到明文，不能把它当作服务器身份验证。
- 只通过 `@arkdb/mysql` 导入公共接口，不从包内路径导入，也不将驱动源码模块注册进消费应用。
- 当前没有参数绑定接口。不要把不可信输入拼接成 SQL，也不要把连接断开或取消失败当作写入未发生的证明。
- 反馈中不要提交密码、私钥、客户数据或含敏感信息的服务器错误原文。

## 源码、示例与反馈

[ArkDB 仓库](https://github.com/OrcaSQL-Workbench/ArkDB)维护驱动源码和发行资产；[Worker 示例](https://github.com/OrcaSQL-Workbench/ArkDB/tree/main/examples/mysql-client)展示宿主应用的职责。驱动问题请提交到 [ArkDB Issues](https://github.com/OrcaSQL-Workbench/ArkDB/issues)，附 HAR 版本、目标设备/API、服务器类型及脱敏复现步骤。

本手册与 [ArkDB Wiki](https://github.com/OrcaSQL-Workbench/ArkDB/wiki)使用[文档仓库中的同一份 Markdown](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/tree/main/docs/arkdb)。内容修正请修改这份源文件；Wiki 是单向生成的镜像，不是另一份编辑源。

接口与行为依据：ArkDB 提交 [`508adf42a6d7`](https://github.com/OrcaSQL-Workbench/ArkDB/commit/508adf42a6d7d485fe38c84cdf5c91322adf6e6d)的包指南、公共导出和构建指南。升级驱动时应一并核对这些接口与行为边界。
