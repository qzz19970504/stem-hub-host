# 限速采样与连接超时实施报告

日期：2026-07-23  
对应规格：
`docs/superpowers/specs/2026-07-23-rate-limited-sampling-and-connection-timeout-design.md`

## 1. 采样频率

采样控件保留一位小数，但限制为五个安全档位：

| 频率 | 轮询周期 |
|---:|---:|
| 0.2 Hz | 5000 ms |
| 0.4 Hz | 2500 ms |
| 0.6 Hz | 1667 ms |
| 0.8 Hz | 1250 ms |
| 1.0 Hz | 1000 ms |

默认频率和最高频率均为 1.0 Hz，因此每秒最多启动一次完整轮询周期。
每个周期仍发送 SENSE、FAULT、MOTOR 三条现有查询命令。

用户键入非档位数值时，Controller 会归一化到最近档位；正中间值向较高
档位归一化，并把最终结果同步回控件。

## 2. 绘图时基

图表继续使用 `time.monotonic()` 产生的真实采样时间，而不是按样本序号
伪造等距时间。最新数据为 0 秒，历史数据按真实经过时间显示为负值。

可视横轴固定为 `[-300, 0]` 秒，因此切换采样档位后：

- 数据点间距会随真实采样周期变化。
- 已采集数据的时间戳不会被重写。
- 各档位始终使用相同的最近五分钟时间尺度。

## 3. 有限连接状态机

生产时序：

- 串口打开后 200 ms 发起第一次握手。
- 单次握手最多等待 500 ms。
- 未成功时约 1000 ms 后重试。
- 整轮连接尝试最长 5000 ms。

连接成功会取消全部握手定时器并启动遥测。达到总期限后：

1. 停止所有握手和重试定时器。
2. 主动关闭串口。
3. 清除旧遥测及连接期状态。
4. 通过现有断开数据流恢复 `OFFLINE`、绿色 `CONNECT` 和端口选择。
5. 写入最终失败日志。
6. 只弹出一次“连接失败”提示。

用户在 `CONNECTING` 期间主动点击 `DISCONNECT` 会立即取消，不弹失败
提示。直接打开串口失败也不会进入后台重试。

## 4. 无硬件测试

可操作的完整 fake 界面：

```powershell
& 'env\release\Scripts\python.exe' -m stem_hub_host.main --fake
```

打包版本：

```powershell
& 'dist\stem-hub-host.exe' --fake
```

只运行连接自动测试：

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests\test_connection_flow.py -q
```

`pytest` 会自动关闭窗口，仅用于逻辑回归；人工点击和查看动画应使用
`--fake`。

## 5. 验证结果

- 合并后全量测试：154 passed
- Python `compileall`：通过
- FakeFirmware 真实连接流：通过，连接徽章进入 `CONNECTED`
- 源码 `--fake`：运行 5 秒仍存活
- 视觉回归：16/16 通过，平均 RGB 差异均为 0
- PyInstaller 6.21.0：构建成功
- 打包版 `--fake`：运行 5 秒仍存活

发布产物：

- 路径：`dist/stem-hub-host.exe`
- 大小：77,907,041 bytes（74.30 MiB）
- SHA-256：
  `CE2FB4C0281C35FD325D35724A74BCE629CE8E0A5C6AF272E9438FBCECC1D805`

构建清单包含 Rajdhani、JetBrains Mono Regular/Bold、Noto Sans SC 四个
字体文件和 `style.qss`，未发现 MKL/TBB。`env/release` 原样保留，可
继续复用。
