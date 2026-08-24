# v3.3 输出状态、旁路与电源路径 AT 契约

本文档定义 `stem-hub-host` 与 `stem-hub release-v3.3` 之间的输出控制契约。上位机只请求业务模式，互锁、GPIO 时序、间歇充电、旁路锁存和温度保护由 MCU 单点保证。

## 三种允许的物理状态

| 模式 | LM51770 | MP4317 | 用途 |
| --- | --- | --- | --- |
| OFF | 关 | 关 | 电源路径全关 |
| CHARGE | 默认 10 秒开 / 50 秒关；可配置为 n 秒开 / (60-n) 秒关 | 关 | 间歇充电循环启用 |
| DRIVE | 关 | 开 | 后级驱动/输出路径打开 |

固件不允许两路同时打开。进入 DRIVE 或每次重新开启 CHARGE 时，MCU 总是先关闭两路，再仅打开目标路径。

## 唯一有效的五条控制命令

| 命令 | 目标状态 |
| --- | --- |
| `AT+CHARGE=ON\r\n` | 启动并持续 CHARGE 循环 |
| `AT+CHARGE=OFF\r\n` | OFF |
| `AT+DRIVE=ON\r\n` | DRIVE |
| `AT+DRIVE=OFF\r\n` | OFF |
| `AT+POWER=OFF\r\n` | OFF |

每次模式操作只发送上表中的一条命令，并等待 `OK`。上位机不应自行发送多条命令来编排关断和打开顺序。

一次 `AT+CHARGE=ON` 会持续执行 60 秒周期的间歇循环，直到 OFF、DRIVE 或 MCU 复位。默认是 10 秒开启、50 秒全关；固件接受 `AT+CHARGE_TIME=n`（`n=1..60`），将后续完整周期设置为 n 秒开启、(60-n) 秒全关。配置只保存在 RAM，运行中设置从下一次 ON 阶段开始生效；`n=60` 表示连续开启。当前上位机没有 CHARGE_TIME 设置 UI，联调需直接使用串口 AT 接口。开启段和关闭段内重复发送 `CHARGE=ON` 都不会重置当前阶段截止时间。`OK` 只表示请求已成功入队，不表示 LM51770 此刻必处于开启段。

旧的 `AT+LM51770=ON/OFF` 与 `AT+MP4317=ON/OFF` 已从当前命令集删除；固件对这些命令返回 `ERROR:PARSE`。`AT+POWER=ON` 同样无效。

## 上位机映射

- CHARGE 开关打开：发送 `AT+CHARGE=ON`；开关保持打开表示间歇循环已启用，不表示当前 EN 电平。
- DRIVE 开关打开：发送 `AT+DRIVE=ON`。
- 任一模式开关关闭：发送该模式的 `OFF`，结果均为两路全关。
- ALL OFF：关闭两路旁路、电源路径、NMOS1、NMOS2 和 LIGHTS，不改变独立电机模式。
- fake firmware 使用相同的三态和五条命令，便于无硬件回归。

模式切换请求继续走上位机现有的串行命令队列，避免多个 UI 操作交叠。MCU 仍是最终安全边界，即使绕开 UI 直接写串口也无法通过有效 AT 指令同时打开两路。

## GPIO 时序

LM51770 EN/UVLO（PB3）和 MP4317 控制（PA8）都是低电平使能。对于任一有效模式请求，固件输出任务按以下顺序执行：

1. PB3 置高，关闭 LM51770。
2. PA8 置高，关闭 MP4317。
3. CHARGE 开启段仅将 PB3 置低，默认 10 秒后回到两路全关 50 秒；配置为 n 时则开启 n 秒、全关 (60-n) 秒，再重复上述顺序。DRIVE 仅将 PA8 置低；OFF 不再打开任何一路。

因此可观察到的最终 GPIO 组合只有 `PB3=1/PA8=1`、`PB3=0/PA8=1`、`PB3=1/PA8=0`。

## 输出状态、旁路与子项联锁

`AT+OUTPUT?` 固定返回：

