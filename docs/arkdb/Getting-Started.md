# 下载与快速接入

普通使用者只需下载驱动 HAR 并将它加入兼容的 HarmonyOS 项目，不需要克隆 ArkDB、安装其 npm 维护依赖或拥有 OHPM 发布账号。

## 下载同一版本的资产

当前已发布的 [MySQL 工程预览 mysql-v1.0.1](https://github.com/OrcaSQL-Workbench/ArkDB/releases/tag/mysql-v1.0.1)提供以下文件：

| 文件 | 用途 |
| --- | --- |
| [arkdb-mysql-1.0.1.har](https://github.com/OrcaSQL-Workbench/ArkDB/releases/download/mysql-v1.0.1/arkdb-mysql-1.0.1.har) | 要安装的驱动 |
| [arkdb-mysql-1.0.1.har.sha256](https://github.com/OrcaSQL-Workbench/ArkDB/releases/download/mysql-v1.0.1/arkdb-mysql-1.0.1.har.sha256) | HAR 的 SHA-256 |
| [arkdb-mysql-1.0.1.manifest.json](https://github.com/OrcaSQL-Workbench/ArkDB/releases/download/mysql-v1.0.1/arkdb-mysql-1.0.1.manifest.json) | 包身份、平台、源码身份、文件大小和摘要 |

在下载目录检查：

```powershell
Get-FileHash -Algorithm SHA256 .\arkdb-mysql-1.0.1.har
Get-Content .\arkdb-mysql-1.0.1.har.sha256
```

两者的 SHA-256 必须相同；不一致就停止安装，重新核对来源。不要把不同 Release 的 HAR、校验文件或清单混在一起。当前 HAR 是面向 HarmonyOS 6.1.1 / API 24、tablet 和 2in1 的字节码包，不能假定旧版 SDK 可消费。

## 加入应用模块

从应用的消费模块目录（例如 `MyApp\entry`）运行：

```powershell
ohpm install C:\Downloads\arkdb-mysql-1.0.1.har
```

也可以将 HAR 保存在 `MyApp\libs`，在 `MyApp\entry\oh-package.json5` 中声明：

```json5
{
  "dependencies": {
    "@arkdb/mysql": "file:../libs/arkdb-mysql-1.0.1.har"
  }
}
```

文件路径相对于模块的 `oh-package.json5`，不是相对于 ArkDB 仓库。恢复依赖后重建应用，不要把 ArkDB 源码模块加入应用的模块注册表。当前未发布到 OHPM，因此不要用未上架的注册表包替代已下载的 HAR。

确认应用合并后的权限包含 `ohos.permission.INTERNET`。这不是运行时弹窗权限；获取证书文件所需的权限和凭据存储由宿主应用负责。

## 首次连接、查询和关闭

下面的函数应在应用自行管理的 Worker 中执行，而不是直接放进 ArkUI 事件回调：

```typescript
import {
  ConnectionConfig, DbConnection, MySqlDriverFactory,
  QueryResult, SslMode
} from '@arkdb/mysql';

export async function readVersion(host: string, user: string, password: string): Promise<QueryResult> {
  const config = new ConnectionConfig();
  config.host = host;
  config.user = user;
  config.ssl.mode = SslMode.VERIFY_IDENTITY;

  const issues = config.validate();
  if (issues.length > 0) {
    throw issues[0];
  }

  const connection: DbConnection = new MySqlDriverFactory().createConnection(config, password);
  try {
    await connection.connect();
    return await connection.query('SELECT VERSION() AS version');
  } finally {
    await connection.close();
  }
}
```

密码单独传给 `createConnection`，不放进 `ConnectionConfig`，也不写进日志。`VERIFY_IDENTITY` 同时要求证书链和主机名验证；请使用证书匹配的服务器名称。自定义 CA 见[连接配置与 TLS](Connections.md)。

`close()` 也可能失败，上面的最短示例会传播关闭错误。如果业务必须同时保留查询错误和清理错误，应分别保存并报告，不能让清理错误掩盖主要失败；[完整 Worker 示例](https://github.com/OrcaSQL-Workbench/ArkDB/tree/main/examples/mysql-client)包含这类处理。

## 接入 Worker

已有 Stage 应用需要在模块的 `build-profile.json5` 中注册 Worker：

```json5
{
  "buildOption": {
    "sourceOption": {
      "workers": ["./src/main/ets/workers/mysql.worker.ets"]
    }
  }
}
```

宿主通过 `@kit.ArkTS` 的 `worker.ThreadWorker` 创建该入口；示例路径为 `entry/ets/workers/mysql.worker.ets`。Worker 内拥有连接及其生命周期，UI 只收发有界、扁平的 DTO。不要跨线程传递连接、错误对象、`QueryResult` 或 UI 引用。Worker 入口文件不导出声明，共享 DTO 放在独立模块中。

一条连接上的查询、元数据和指标调用必须串行。结束页面时先请求清理，再使用有界的强制终止兜底；强制终止 Worker 不是服务器端取消成功的证据。

下一步阅读[查询、结果与流式读取](Queries.md)，或按[构建、示例与发行](Building-and-Releasing.md)运行完整示例。
