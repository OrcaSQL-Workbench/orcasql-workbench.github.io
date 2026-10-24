# 兼容性与升级

本手册介绍 **`@arkdb/mysql` 1.0.2 工程预览版**，接口与示例按该 Release 的 HAR、包内指南及[对应源码 f532d0c37adf](https://github.com/OrcaSQL-Workbench/ArkDB/tree/f532d0c37adf4dbba7a1a313679f0024822ed752)编写，不把开发分支中的版本号当作已经发布。

本页内容：[版本和平台](#版本和平台)、[支持范围](#支持范围)、[升级 HAR](#升级-har)、[接口兼容](#接口兼容)、[验证范围](#验证范围)。

## 版本和平台

| 项目 | 要求或状态 |
| --- | --- |
| 当前手册版本 | [MySQL 1.0.2 工程预览](https://github.com/OrcaSQL-Workbench/ArkDB/releases/tag/mysql-v1.0.2) |
| 包形式 | 使用规范化 OHM URL 的字节码 HAR，包含共享 core 1.0.0 源码编译产物 |
| 目标 | HarmonyOS 6.1.1 / API 24，tablet 和 2in1 |
| 安装方式 | 从 GitHub Releases 下载一个 HAR，在应用模块中以本地文件依赖安装 |
| 旧版 | [1.0.1 Release](https://github.com/OrcaSQL-Workbench/ArkDB/releases/tag/mysql-v1.0.1)和[对应包指南](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.0.1/mysql/README.md) |

1.0.1 的 tag 和发行文件不因后续修改而替换。重查旧包时，用它自己的指南和同版示例，不套用当前源码的构建路径。

原来的[事务、取消与超时](Transactions-and-Cancellation.md)入口仍保留，旧书签可以继续使用；完整示例已分别放到事务和取消指南中。

## 支持范围

MySQL 已实现文本协议查询、认证、TCP/TLS、有界结果、事务、元数据、取消原语和服务器指标。MariaDB 仍为实验性支持，服务器指标不支持 MariaDB。

目前没有 PostgreSQL 驱动、预处理语句、参数绑定、连接池或自动管理的 Worker。`ServerFamily.PostgreSQL` 只是保留枚举值；共享 core 是源码组织，不是第二个需要安装的包。

没有实机验证记录的服务器版本、设备或 TLS 组合，不应当写成已经兼容。应用需要按自己的目标环境验收，不能从“协议已实现”推导出完整的兼容矩阵。

## 升级 HAR

1. 从同一新 Release 取得 HAR、校验文件和清单，先校验摘要。
2. 在应用中替换选定的 HAR，更新模块的文件依赖路径，恢复 OHPM 依赖并重新构建。
3. 检查自己使用的接口、Worker 消息格式、TLS 配置、结果截断和错误处理。
4. 在目标设备和服务器上验证实际业务需要的操作，再替换已运行的版本。

不要把新 HAR 与旧校验文件混用，也不要为升级添加 core 依赖或源码 override。当前没有自动重连重放机制；升级不改变应用处理不确定写入的责任。

## 接口兼容

1.0.2 保留既有的非泛型 MySQL `DbDriverFactory`、完整 `DbConnection`、句柄式取消方法和原生结果类型。已有调用方不需要被迫改成能力查找或泛型工厂。

通用集成另用 `CoreDbConnection`、`CoreDbDriverFactory`、`CoreDbExecutionController`、`CoreMetadataProvider` 及相应 `Core...` 结果类型。它们不是对原名称的替换。两条路径都从 `@arkdb/mysql` 导入，详见[公共接口](API-Reference.md)。

源码兼容也不等于可以不恢复依赖、不重建应用。多个独立构建的驱动 HAR 是否共享运行时构造器，需要另外验证，不能从单个 HAR 的行为推断。

## 验证范围

ArkTS 编译、离线协议/生命周期测试、实际 HAR 的安装与示例编译，分别覆盖不同问题。它们不能代替真实设备上的网络、平台信任、认证、事务、取消竞争和连接复用测试。

公开可下载、OHPM 注册表可获取和生产适用性也是不同状态。本手册使用 GitHub Release 的 HAR 安装方式，不要求 OHPM 发布账号。

维护者的具体验证与发行步骤见[构建、示例与发行](Building-and-Releasing.md)，应用接入从[快速开始](Getting-Started.md)继续。
