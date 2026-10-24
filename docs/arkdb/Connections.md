# 连接配置与 TLS

MySQL 1.0.2 通过 `ConnectionConfig` 配置连接，密码另行传给 `MySqlDriverFactory.createConnection(config, password)`。创建连接对象时不会联网，调用 `connect()` 后才开始连接。

## 连接字段

先填写 `host` 和 `user`，需要时设置 `port`、`defaultSchema` 和连接截止时间，再调用 `validate()`。返回非空错误列表时先修正配置，不要继续连接。

需要把错误标到具体输入框时，使用 `validateIssues()`；其中的 `ConnectionConfigField` 标识对应字段。两种校验都不会打开网络连接。

完整的字段类型、默认值和限制见[配置参考](Configuration-Reference.md#connectionconfig)。密码、连接分组和界面状态不属于连接配置。`clone()` 会复制配置，并隔离嵌套的 TLS 设置。

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
