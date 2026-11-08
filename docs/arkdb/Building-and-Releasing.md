# 构建、示例与发行

本页适合需要从源码构建驱动、运行官方示例或参与发布的开发者。普通应用请直接[安装发布的 HAR](Getting-Started.md)。

修改驱动前，先看[总览架构与源码导读](Architecture.md)，区分源码中的 `core` / `mysql` 分层、单 HAR 交付和宿主负责的 Worker。

## 本机工具链

驱动源码的构建基线是 Node.js `>=22.19.0`、DevEco Studio 6.1.1.300 和 HarmonyOS API 24。仓库不下载或重新分发 SDK。

环境变量、构建命令和产物位置见 ArkDB 的[构建指南](https://github.com/OrcaSQL-Workbench/ArkDB/blob/main/docs/building-drivers.md)。需要构建与本手册一致的版本时，请使用 [1.1.0 源码](https://github.com/OrcaSQL-Workbench/ArkDB/tree/mysql-v1.1.0)。

## 运行 Worker 示例

示例是完整 Stage 应用，使用构建好的 HAR，并包含页面、Worker、DTO 和连接清理逻辑。

运行步骤见[示例说明](https://github.com/OrcaSQL-Workbench/ArkDB/blob/mysql-v1.1.0/examples/mysql-client/README.md)。准备好匹配的 HAR 后，用 DevEco Studio 打开项目并配置本地调试签名。

把同样的结构接入自己的应用时，看 [Worker 集成](Worker-Integration.md)，不要复制示例的构建依赖到普通应用。

## 区分验证层次

| 检查 | 能说明什么 |
| --- | --- |
| 不需要 SDK 的工具测试 | 包结构和公共接口是否符合项目约束 |
| ArkTS 编译与原生测试 | 源码能否编译，离线协议与生命周期测试是否通过 |
| HAR 消费检查 | 发布包能否安装，包内示例和样例 HAP 能否编译 |
| 目标设备测试 | 实际网络、证书、认证、事务、取消和连接复用是否符合预期 |

本地检查不能替代目标设备测试。应用侧需要验证的项目见[兼容性与升级](Compatibility-and-Upgrading.md#验证范围)。

## 本机构建，GitHub Release 分发

HAR 由配置好 HarmonyOS SDK 的开发环境构建。GitHub Actions 不安装 HarmonyOS SDK，也不会自动生成发布包。

版本准备、上传和下载校验见[发布流程](https://github.com/OrcaSQL-Workbench/ArkDB/blob/main/docs/releasing.md)。已经发布的同名文件不应被覆盖。应用通过本地 HAR 安装时不依赖 OHPM 发布。
