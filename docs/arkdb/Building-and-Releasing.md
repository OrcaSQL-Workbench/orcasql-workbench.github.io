# 构建、示例与发行

这页给需要编译驱动、准备源码示例或维护发行的人。普通应用直接[安装发布的 HAR](Getting-Started.md)，不需要先克隆仓库或安装 npm 维护依赖。

修改驱动前，先看[总览架构与源码导读](Architecture.md)，区分源码中的 `core` / `mysql` 分层、单 HAR 交付和宿主负责的 Worker。

## 本机工具链

驱动源码的构建基线是 Node.js `>=22.19.0`、DevEco Studio 6.1.1.300 和 HarmonyOS API 24。仓库不下载或重新分发 SDK。

环境变量、驱动选择、单 HAR 构建与产物位置以 ArkDB 的[构建指南](https://github.com/OrcaSQL-Workbench/ArkDB/blob/main/docs/building-drivers.md)为准。维护当前分支时读当前指南；重查 1.0.2 发布包时用[对应源码版本](https://github.com/OrcaSQL-Workbench/ArkDB/tree/f532d0c37adf4dbba7a1a313679f0024822ed752)。

## 运行 Worker 示例

示例是完整 Stage 应用，不是驱动内部自动管理的 Worker 客户端。它消费实际 HAR，提供页面、Worker、DTO 和清理逻辑。

运行步骤集中在[示例 README](https://github.com/OrcaSQL-Workbench/ArkDB/blob/f532d0c37adf4dbba7a1a313679f0024822ed752/examples/mysql-client/README.md)。准备好匹配的 HAR 后，用 DevEco Studio 打开项目，配置自己的本地调试签名。仓库不附带签名身份。

把同样的结构接入自己的应用时，看 [Worker 集成](Worker-Integration.md)，不要复制示例的构建依赖到普通应用。

## 区分验证层次

| 检查 | 能说明什么 |
| --- | --- |
| 不需要 SDK 的工具测试 | 工具、包和接口约束是否符合要求 |
| ArkTS 编译与原生测试 | 当前源码是否能编译，离线契约与协议行为是否通过 |
| 实际 HAR 消费检查 | 选定包的安装、导出、包内示例和样例 HAP 能否编译 |
| 公开下载验收 | 下载的发行文件是否一致，能否被独立消费者使用 |
| 目标设备/服务器测试 | 实际网络、平台信任、认证、事务、取消和复用行为 |

前几项不能替代最后一项。应用开发者需要了解的限制在[兼容性与升级](Compatibility-and-Upgrading.md#验证范围)，维护命令在[发行流程](https://github.com/OrcaSQL-Workbench/ArkDB/blob/main/docs/releasing.md)中。

## 本机构建，GitHub Release 分发

维护者在自己的开发电脑上构建并核对候选包，再经授权上传同一份字节。GitHub Actions 不安装 HarmonyOS SDK，也不会因为推送 tag 自动编译 HAR。

准备、上传、部分上传恢复和下载验收，统一遵循[发行流程](https://github.com/OrcaSQL-Workbench/ArkDB/blob/main/docs/releasing.md)。不要重新发行或覆盖已经发布的同名资产。OHPM 发布是另一条可选路线，不是本地 HAR 安装的前提。

准备增加新驱动时，先读[共享驱动契约](https://github.com/OrcaSQL-Workbench/ArkDB/blob/main/docs/driver-contracts.md)；协议测试的上游来源记录在[测试来源说明](https://github.com/OrcaSQL-Workbench/ArkDB/blob/main/docs/protocol-test-provenance.md)中。新驱动需要自己的实现和验收，增加一个配置项不代表已经支持它。
