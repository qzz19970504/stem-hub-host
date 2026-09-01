# stem-hub-host 当前架构模型 — 证据索引

生成方式：`system-modeler` + `c4model`（Structurizr DSL）+ `graphviz`（DOT）
状态：**current**（仅当前架构，不含目标/演进态）
图源码：`workspace.dsl`（L1/L2/L3 C4 视图）、`module-graph.dot`（模块依赖关系图）

## 节点证据

| ID | 标签 | 类型 | 置信度 | 证据 (sourceRefs) |
| --- | --- | --- | --- | --- |
| actor.operator | 运维/调试人员 | actor | high | `README.md` 功能章节 |
| ext.firmware | stem-hub 固件 release-v3.3 | external-system | high | `README.md`、`controller.py:43` (`POWER_PROTOCOL_VERSION`)、`docs/power-path-at-contract.md` |
| ext.serial | Windows 串口设备 | external-system | high | `transport.py` (`QSerialPort`/`QSerialPortInfo`) |
| comp.entry | 入口与装配 | module | high | `stem_hub_host/main.py`、`stem_hub_host/app.py`、`stem_hub_host/branding.py` |
| comp.controller | Controller | module | high | `stem_hub_host/controller.py`（握手 `L673-756`、轮询 `L194-220`、电源转换串行化 `L240-370`、透传 `L404-521`） |
| comp.worker | SerialWorker | module | high | `stem_hub_host/serial_worker.py`（FIFO 队列、重同步 `L321-351`） |
| comp.transport | 传输抽象 | module | high | `stem_hub_host/transport.py`（Transport Protocol + Real/Fake） |
| comp.protocol | AT 协议层 | module | high | `stem_hub_host/at_protocol.py` |
| comp.models | 数据模型 | module | high | `stem_hub_host/models.py`（7 个冻结 dataclass） |
| comp.buffer | DataBuffer | module | high | `stem_hub_host/data_buffer.py`（180s 窗口、8 通道） |
| comp.fake | FakeFirmware | module | high | `stem_hub_host/fake_firmware.py`、`main.py --fake` 分支 |
| comp.ui | UI 层 | module | high | `ui/main_window.py`、`ui/tab1_console.py`、`ui/tab2_plot.py`、`ui/tab3_passthrough.py`、`ui/widgets/*`（13 个文件） |
| comp.theme | 视觉与主题 | module | high | `ui/theme.py`、`ui/style.qss`、`ui/stylesheet.py`、`ui/fonts.py`、`ui/native_chrome.py` |
| cap.console | 控制台能力（Tab 1） | capability | high | `README.md` 功能、`ui/tab1_console.py` |
| cap.charts | 实时图表能力（Tab 2） | capability | high | `README.md` 功能、`ui/tab2_plot.py`、`ui/widgets/plot_widget.py` |
| cap.passthrough | UART 透传能力（Tab 3） | capability | high | `README.md` 功能、`ui/tab3_passthrough.py`、`ui/widgets/passthrough_panel.py` |

## 关系证据

| ID | 关系 | 类型/协议 | 置信度 | 证据 |
| --- | --- | --- | --- | --- |
| edge.entry.assembles | main 构造 app/worker/controller/window | depends-on / in-process | high | `main.py:24-44` |
| edge.ui.controller.down | UI → Controller 命令下发 | calls / in-process | high | `main_window.py:110-121, 155-160` |
| edge.controller.ui.up | Controller → UI 状态/错误信号 | publishes / in-process | high | `main_window.py:124-149`、`controller.py:62-70` |
| edge.controller.worker | Controller → Worker `send_command`/`send_and_wait` | calls | high | `controller.py:215-218, 682` |
| edge.worker.controller | Worker → Controller `response_received`/`at_data_received`/`uart_rx_received` | publishes | high | `controller.py:147-152` |
| edge.worker.transport | Worker 持有 Transport | depends-on | high | `serial_worker.py:70` |
| edge.worker.protocol | Worker 用 LineSplitter/ParsedResponse | depends-on | high | `serial_worker.py:24, 240` |
| edge.protocol.models | 协议解析产出 models | depends-on | high | `at_protocol.py:14-23` |
| edge.controller.buffer | Controller 向 DataBuffer 喂数据 | writes | high | `controller.py:663` |
| edge.buffer.plot | PlotWidget 从 buffer 刷新 | reads | high | `main_window.py:509`、`ui/tab2_plot.py:16-18` |
| edge.buffer.console | ConsoleTab 构造时注入 buffer | reads | medium | `main_window.py:94`、`tab1_console.py:12,33`（注入已确认；页面内具体读取点未逐行核实） |
| edge.transport.hw | RealTransport ↔ 物理串口 | reads/writes / serial | high | `transport.py:30-73` |
| edge.host.firmware | 上位机 ↔ 固件 UART1 9600 8N1 AT | calls / serial | high | `README.md` 协议章节、`at_protocol.py` |
| edge.fake.loop | FakeFirmware ↔ Transport/Worker | calls / in-memory | high | `fake_firmware.py:1-13`、`main.py:27-37` |
| edge.ui.refresh | MainWindow 100ms 定时器拉 `get_latest()` 刷新 UI | reads | high | `main_window.py:151-153, 491-509` |

## 关键架构决策（代码中可观察到）

1. **Transport 抽象使真/假串口可互换**：`SerialWorker` 只依赖 `Transport` 协议（`transport.py:15-27`），`--fake` 模式与测试共享同一代码路径。
2. **单线程事件循环架构**：无 QThread，串口读取、超时、轮询全部跑在 Qt 主事件循环（`send_and_wait` 用 `QEventLoop` 局部阻塞，`serial_worker.py:175-214`）。
3. **FIFO 命令队列 + 响应归属**：所有命令排队、按序发送、按序归属响应，超时触发 200ms 静默重同步（`serial_worker.py:29, 321-351`）。
4. **握手门禁**：连接后 200ms 发起 `AT+VERSION?`，仅接受精确 `release-v3.3`，5 秒 deadline，失败自动关串口（`controller.py:673-751`）。
5. **以固件确认为准的 UI 状态**：开关点亮只依据 `AT+OUTPUT?` 回读（`main_window.py:511-527`），UI 不自行乐观更新。
6. **互斥电源路径串行化**：CHARGE/DRIVE/OFF 转换与"全关"序列在 Controller 中排队执行，期间门控 UI（`controller.py:240-370`、`main_window.py:302-343`）。
7. **集中式主题令牌**：颜色/间距/动画集中在 `theme.py`，`style.qss` 用令牌渲染，支撑 16 张黄金截图视觉回归（`README.md` 视觉回归章节）。

## 假设与未验证项（unknown / low）

- `ui/tab1_console.py` 内部对 `data_buffer` 的具体使用点未逐行核实（注入已确认）。
- `visual_audit.py` / `visual_regression.py` 的调用方式仅从 `tools/check_visual_regression.py` 与 `README.md` 推断，未读源码。
- 打包发布拓扑（PyInstaller → `dist/stem-hub-host.exe`）为构建期事实，运行期仅单进程桌面应用，未观察到其他部署形态。
- 固件仓 `../stem-hub` 不在本工作区，固件侧行为（安全停机、充电循环等）均按 `README.md` 与契约文档转述，标记为外部系统描述而非本仓证据。
