# 连接配置与 TLS

MySQL 1.0.2 通过 `ConnectionConfig` 配置连接，密码另行传给 `MySqlDriverFactory.createConnection(config, password)`。创建连接对象时不会联网，调用 `connect()` 后才开始连接。

## 连接字段

先填写 `host` 和 `user`，需要时设置 `port`、`defaultSchema` 和连接截止时间，再调用 `validate()`。返回非空错误列表时先修正配置，不要继续连接。

需要把错误标到具体输入框时，使用 `validateIssues()`；其中的 `ConnectionConfigField` 标识对应字段。两种校验都不会打开网络连接。

完整的字段类型、默认值和限制见[配置参考](Configuration-Reference.md#connectionconfig)。密码、连接分组和界面状态不属于连接配置。`clone()` 会复制配置，并隔离嵌套的 TLS 设置。

## 定义连接信息并调用

ArkDB 使用配置对象，不是拼接连接字符串。先完成 [HAR 安装](Getting-Started.md#加入应用模块)，再将下面三个代码块依次放在 `src\main\ets\sample\ConnectionExample.ets` 中。连接操作由应用自己的 Worker 调用，注册方式见 [Worker 集成](Worker-Integration.md)。

这里明确列出连接信息的定义位置。替换 `host`、`port`、`database`、`user` 为实际测试环境信息；示例域名不是可用服务器，数据库必须已存在并允许该账号访问。

[//]: # (arkdb-example: connection-config)
```typescript
import { ConnectionConfig, DbConnection, MySqlDriverFactory, SslMode } from '@arkdb/mysql';

export function createExampleConfig(): ConnectionConfig {
  const host: string = 'mysql.example.com';
  const port: number = 3306;
  const database: string = 'arkdb_demo';
  const user: string = 'arkdb_demo_user';
  const caPemPath: string = '';

  const config = new ConnectionConfig();
  config.host = host;
  config.port = port;
  config.defaultSchema = database;
  config.user = user;
  config.autocommit = true;
  config.ssl.mode = SslMode.VERIFY_IDENTITY;
  if (caPemPath.length > 0) config.ssl.caCertPath = caPemPath;
  return config;
}
```

| 变量 | 应填写什么 |
| --- | --- |
| `host` | MySQL DNS 名称，必须与服务器证书匹配 |
| `port` | MySQL 监听端口，通常为 `3306` |
| `database` | 已存在且已授权的测试数据库名，对应 `defaultSchema` |
| `user` | 实际测试账号 |
| `caPemPath` | 应用可读的 CA PEM 路径；留空表示使用平台信任策略，不是关闭证书验证 |
| `passwordFromUi` | 下方调用函数接收的本次密码，由应用输入并传给 Worker，不写入源码或日志 |

### 连接和关闭的共同处理

下面的 `withConnection()` 负责校验、连接、执行回调和关闭。回调只借用连接，不能将它保存到函数外继续使用。后续查询、流式读取和元数据示例复用这段生命周期代码，不各自复制清理逻辑。

[//]: # (arkdb-example: connection-lifecycle)
```typescript
export class ConnectionExampleFailure extends Error {
  primaryFailure: Object | null;
  cleanupFailure: Object | null;

  constructor(primary: Object | null, cleanup: Object | null) {
    super('Connection operation or cleanup failed; inspect retained failures without logging secrets.');
    this.primaryFailure = primary;
    this.cleanupFailure = cleanup;
  }
}

export async function withConnection(config: ConnectionConfig, password: string,
  operation: (connection: DbConnection) => Promise<void>): Promise<void> {
  const issues = config.validate();
  if (issues.length > 0) throw issues[0];
  const connection = new MySqlDriverFactory().createConnection(config, password);
  let primary: Object | null = null;
  let cleanup: Object | null = null;
  try {
    await connection.connect();
    await operation(connection);
  } catch (error) {
    primary = error as Object;
  } finally {
    try {
      await connection.close();
    } catch (error) {
      cleanup = error as Object;
    }
  }
  if (primary !== null || cleanup !== null) {
    throw new ConnectionExampleFailure(primary, cleanup);
  }
}
```

### 检查连接的调用示例

[//]: # (arkdb-example: connection-call)
```typescript
export async function checkConnection(config: ConnectionConfig, password: string): Promise<void> {
  await withConnection(config, password, async (connection: DbConnection): Promise<void> => {
    await connection.ping();
  });
}

export async function runConnectionExample(passwordFromUi: string): Promise<void> {
  const config = createExampleConfig();
  const password: string = passwordFromUi;
  await checkConnection(config, password);
}
```

Worker 收到本次密码后调用 `runConnectionExample()`，不要直接从 ArkUI 事件执行数据库操作。需要从表单取得全部连接信息时，由 Worker 构造同样的 `ConnectionConfig`，再调用 `checkConnection(config, password)`；可直接参考 [Worker 请求与响应代码](Worker-Integration.md#连接检查的请求与响应示例)。

Promise 正常完成表示连接、ping 和关闭均成功，不修改数据库。配置错误直接抛出；连接、操作和关闭失败时分别保留错误，安全展示见[错误与日志](Errors-and-Logging.md#展示连接与清理错误)。

## 明确选择 TLS 模式

新接入建议显式选择 `SslMode.VERIFY_IDENTITY`，使用与服务器证书匹配的 DNS 名称。它同时验证证书链和主机名。

默认值 `PREFERRED` 在服务器不提供 TLS 时允许明文。`REQUIRED` 只要求加密，不能替代身份验证。五种模式的差异在 [SslConfig 参考](Configuration-Reference.md#sslconfig)中。

证书校验失败时，先核对主机名、信任链和证书文件是否可读，不要在错误分支里自动改成不验证或明文。

## 自定义 CA 与客户端证书

下面的示例设置自定义 CA 和客户端证书。只验证服务器时，保留 CA 设置，不设置两个客户端字段。

```typescript
import { ConnectionConfig, SslMode } from '@arkdb/mysql';

export function configureVerifiedTls(config: ConnectionConfig, caPemPath: string,
  clientCertificatePath: string, clientPrivateKeyPath: string): void {
  config.ssl.mode = SslMode.VERIFY_IDENTITY;
  config.ssl.caCertPath = caPemPath;
  config.ssl.tlsVersions = ['TLSv1.2', 'TLSv1.3'];
  config.ssl.clientCertPath = clientCertificatePath;
  config.ssl.clientKeyPath = clientPrivateKeyPath;
  const errors = config.validate();
  if (errors.length > 0) throw errors[0];
}
```

证书路径由 HarmonyOS 应用进程解释，不是开发电脑上的路径。应用负责选择文件、拷入沙箱、获得访问权限和保管私钥。`clientCertPath` 与 `clientKeyPath` 要成对设置。

不设置 CA 路径时使用平台信任策略。示例不会替应用选择文件或授权读取任意路径；实机信任链、主机名拒绝和双向 TLS 仍需在目标环境验收。

## 会话生命周期

`connect()` 完成后再执行命令，结束时总要尝试 `close()`。`ping()` 检查当前会话；`changeContext(context)` 切换默认数据库。它们与查询一样，必须在该连接上串行执行。

MySQL 的 catalog 和 schema 是同一个数据库的两种表达方式。`DatabaseContext` 可以填写其中之一；两者同时填写且冲突时会报错。这个约定不适用于所有数据库。

驱动不会自动重连或重放 SQL。连接、提交响应丢失时，先处理[不确定结果](Troubleshooting.md#断线或超时后能否重试写入)，不要直接重试写入。需要查看状态与方法签名时，见[公共接口](API-Reference.md#工厂与连接)。
