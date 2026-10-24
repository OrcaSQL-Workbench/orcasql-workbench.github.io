# Worker 集成

数据库连接由应用自己的 Worker 管理。页面负责输入和展示，Worker 负责连接、执行和关闭。驱动不会创建 Worker，也不会替应用排队并发请求。

这页适用于 MySQL 1.0.2。可以对照[完整 Stage 示例](https://github.com/OrcaSQL-Workbench/ArkDB/tree/f532d0c37adf4dbba7a1a313679f0024822ed752/examples/mysql-client)接入，不必自行设计一套托管客户端接口。

## 注册入口

在应用模块的 `build-profile.json5` 中注册：

```json5
{
  "buildOption": {
    "sourceOption": {
      "workers": ["./src/main/ets/workers/mysql.worker.ets"]
    }
  }
}
```

宿主通过 `@kit.ArkTS` 的 `worker.ThreadWorker` 创建入口；对应的运行路径是 `entry/ets/workers/mysql.worker.ets`。Worker 入口文件不要导出声明，共享 DTO 放在另一个模块。

路径、生命周期和消息接口以 Huawei 的 [Worker 指南](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/worker-introduction)为准。

## 在两端传什么

UI 向 Worker 发送操作所需的数据，Worker 返回有界的结果摘要或展示数据。不要传递连接对象、`QueryResult`、原始错误或 UI 引用。

示例使用扁平的 `@Sendable` 请求和响应类。自己的消息格式也要明确处理 `bigint`、精确小数、二进制和 SQL NULL：不要直接对整个查询结果做 JSON 序列化。类型说明见[数据类型与结果](Data-Types-and-Results.md)。

密码只在本次操作需要的地方传递，不写入配置或日志。不要把清空一个字符串引用说成已经安全擦除内存。

## 连接检查的请求与响应示例

下面是一次性连接检查的完整消息路径，不是自动管理的 Worker。先准备[连接页的 `ConnectionExample.ets`](Connections.md#定义连接信息并调用)和[错误页的 `ErrorFormatting.ets`](Errors-and-Logging.md#展示连接与清理错误)，并按上节注册 `mysql.worker.ets`。

### 共享消息：`sample\ConnectionMessages.ets`

消息中的主机、端口、账号、数据库和 CA 路径来自宿主配置；密码来自本次输入。两端导入同一组类，不把连接对象放入消息。

[//]: # (arkdb-example: worker-messages)
```typescript
@Sendable
export class ConnectionRequest {
  host: string = '';
  port: number = 3306;
  user: string = '';
  password: string = '';
  database: string = '';
  caCertPath: string = '';
}

@Sendable
export class ConnectionResponse {
  ok: boolean = false;
  text: string = '';
}
```

### 宿主发送：`sample\ConnectionClient.ets`

`createExampleConfig()` 中明确列出了需要替换的 `host` 等信息；正式应用也可以改成从连接表单取得。下面的函数只启动 Worker 和传消息，不在 UI 线程执行数据库操作。

[//]: # (arkdb-example: worker-host)
```typescript
import { ErrorEvent, MessageEvents, worker } from '@kit.ArkTS';
import { ConnectionExampleFailure, createExampleConfig } from './ConnectionExample';
import { ConnectionRequest, ConnectionResponse } from './ConnectionMessages';

export function startConnectionCheck(passwordFromUi: string,
  onResult: (ok: boolean, text: string) => void): worker.ThreadWorker {
  const config = createExampleConfig();
  const request = new ConnectionRequest();
  request.host = config.host;
  request.port = config.port;
  request.user = config.user;
  request.database = config.defaultSchema ?? '';
  request.caCertPath = config.ssl.caCertPath ?? '';
  request.password = passwordFromUi;

  const instance = new worker.ThreadWorker('entry/ets/workers/mysql.worker.ets');
  let receivedResponse = false;
  instance.onmessage = (event: MessageEvents): void => {
    receivedResponse = true;
    const response: Object = event.data;
    if (!(response instanceof ConnectionResponse)) {
      onResult(false, 'Invalid Worker response. No operation was replayed.');
      return;
    }
    onResult(response.ok, response.text);
  };
  instance.onerror = (_error: ErrorEvent): void => {
    receivedResponse = true;
    onResult(false, 'Worker failed. The execution outcome is unknown.');
  };
  instance.onmessageerror = (): void => {
    receivedResponse = true;
    onResult(false, 'Worker message could not be decoded.');
  };
  instance.onexit = (): void => {
    if (!receivedResponse) onResult(false, 'Worker exited without a result.');
  };
  try {
    instance.postMessage(request);
  } catch (error) {
    let cleanup: Object | null = null;
    try {
      instance.terminate();
    } catch (failure) {
      cleanup = failure as Object;
    }
    throw new ConnectionExampleFailure(error as Object, cleanup);
  }
  return instance;
}
```

页面事件从密码输入框取得本次值后，调用 `startConnectionCheck(passwordFromUi, onResult)`，其中 `onResult` 是页面更新展示状态的回调。启动和发送也可能抛错，页面应捕获并显示失败，而不是保持“正在连接”。返回的 Worker 句柄由页面持有；同一页面操作未完成前禁用重复触发，页面退出时按下一节安排清理。

### Worker 接收：`workers\mysql.worker.ets`

入口文件不导出声明。一次性 Worker 只接收一条连接检查请求；完成数据库清理后发送结果并关闭消息端口。

[//]: # (arkdb-example: worker-entry)
```typescript
import { MessageEvents, ThreadWorkerGlobalScope, worker } from '@kit.ArkTS';
import { ConnectionConfig, SslMode } from '@arkdb/mysql';
import { checkConnection } from '../sample/ConnectionExample';
import { ConnectionRequest, ConnectionResponse } from '../sample/ConnectionMessages';
import { connectionErrorText } from '../sample/ErrorFormatting';

const port: ThreadWorkerGlobalScope = worker.workerPort;
let started: boolean = false;

port.onmessage = (event: MessageEvents): void => {
  const request: Object = event.data;
  if (!(request instanceof ConnectionRequest) || started) {
    throw new Error('Expected one connection request per Worker.');
  }
  started = true;
  void run(request);
};

async function run(request: ConnectionRequest): Promise<void> {
  const response = new ConnectionResponse();
  try {
    const config = new ConnectionConfig();
    config.host = request.host;
    config.port = request.port;
    config.user = request.user;
    config.defaultSchema = request.database;
    config.ssl.mode = SslMode.VERIFY_IDENTITY;
    if (request.caCertPath.length > 0) config.ssl.caCertPath = request.caCertPath;
    await checkConnection(config, request.password);
    response.ok = true;
    response.text = 'Connected, ping completed, and connection closed.';
  } catch (error) {
    response.text = connectionErrorText(error as Object);
  } finally {
    request.password = '';
  }
  try {
    port.postMessage(response);
  } finally {
    port.close();
  }
}
```

成功响应中的 `ok` 为 `true`；连接或关闭失败时保持 `false`，展示脱敏后的错误。设置空密码引用只减少保留，不代表安全擦除。消息在发送后不要由宿主立即修改，以免影响 Worker 使用共享请求。

此入口只检查连接。需要运行[查询页的 CRUD](Queries.md#串行调用与结果)时，在 Worker 导入 `runCrudExample()`，用它替换 `checkConnection()` 的调用，并将返回的字符串行放入响应文字；不要同时启动两个操作。现成上游应用仍是只读示例，不因本页新增代码就具备 CRUD 界面。

## 安排连接的生命周期

同一连接上的查询、事务、元数据和指标操作要串行执行。前一个操作结束前，不要发下一条命令；应用可以拒绝重叠请求，也可以自己维护队列。

页面退出时先请求 Worker 停止接收新操作并清理连接。必要时可用有界的强制终止兜底，但终止 Worker 不能证明服务器端查询已取消，特别是已经发出的写操作。

上面的一次性连接检查入口不实现 `stop` 消息，不要直接向它发送上游完整示例的 `stop` 请求。需要可协作停止、页面退出计时和强制终止兜底时，使用下方完整示例的 `SampleRunner.stop()` 与页面生命周期实现；强制终止也不能证明数据库清理已经完成。

取消查询时还要等待原查询结束，详见[取消与超时](Cancellation-and-Timeouts.md)。

## 运行完整示例

从与 Release 对应的 [ArkDB 源码](https://github.com/OrcaSQL-Workbench/ArkDB/tree/f532d0c37adf4dbba7a1a313679f0024822ed752)准备示例。构建步骤在[示例 README](https://github.com/OrcaSQL-Workbench/ArkDB/blob/f532d0c37adf4dbba7a1a313679f0024822ed752/examples/mysql-client/README.md)中，包括 HAR 准备和未签名 HAP 构建。

用 DevEco Studio 打开 `examples\mysql-client`，配置自己的本地调试签名，选择兼容的 API-24 tablet/2in1 目标。示例不附带签名身份。

运行后填写测试服务器、账号和密码，按 **Connect, read, and close**。示例执行固定只读查询，显示版本、BIGINT、DECIMAL 和 NULL，然后关闭连接。它始终验证 TLS 身份；填写的 CA 路径必须已经在应用沙箱内可读。

示例的主要文件：

| 文件 | 用途 |
| --- | --- |
| `pages\Index.ets` | 输入、展示和 Worker 错误/退出处理 |
| `workers\mysql.worker.ets` | Worker 入口、消息分发与关闭 |
| `sample\Messages.ets` | 请求和响应 DTO |
| `sample\SampleRunner.ets` | 校验、连接、读取、脱敏和清理 |

本地编译与离线测试不等于实机网络、证书和取消测试。需要验收的范围见[兼容性说明](Compatibility-and-Upgrading.md#验证范围)。
