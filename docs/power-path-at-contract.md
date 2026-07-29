# v3.0 电源路径 AT 契约

本文档定义 `stem-hub-host` 与 `stem-hub release-v3.0` 之间的电源路径控制契约。上位机只请求业务模式，LM51770 与 MP4317 的互锁和 GPIO 时序由 MCU 单点保证。

## 三种稳定状态

| 模式 | LM51770 | MP4317 | 用途 |
| --- | --- | --- | --- |
| OFF | 关 | 关 | 电源路径全关 |
| CHARGE | 开 | 关 | 充电路径打开 |
| DRIVE | 关 | 开 | 后级驱动/输出路径打开 |

固件不允许两路同时打开。切换到 CHARGE 或 DRIVE 时，MCU 总是先关闭两路，再仅打开目标路径。

## 唯一有效的五条控制命令

| 命令 | 目标状态 |
| --- | --- |
| `AT+CHARGE=ON\r\n` | CHARGE |
| `AT+CHARGE=OFF\r\n` | OFF |
| `AT+DRIVE=ON\r\n` | DRIVE |
| `AT+DRIVE=OFF\r\n` | OFF |
| `AT+POWER=OFF\r\n` | OFF |

每次模式操作只发送上表中的一条命令，并等待 `OK`。上位机不应自行发送多条命令来编排关断和打开顺序。

旧的 `AT+LM51770=ON/OFF` 与 `AT+MP4317=ON/OFF` 已从当前命令集删除；固件对这些命令返回 `ERROR:PARSE`。`AT+POWER=ON` 同样无效。

## 上位机映射

- CHARGE 开关打开：发送 `AT+CHARGE=ON`。
- DRIVE 开关打开：发送 `AT+DRIVE=ON`。
- 任一模式开关关闭：发送该模式的 `OFF`，结果均为两路全关。
- ALL OFF：先发送 `AT+POWER=OFF`，再按现有流程关闭 NMOS1、NMOS2 和灯光。
- fake firmware 使用相同的三态和五条命令，便于无硬件回归。

模式切换请求继续走上位机现有的串行命令队列，避免多个 UI 操作交叠。MCU 仍是最终安全边界，即使绕开 UI 直接写串口也无法通过有效 AT 指令同时打开两路。

## GPIO 时序

LM51770 EN/UVLO（PB3）和 MP4317 控制（PA8）都是低电平使能。对于任一有效模式请求，固件输出任务按以下顺序执行：

1. PB3 置高，关闭 LM51770。
2. PA8 置高，关闭 MP4317。
3. 目标为 CHARGE 时仅将 PB3 置低；目标为 DRIVE 时仅将 PA8 置低；目标为 OFF 时不再打开任何一路。

因此可观察到的最终 GPIO 组合只有 `PB3=1/PA8=1`、`PB3=0/PA8=1`、`PB3=1/PA8=0`。

## 传感采样语义

`AT+SENSE?` 中的 BATT_NTC、BATT_V、NTC1_C、NTC2_C、NTC3_C 使用最近五个完整成功的 1 Hz 采样周期原始 ADC 值的滑动平均，再换算为物理量。只有五路在同一周期全部读取成功时，五个窗口才同步推进；启动不足五个完整周期时按已有有效样本数求均值。

五个窗口是 MCU 静态环形缓冲，每路保存 5 个 `uint16_t` 并使用 `uint32_t` 运行和；单路最大和是 `5 × 4095 = 20475`，不会在 sensorTask 栈上创建五份样本快照。MOTOR_I 继续使用即时值，以保留过流保护响应。

## 版本门禁

上位机只把 `release-v3.x` 识别为兼容当前电源路径契约。连接 v2.x 或其他未知版本时会关闭串口并报告 `INCOMPATIBLE_VERSION`，不会进入已连接状态或发送 CHARGE/DRIVE 命令。

## 联调清单

1. 用 `AT+VERSION?` 确认返回 `+VERSION:release-v3.0`。
2. 依次发送五条有效命令，确认均返回 `OK`。
3. 发送四条旧独立芯片命令和 `AT+POWER=ON`，确认均返回 `ERROR:PARSE`。
4. 在 CHARGE、DRIVE、OFF 三种状态下检查 PB3/PA8，确认没有两路同时为低电平。
5. 连续读取至少五次 `AT+SENSE?`，确认计数递增且五路传感值采用滚动窗口语义。
