# 构建、示例与发行

消费应用可直接[安装已下载的 HAR](Getting-Started.md)。本页面向需要构建驱动、运行完整示例或维护发行的开发者；这些维护工具不是驱动的运行时依赖。

## 本机工具链

使用 Node.js `>=22.19.0` 和已安装的 DevEco/HarmonyOS API-24 工具链。上游提取基线为 DevEco Studio 6.1.1.300。仓库不会下载或重新分发 SDK。

Windows 默认使用 `C:\Program Files\Huawei\DevEco Studio`。其他安装位置可设置 `DEVECO_HOME`；外部 SDK 使用 `DEVECO_SDK_HOME`；显式工具入口可通过 `HARMONYOS_HVIGORW` 和 `HARMONYOS_OHPM` 指定。

在 [ArkDB 源码仓库](https://github.com/OrcaSQL-Workbench/ArkDB)根目录运行：

```powershell
npm ci --ignore-scripts
npm run restore
npm run drivers
npm run pack -- --driver mysql
```

`--driver` 选择真实注册的 HAR 模块名，不是任意文件系统路径。当前只有 `mysql` / `@arkdb/mysql`，选择尚未实现的 `pgsql` 会明确失败。增加一个矩阵项不会产生可用的 PostgreSQL 驱动。

输出为 `dist\arkdb-mysql-1.0.1.har`、同名 `.har.sha256` 和 `.manifest.json`。清单记录包身份、源码目录、源码指纹、大小和摘要；未提交候选的 `sourceClean` 为 `false`、`sourceCommit` 为 `null`，不能把当前 Git HEAD 冒充它的已审阅来源。

## 运行 Worker 示例

上游的 [examples/mysql-client](https://github.com/OrcaSQL-Workbench/ArkDB/tree/main/examples/mysql-client)是完整 Stage-model HAP，消费实际 HAR，不直接引用驱动源码：

```powershell
npm run example:prepare
npm run example:build
```

先完成上面的依赖恢复与 HAR 构建，再执行示例命令。用 DevEco Studio 打开 `examples\mysql-client`，选择兼容的 API-24 tablet/2in1 目标并配置自己的本地调试签名。仓库只生成未签名 HAP，不提供签名身份，也不声称完成设备运行。

示例在 Worker 内连接、执行固定只读查询并关闭，展示服务器版本、精确 BIGINT/DECIMAL 和 NULL。它始终验证 TLS 身份；可选 CA 文件必须已在应用沙箱内可读。UI 不持久化密码，提交后清空密码输入框。

## 区分验证层次

| 命令 | 覆盖范围 |
| --- | --- |
| `npm run check` | 不需要 SDK 的工具测试及包、接口和导入检查 |
| `npm run test:arkts` | 本地 Hypium 驱动测试 |
| `npm run test:consumer` | 针对实际 HAR 编译示例 HAP/Worker 和包内 README 示例，运行离线示例生命周期测试 |
| `npm run release:check` | 包与证据校验，以及不发布的 OHPM 检查 |
| `npm run verify` | 完整本地验证、打包、消费者检查和不发布的预检 |
| `npm run release:verify-download -- --driver mysql --tag mysql-v1.0.1` | 下载实际已发布资产，校验后安装并编译独立消费者；不回退到本地 `dist` 或驱动源码 |

编译通过、本地模拟通过、公开 HAR 可下载、OHPM 可获取和真实设备互操作是不同状态。当前工程预览不提供实机网络、TLS 或取消认证；MariaDB 还需要单独的兼容性证据。

## 本机构建，GitHub Release 分发

当前发行路线不需要专用服务器或自托管 runner。维护者在已有开发电脑上构建和验证，再单独授权上传同一份字节；GitHub Actions 只运行工具链无关的 `check`，推送 tag 不会触发云端 HAR 编译。

审阅并提交源码，按所有者批准的 Git 流程准备与包版本及干净源码提交匹配的 annotated tag 后：

```powershell
npm run release:prepare -- --driver mysql --tag mysql-v1.0.1
```

该命令运行本地验证，生成 `dist\releases\mysql-v1.0.1` 下的不可变发行集合，包括明确允许的资产和 `release-set.json`。它不提交、不推送、不创建 tag，也不发布。

远端 tag 已匹配且获得所有者明确的发行授权后，才使用单独的上传入口：

```powershell
npm run release:publish -- --driver mysql --tag mysql-v1.0.1 --confirm-publish
```

这里的 tag 仅展示当前版本的命令格式，不应重新发行或替换已发布资产。准备新版本时同步修改包版本、tag 和下载信息。上传不重新构建；同名冲突资产不能覆盖，部分上传或写入结果不确定时先核对远端状态，不盲目重试。

详细授权、恢复与验收步骤以[上游发行流程](https://github.com/OrcaSQL-Workbench/ArkDB/blob/508adf42a6d7d485fe38c84cdf5c91322adf6e6d/docs/releasing.md)为准。OHPM 上架是独立的可选分发路线，不是消费本地 HAR 的前提。
