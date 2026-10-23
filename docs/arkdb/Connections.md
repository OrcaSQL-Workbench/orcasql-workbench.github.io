# 连接配置与 TLS

通过 `new ConnectionConfig()` 配置连接，先调用 `validate()` 或 `validateIssues()`，再交给 `MySqlDriverFactory.createConnection(config, password)`。校验不会打开连接，密码由调用方另行提供。

## 连接字段

| 字段 | 默认值 | 含义 |
| --- | --- | --- |
| `host` | 空，必填 | 服务器名称或 IP；验证身份时须匹配证书 |
| `port` | `3306` | 1–65535 的整数 |
| `user` | 空，必填 | MySQL 账号 |
| `defaultSchema` | 未设置 | 认证时选择的默认数据库 |
| `ssl` | `new SslConfig()` | TLS 策略与可选证书路径 |
| `connectTimeoutMs` | `10000` | 正整数，覆盖打开连接的总截止时间 |
| `autocommit` | `true` | 请求的初始自动提交状态 |

`validate()` 返回 `ArkDbError[]`；`validateIssues()` 还提供 `ConnectionConfigField` 字段定位。`clone()` 会复制连接配置并隔离嵌套的 TLS 配置。

配置中不保存连接分组、配置档案 ID、密码或界面状态。驱动通过工厂选择，不通过配置中的引擎标签选择。客户端使用 `utf8mb4`；不要添加当前公共接口未提供的字符集、压缩、SQL mode 或未来引擎选项。

## 明确选择 TLS 模式

| `SslMode` | 行为 |
| --- | --- |
| `DISABLED` | 明文 TCP，仅在明确允许时使用 |
| `PREFERRED` | 服务器提供 TLS 时协商，否则允许明文；这是兼容性默认值 |
| `REQUIRED` | 要求加密，但不提供验证模式的服务器身份保证 |
| `VERIFY_CA` | 要求 TLS 并验证证书链 |
| `VERIFY_IDENTITY` | 验证证书链与主机名，新接入建议使用 |

不要为解决证书错误而自动降级到明文或不验证身份。应核对服务器名称、证书链、平台信任和证书文件的可读性。

## 自定义 CA 与客户端证书

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

只验证服务器时，不设置 `clientCertPath` 和 `clientKeyPath`。需要双向 TLS 时，这两项必须成对提供。`SslConfig` 另有可选的 `cipherSuites`；不设置 CA 时使用平台信任策略。

证书路径由运行应用的 HarmonyOS 进程解释，不是开发电脑的路径。应用负责文件选择、拷入沙箱、访问授权及私钥安全存储；示例中的 CA 路径必须事先可读，不会自动获得任意文件访问权限。

本地编译和模拟证书测试不能证明实机证书链、主机名拒绝或双向 TLS 已通过。请在目标设备上按所选策略验收，不将工程预览当作安全兼容性认证。

## 会话生命周期

`connect()` 完成后才能查询。`ping()` 检查当前会话，`changeContext(context)` 切换 MySQL 默认数据库，`close()` 释放连接。调用方必须串行化这些操作，并检查 `state`、`sessionStatus` 和执行结果。

驱动不会在连接失败后自动重连或重放。连接或提交响应丢失时，执行结果可能未知，不能直接重试写入。截止时间与取消的区别见[事务、取消与超时](Transactions-and-Cancellation.md)。

接口依据：[ConnectionConfig](https://github.com/OrcaSQL-Workbench/ArkDB/blob/508adf42a6d7d485fe38c84cdf5c91322adf6e6d/mysql/src/main/ets/core/model/ConnectionConfig.ets)。
