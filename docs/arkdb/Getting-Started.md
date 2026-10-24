# 下载与快速接入

下面以 MySQL 1.0.2 为例，把驱动加入已有的 HarmonyOS Stage 项目。目标工具链为 HarmonyOS 6.1.1 / API 24，设备类型为 tablet 或 2in1。

只安装 HAR 即可，不需要克隆 ArkDB、安装它的 npm 依赖或准备 OHPM 发布账号。版本和支持范围见[兼容性与升级](Compatibility-and-Upgrading.md)。

## 下载同一版本的资产

打开 [mysql-v1.0.2 Release](https://github.com/OrcaSQL-Workbench/ArkDB/releases/tag/mysql-v1.0.2)，下载这三个文件：

| 文件 | 用途 |
| --- | --- |
| [arkdb-mysql-1.0.2.har](https://github.com/OrcaSQL-Workbench/ArkDB/releases/download/mysql-v1.0.2/arkdb-mysql-1.0.2.har) | 驱动包 |
| [arkdb-mysql-1.0.2.har.sha256](https://github.com/OrcaSQL-Workbench/ArkDB/releases/download/mysql-v1.0.2/arkdb-mysql-1.0.2.har.sha256) | SHA-256 校验值 |
| [arkdb-mysql-1.0.2.manifest.json](https://github.com/OrcaSQL-Workbench/ArkDB/releases/download/mysql-v1.0.2/arkdb-mysql-1.0.2.manifest.json) | 包版本、平台与来源信息 |

在下载目录检查摘要：

```powershell
Get-FileHash -Algorithm SHA256 .\arkdb-mysql-1.0.2.har
Get-Content .\arkdb-mysql-1.0.2.har.sha256
```

两个 SHA-256 必须相同。不一致时先停止安装，重新核对下载来源。HAR、校验文件和清单应来自同一 Release。

## 加入应用模块

在消费模块目录（例如 `MyApp\entry`）运行：

```powershell
ohpm install C:\Downloads\arkdb-mysql-1.0.2.har
```

如果希望将包随项目保存，可以放到 `MyApp\libs`，再在 `MyApp\entry\oh-package.json5` 中声明：

```json5
{
  "dependencies": {
    "@arkdb/mysql": "file:../libs/arkdb-mysql-1.0.2.har"
  }
}
```

路径相对于模块的 `oh-package.json5`。恢复依赖后重建项目。这个 HAR 已包含共享核心代码，不要再添加 `@arkdb/core` 依赖、core override 或 ArkDB 源码模块。

确认最终合并的应用权限中有 `ohos.permission.INTERNET`。证书文件的读取和凭据存储由应用处理。

## 首次连接、查询和关闭

把下面的函数放在应用的 Worker 所用模块中，由 Worker 调用，不要直接放进 ArkUI 事件回调。它是一次数据库操作，不是完整的 Worker 入口；注册和消息处理见下一节。

```typescript
import {
  ConnectionConfig, DbConnection, DbDriverFactory, MySqlDriverFactory,
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

  const factory: DbDriverFactory = new MySqlDriverFactory();
  const connection: DbConnection = factory.createConnection(config, password);
  try {
    await connection.connect();
    return await connection.query('SELECT VERSION() AS version');
  } finally {
    await connection.close();
  }
}
```

查询成功时，`result.columns[0]` 描述名为 `version` 的列，`result.rows[0][0]` 是服务器版本值。读取其他类型和多个结果集的方法见[查询指南](Queries.md)。

请使用与证书匹配的服务器名称。示例选择 `VERIFY_IDENTITY`，同时验证证书链和主机名；需要自定义 CA 时看 [TLS 配置](Connections.md#自定义-ca-与客户端证书)。密码单独传给工厂，不放进 `ConnectionConfig` 或日志。

`close()` 也可能失败。这个最短示例会传播关闭错误；需要同时保留查询错误和关闭错误时，使用[事务示例中的错误处理方式](Transactions.md#提交与回滚示例)或完整 Worker 示例。

## 接入 Worker

接下来按 [Worker 集成](Worker-Integration.md)注册入口并连接 UI 消息。连接留在 Worker 内，UI 只接收适合展示的数据。

如果想先运行一个现成项目，可以使用[完整示例](Worker-Integration.md#运行完整示例)。它的源码准备步骤与上面的 HAR 安装是两条不同路径，不需要为了在自己的应用里使用驱动而构建示例。

需要明确填写主机、端口、数据库、账号和证书位置时，继续看[连接信息与调用示例](Connections.md#定义连接信息并调用)。上面的 `host`、`user` 和 `password` 是调用方传入的参数，不是驱动自动提供的值。

验证连接后，按[查询页的 CRUD 示例](Queries.md#crud-示例的准备)分别练习建表、插入、查询、更新和删除。只读连接检查不需要建表权限；CRUD 使用临时表，需要测试数据库的相应权限。