```text
+OUTPUT:POWER=<OFF|CHARGE|DRIVE>,CHARGE_PHASE=<IDLE|ON|OFF>,NMOS1=<0|1>,NMOS2=<0|1>,LIGHTS=<0|1>,MOTOR_BYPASS=<0|1>,CHARGE_BYPASS=<0|1>
OK
```

上位机严格要求完整、无重复且合法的字段集合，并以该回读作为唯一输出确认状态。控制命令成功后额外查询一次，命令拒绝、超时或查询失败时保留上一次确认状态。

- PC14 的 CHARGE BYPASS 只要求请求模式为 CHARGE，不要求当前处于周期 ON；开启后跨周期 OFF 保持，离开 CHARGE 或安全停机时清除。
- PC13 的 MOTOR BYPASS 仅在 FWD/REV 可开启，换向、STOP、BRAKE、SLEEP、堵转或安全停机时清除。
- NMOS1、NMOS2、LIGHTS 只有 DRIVE 模式可开启；离开 DRIVE 自动关闭。所有 OFF 请求始终允许。

## 安全边界

默认 10 秒开 / 50 秒关及可配置的 n/(60-n) 周期都只是时间降额措施。MCU_C、LM51770_C、MP4317_C、DRV8874_C、CHARGE_MOS_C 五路器件 NTC 执行软件保护：任一路严格高于 60.0°C、无效或读取失败即安全停机；只有五路全部有效且不高于 55.0°C 才解除锁存。BATT_NTC 仅显示。软件保护仍不能替代硬件限流、功率器件选型和散热设计。

## 传感采样语义

`AT+SENSE?` 按固定顺序发送 `BATT_NTC,BATT_V,MCU_C,LM51770_C,MP4317_C,DRV8874_C,CHARGE_MOS_C,MOTOR_I,TICK,COUNT,STK_AT,STK_SENSOR,STK_MOTOR,TX_SP,TX_LS`。上位机严格要求完整语义字段集合，不兼容旧的编号 NTC 字段。

BATT_NTC、BATT_V 与五路器件 NTC 使用同步七通道 1 Hz 滚动窗口。只有七路在同一周期全部成功时才共同推进并发布；任何部分周期都不推进、不发布。每路对最近五个完整周期的原始 ADC 值求均值后再换算，启动不足五个完整周期时按已有完整样本数求均值。若电池通道失败而五路器件通道成功，MCU 只计算受保护器件的预览均值用于保护，不发布 SENSE。

七个窗口是 MCU 静态环形缓冲，每路保存 5 个 `uint16_t` 并使用 `uint32_t` 运行和；单路最大和是 `5 × 4095 = 20475`。MOTOR_I 继续使用即时值，以保留过流保护响应。上位机 DataBuffer 和图表精确提供八个通道：`batt_v`、`batt_ntc`、`mcu_c`、`lm51770_c`、`mp4317_c`、`drv8874_c`、`charge_mos_c`、`motor_i`；控制台以 3×2 网格显示六张温度卡。

## 版本门禁

上位机只接受精确的 `+VERSION:release-v3.3` 后跟 `OK`。任何其他版本都会关闭串口并报告 `INCOMPATIBLE_VERSION`，不会进入已连接状态或发送输出命令。

## 联调清单

1. 用 `AT+VERSION?` 确认返回 `+VERSION:release-v3.3`，并严格解析 `AT+OUTPUT?`。
2. 依次发送五条有效命令，确认均返回 `OK`。
3. 发送四条旧独立芯片命令和 `AT+POWER=ON`，确认均返回 `ERROR:PARSE`。
4. 默认配置下验证 CHARGE 在约 10 秒转全关、约 60 秒重新开启；再通过串口设置一个 `AT+CHARGE_TIME=n` 值，确认下一完整周期采用 n/(60-n) 秒且重复 CHARGE 不延长当前开启段。
5. 在 CHARGE 的开启段和关闭段分别发送 OFF/DRIVE，确认立即取消循环且旧计时不会复活。
6. 检查 PB3/PA8，确认任何时刻都没有两路同时为低电平。
7. 连续读取至少五次 `AT+SENSE?`，确认计数递增、语义字段顺序精确且七路传感值采用同步滚动窗口语义。
