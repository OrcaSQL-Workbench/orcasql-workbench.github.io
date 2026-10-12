# 用户文档

本指南介绍 OrcaSQL Workbench 0.1.0 的连接管理、SQL 编辑执行、结果查看与本地工作数据管理。应用面向 HarmonyOS NEXT，当前连接选择器提供 **MySQL**。

PostgreSQL、SQL Server、Oracle、SQLite、MongoDB 和 Redis 尚未作为可用引擎提供，不能将它们视为当前版本已支持的连接类型。

## 阅读入口

| 文档 | 内容 |
| --- | --- |
| [入门指南](Getting-Started.md) | 准备连接信息，建立第一个 MySQL 连接并进入查询编辑器 |
| [连接管理与 TLS](Connections.md) | 连接字段、测试与保存、TLS 模式和证书文件 |
| [SQL 编辑与执行](SQL-Editor.md) | 选择连接和数据库，执行、停止及处理事务 |
| [结果查看与导出](Results-and-Export.md) | 结果、消息、已加载行、复制和 CSV/JSON 导出 |
| [SQL 历史与文件](History-and-Files.md) | 执行历史、保留限制、文件保存和工作区恢复 |
| [常见问题](FAQ.md) | 当前支持范围、TLS、导出与历史记录的常见疑问 |

## 使用前的提醒

- 只连接和操作你具有合法权限的数据库。
- SQL 可能修改或删除业务数据。查看结果表格不代表整个连接是只读的。
- 根据数据库管理员提供的要求配置 TLS、证书和访问权限。
- 不要在反馈、邮件或截图中提交密码、私钥、客户数据或其他敏感信息。

数据处理和本地存储的说明见 [隐私政策](https://orcasql-workbench.github.io/privacy/)。

## 安装与版本

本网站目前没有提供安装包下载入口。安装包来源、设备兼容要求及分发渠道，以开发者正式发布的信息为准。

操作说明以 0.1.0 的简体中文界面为准；如果你使用的版本或界面不同，反馈时请注明版本和具体操作步骤。

## 文档反馈

发现错误、缺漏或过时内容，可通过 [GitHub Issues](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/issues) 提出。请说明文档页、Workbench 版本、问题现象及不含敏感数据的操作步骤。
