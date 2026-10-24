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

## 安排连接的生命周期

同一连接上的查询、事务、元数据和指标操作要串行执行。前一个操作结束前，不要发下一条命令；应用可以拒绝重叠请求，也可以自己维护队列。

页面退出时先请求 Worker 停止接收新操作并清理连接。必要时可用有界的强制终止兜底，但终止 Worker 不能证明服务器端查询已取消，特别是已经发出的写操作。

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
