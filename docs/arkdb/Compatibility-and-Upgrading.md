# 兼容性与升级

本手册介绍 **`@arkdb/mysql` 1.1.0 工程预览版**，接口与示例按该 Release 的 HAR、包内指南及[对应源码 126f786f9341](https://github.com/OrcaSQL-Workbench/ArkDB/tree/126f786f93416f7d6894d842bf85aa26c7accbe4)编写，不把开发分支中的版本号当作已经发布。

本页内容：[版本和平台](#版本和平台)、[支持范围](#支持范围)、[升级 HAR](#升级-har)、[接口兼容](#接口兼容)、[验证范围](#验证范围)。

## 版本和平台

| 项目 | 要求或状态 |
| --- | --- |
| 当前手册版本 | [MySQL 1.1.0 工程预览](https://github.com/OrcaSQL-Workbench/ArkDB/releases/tag/mysql-v1.1.0) |
| 包形式 | 使用规范化 OHM URL 的字节码 HAR，包含共享 core 1.1.0 源码编译产物 |
| 目标 | HarmonyOS 6.1.1 / API 24，tablet 和 2in1 |
| 安装方式 | 从 GitHub Releases 下载一个 HAR，在应用模块中以本地文件依赖安装 |
| 旧版 | [1.0.2 Release](https://github.com/OrcaSQL-Workbench/ArkDB/releases/tag/mysql-v1.0.2)、[1.0.1 Release](https://github.com/OrcaSQL-Workbench/ArkDB/releases/tag/mysql-v1.0.1) |

旧版 tag 和发行文件不因后续修改而替换。重查旧包时，用它自己的包内指南和同版示例，不套用 1.1.0 的能力或构建路径。

原来的[事务、取消与超时](Transactions-and-Cancellation.md)入口仍保留，旧书签可以继续使用；完整示例已分别放到事务和取消指南中。

## 支持范围

MySQL 已实现文本协议查询、认证、TCP/TLS、有界结果、类型化预处理和命名参数、批处理、受限多行 INSERT、只读服务端游标、长参数、二进制存储过程 OUT/INOUT、事务回调与保存点、语句截止时间、会话重置、元数据、取消原语、执行观察和服务器指标。

目前没有 PostgreSQL 驱动、连接池或自动管理的 Worker。`ServerFamily.PostgreSQL` 只是保留枚举值；共享 core 是源码组织，不是第二个需要安装的包。驱动不会自动重连、故障转移或重放 SQL。

没有实机验证记录的服务器版本、设备或 TLS 组合，不应当写成已经兼容。应用需要按自己的目标环境验收，不能从“协议已实现”推导出完整的兼容矩阵。

## 升级 HAR

1. 从同一新 Release 取得 HAR、校验文件和清单，先校验摘要。
2. 在应用中替换选定的 HAR，更新模块的文件依赖路径，恢复 OHPM 依赖并重新构建。
3. 检查自己使用的接口、Worker 消息格式、TLS 配置、结果截断和错误处理。
4. 在目标设备和服务器上验证实际业务需要的操作，再替换已运行的版本。

不要把新 HAR 与旧校验文件混用，也不要为升级添加 core 依赖或源码 override。当前没有自动重连重放机制；升级不改变应用处理不确定写入的责任。

## 接口兼容

1.1.0 保留 1.0.2 的包根公共契约，包括非泛型 MySQL `DbDriverFactory`、完整 `DbConnection`、句柄式取消方法和原生结果类型。新增能力通过可选的 `mysqlFeatures` 和新增类型提供，已有调用方不需要被迫改成能力查找或泛型工厂。

通用集成另用 `CoreDbConnection`、`CoreDbDriverFactory`、`CoreDbExecutionController`、`CoreMetadataProvider` 及相应 `Core...` 结果类型。它们不是对原名称的替换。两条路径都从 `@arkdb/mysql` 导入，详见[公共接口](API-Reference.md)。

源码兼容也不等于可以不恢复依赖、不重建应用。多个独立构建的驱动 HAR 是否共享运行时构造器，需要另外验证，不能从单个 HAR 的行为推断。

## 验证范围

1.1.0 的 Release 记录了 828 个驱动测试、8 个包指南示例、20 个本地样例用例、实际 HAR 消费和样例 HAP 编译；单 HAR 自包含运行时检查通过。它们分别覆盖源码、离线协议/生命周期和归档消费问题，不能代替真实设备上的网络、平台信任、认证、事务、取消竞争和连接复用测试。

该发行没有建立真实设备、实时网络、TLS 或取消竞争证据，也没有声明 OHPM 注册表可获取或生产认证。公开可下载、注册表可获取和生产适用性是不同状态。本手册使用 GitHub Release 的 HAR 安装方式，不要求 OHPM 发布账号。

维护者的具体验证与发行步骤见[构建、示例与发行](Building-and-Releasing.md)，应用接入从[快速开始](Getting-Started.md)继续。
