# stem-hub-host 架构模型总结

## 这是什么系统

**stem-hub-host** 是 STM32 `stem-hub` 电源路径固件（`release-v3.3`）的桌面**上位机**：一个单进程、单线程的 Qt Python（PySide6）应用，通过 UART1（9600 8N1）用 `\r\n` 结尾的 AT 文本协议与下位机通信，提供三个页面：

1. **CONSOLE（控制台）**：电池电量环、6 张语义温度卡、CHARGE/DRIVE 互斥电源模式、充电/电机限流旁路、电机控制、受 DRIVE 联锁的 NMOS1/2/LIGHTS、全关与故障指示。
2. **CHARTS（实时图表）**：可调频率（0.2–1.0 Hz，默认 1 Hz）轮询 `AT+SENSE?`，8 通道 180 秒滚动绘图。
3. **PASSTHROUGH（UART 透传）**：UART2/UART3/2&3 桥接开关 + 二进制安全的确认式收发隧道。

## 架构分层（自上而下）

```
用户
 │
UI 层        MainWindow + 3 页面 + 13 个自定义控件；主题令牌集中在 theme.py + style.qss
 │           ↕ Qt Signal（命令下行 / 状态上行）+ 100ms 定时拉取刷新
控制层       Controller：握手状态机、周期轮询、电源路径转换串行化、透传桥接；持有 DataBuffer
 │           ↕ send_command / response_received 信号
通信层       SerialWorker：FIFO 命令队列、行切分、响应归属、超时重同步
 │           ├── at_protocol：命令构造与响应解析
 │           ├── models：7 个冻结 dataclass（Sense/Output/Motor/Fault/Diag/Version/UartRx）
 │           └── Transport 抽象：RealSerialTransport(QSerialPort) / FakeSerialTransport
 │
STM32 固件 (release-v3.3)  ← UART1 9600 8N1
```

## 关键设计特征

- **Transport 抽象**：`--fake` 假固件与真硬件共用完全相同的 Worker/Controller/UI 代码路径，是无硬件联调与自动化测试的基础。
- **单线程事件循环**：没有 QThread；串口读取、超时与周期轮询全部由 Qt 主事件循环的 QTimer/Signal 驱动，`send_and_wait` 用局部 `QEventLoop` 实现同步语义。
- **命令-响应严格归属**：命令按队列序发送、响应按序归属；超时不放弃连接，而是进入 200ms 静默重同步，再以 `ERROR:TIMEOUT` 回报所有挂起命令。
- **以固件确认为准（firmware-confirmed state）**：UI 开关状态只来自 `AT+OUTPUT?` 回读，命令失败时回滚到最近确认状态。
- **互斥操作串行化**：CHARGE/DRIVE/OFF 切换、全关序列、透传桥接切换各自排队执行，进行中门控相关 UI 控件。
- **版本握手门禁**：仅接受精确 `+VERSION:release-v3.3`，5 秒内未成功即关串口并提示。

## 图与文件

| 文件 | 回答的问题 | 打开方式 |
| --- | --- | --- |
| `workspace.dsl` | 系统边界、容器、组件分别是什么？（L1/L2/L3 三个 C4 视图） | Qoder DSL 查看器 / Structurizr |
| `module-graph.dot` | 模块之间谁依赖谁、数据往哪流？ | Qoder Graphviz 预览 / dot 工具 |
| `system-model.evidence.md` | 每个节点/关系对应哪段代码证据？ | 任意 Markdown 查看器 |

## 置信度与未验证项

模型中所有节点与关系均有代码直接证据（high），仅 `ConsoleTab → DataBuffer` 的页面内读取细节为 medium（注入已确认）。固件仓在本工作区之外，固件侧行为按 `README.md` 与 `docs/power-path-at-contract.md` 转述。

## 下一步建议（如需继续深入）

- 想看"连接→握手→轮询"或"用户点击→固件确认"的时序 → `flow-visualizer`
- 想评估改动某个模块的影响面 → `dependency-impact-analyzer`
- 想做架构风险/质量审查 → `risk-quality-reviewer`
