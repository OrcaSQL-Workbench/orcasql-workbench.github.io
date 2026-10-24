# 事务、取消与超时

事务和取消的完整用法已分开介绍。按需要阅读[事务](Transactions.md)或[取消与超时](Cancellation-and-Timeouts.md)；下面保留常用概念的入口。

## 事务

使用专用连接和事务型表，串行执行命令。提交、回滚和关闭的错误要分别保留，不让清理错误覆盖原始失败。完整代码见[提交与回滚示例](Transactions.md#提交与回滚示例)。

## 取消使用独立控制连接

MySQL 的取消使用独立控制连接。连接的 `features.cancellation` 会管理这条控制连接；保留的 `createExecutionController(controlConnection)` 则由调用方管理它。

两种方式都必须等待原查询结束，不能只等待取消请求。见[取消当前查询](Cancellation-and-Timeouts.md#取消当前查询)和[兼容的句柄式接口](Cancellation-and-Timeouts.md#兼容的句柄式接口)。

## 连接截止时间不等于语句超时

`connectTimeoutMs` 限制连接打开时间。`statementTimeoutMs` 不会启动语句取消计时器，`Promise.race` 也不会停止服务器执行。具体做法见[连接截止时间和语句截止时间](Cancellation-and-Timeouts.md#连接截止时间和语句截止时间)。

## 何时不能安全复用

传输或协议失败、未知会话状态、强制终止和执行结果不确定时，不要按正常空闲连接继续使用。取消后的状态判断见[取消结果与连接复用](Cancellation-and-Timeouts.md#取消结果与连接复用)。

提交响应丢失后，不自动重试写入；回滚也不能证明提交没有发生。见[回滚不能解决的情况](Transactions.md#回滚不能解决的情况)。
