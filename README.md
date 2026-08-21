# stem-hub 上位机

STM32 `stem-hub` 固件的 Qt Python 上位机（PySide6）。当前精确匹配
`release-v3.2` 固件；完整协议见本仓的
[电源路径 AT 契约](docs/power-path-at-contract.md)和固件仓的
[上位机AT命令文档](../stem-hub/上位机AT命令文档.md)。

## 功能

- **控制台 (Tab 1)**：电池电量与六张 3×2 语义温度卡（电池、MCU、LM51770、MP4317、DRV8874、充电 MOS），CHARGE / DRIVE 互斥模式切换，电机驱动状态 + 控制，NMOS1/2、全关、nFAULT/nFLT 状态和 AT 指令输入框
- **实时图表 (Tab 2)**：可调频率（默认 1 Hz）拉取 `AT+SENSE?` 滚动绘图；DataBuffer 与图表提供 `batt_v`、`batt_ntc`、`mcu_c`、`lm51770_c`、`mp4317_c`、`drv8874_c`、`charge_mos_c`、`motor_i` 八个通道
- **UART 透传 (Tab 3)**：UART2 / UART3 / 2&3 独占透传目标 + 原始字节收发面板

## 快速开始

```powershell
# 1. 准备环境 (一次性, 详细见 env/README.md)
conda create -n stem-hub-host python=3.11 -y
conda activate stem-hub-host
conda install --override-channels -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/ icu=73.2 pyqtgraph numpy -y
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple PySide6 PySide6-Addons

# 2. 跑程序
python -m stem_hub_host.main
```

## 无硬件联调

没有串口或下位机时，使用内置 fake firmware 启动完整、可操作的界面：

```powershell
# 从保留的发布环境启动源码
& 'env\release\Scripts\python.exe' -m stem_hub_host.main --fake

# 打包后启动
& 'dist\stem-hub-host.exe' --fake
```

fake 模式会自动创建并打开 `FAKE0`，模拟版本握手、遥测、输出控制和
电机响应，适合直接观察 UI 与操作效果。

也可以只运行连接相关的自动测试：

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests\test_connection_flow.py -q
```

`pytest` 会自动创建并关闭测试窗口，只给出通过/失败结果，不是持续可
操作的界面预览；想实际点击测试时应使用 `--fake`。

## 项目结构

```
stem-hub-host/
├── env/README.md               # 环境搭建说明
├── requirements.txt
├── stem_hub_host/              # 主包
│   ├── main.py                 # 入口
│   ├── app.py                  # QApplication 装配
│   ├── serial_worker.py        # (待) 串口读取 + 行切分
│   ├── at_protocol.py          # (待) AT 响应解析
│   ├── commands.py             # (待) 高层 AT 命令封装
│   ├── models.py               # (待) 数据模型 dataclass
│   ├── handshake.py            # (待) 握手状态机
│   ├── ui/
│   │   ├── main_window.py      # 主窗口 + TabWidget
│   │   ├── widgets/            # 自定义 widget（卡片 / 图表 / 按钮组）
│   │   ├── theme.py            # (待) 配色常量
│   │   └── icons/              # (待) SVG 图标
│   └── resources/
│       └── style.qss           # (待) QSS 样式表
├── tests/                      # 单元测试
│   ├── test_at_protocol.py
│   └── fixtures/               # 录制下来的固件回包样本
├── tools/                      # 工具脚本
│   └── make_winrt_forwarders.py  # (备用) 写 WinRT API-set forwarder DLL
└── tools/fake_firmware.py      # (待) 模拟固件, 无硬件时联调
```

## 协议

当前电源路径的主机/固件契约见
[docs/power-path-at-contract.md](docs/power-path-at-contract.md)，完整命令集见固件仓
[上位机AT命令文档.md](../stem-hub/上位机AT命令文档.md)。

简要：

- 串口 UART1 = 9600 8N1，AT 命令必须大写、**无空格**、`\r\n` 结尾
- 握手：`AT+VERSION?` → 只接受精确的 `+VERSION:release-v3.2` + `OK`
- 透传进入：`AT+TRANS=1/2/1&2` 分别选择 UART2、UART3 或双路；收到 `OK` 后，UART1 发送的数据按原始字节直接转发
- 透传退出：上位机保证前后各至少 10 ms 静默并发送保留序列 `+++`；收到 `OK` 后恢复 AT 查询。旧 `AT+UART*=ON/OFF` 和 `AT+UARTTX=<HEX>` 不再使用
- 下游反向数据继续解析为 `+UART2RX:<HEX>` / `+UART3RX:<HEX>`，不会占用普通 AT 命令响应队列
- 电源模式仅发送一条命令：`AT+CHARGE=ON/OFF`、`AT+DRIVE=ON/OFF` 或 `AT+POWER=OFF`
- `CHARGE=ON` 表示启动 MCU 内 60 秒间歇充电循环，默认 10 秒开 / 50 秒关；固件可通过 `AT+CHARGE_TIME=n`（`n=1..60`）设置为 `n` 秒开 / `60-n` 秒关，当前上位机没有该设置 UI。CHARGE 开关只表示循环已启用，不表示 LM51770 此刻必为开启
- `DRIVE=ON` 与每次充电重新开启都由 MCU 执行“先全关、后单路打开”，上位机不编排芯片级时序
- 周期查询：`AT+SENSE?` 返回 `+SENSE:...` + `OK`；解析器要求完整语义字段集合，不兼容旧的编号 NTC 字段。固件按 `BATT_NTC,BATT_V,MCU_C,LM51770_C,MP4317_C,DRV8874_C,CHARGE_MOS_C,MOTOR_I,TICK,COUNT,STK_AT,STK_SENSOR,STK_MOTOR,TX_SP,TX_LS` 顺序发送
- BATT_NTC、BATT_V 与五路器件 NTC 构成同步七通道 1 Hz 滚动窗口：最近五个完整周期求均值；部分周期不推进、不发布。电池通道失败而五路器件通道成功时，只生成过温保护预览，不发布 SENSE
- MCU、LM51770、MP4317、DRV8874、充电 MOS 五路受保护器件温度任一路 >60.0°C、无效或读取失败即安全停机；五路全部有效且 ≤55.0°C 才清除。电池 NTC 仅显示
- 控制命令单条发完等回包；旧的 `AT+LM51770` / `AT+MP4317` 指令会被固件拒绝

透传的完整状态、错误处理和二进制边界见
[独占透传协议契约](docs/transparent-mode-at-contract.md)。

## 视觉回归

界面颜色、圆角、间距、控制高度、描边、辉光和动画时长集中定义在
`stem_hub_host/ui/theme.py`，`style.qss` 通过具名令牌渲染。视觉审计覆盖
Dark/Light、三个页面、固定 1600×900、1920×1080 全屏审计视图，以及
Console 的连接/断开状态，共 16 张黄金截图。

```powershell
# 普通检查：只生成临时截图并与黄金基线比较，不会覆盖基线
& 'env\release\Scripts\python.exe' tools\check_visual_regression.py

# 仅在已人工确认视觉变化时，显式更新黄金基线
& 'env\release\Scripts\python.exe' tools\update_visual_baselines.py
```

默认阈值为平均 RGB 绝对差不超过 `3/255`，且任一通道差值大于 12 的
像素占比不超过 1%。黄金图片与清单位于 `tests/golden/visual/`。

## 精简发布包

发布包必须在独立的 Python 3.11 虚拟环境中构建，避免 Conda 版 NumPy
把整套 Intel MKL/TBB 运行库收集进单文件程序。发布依赖固定在
`requirements-release.txt`，应用源码、QSS 和字体资源与开发环境共用。

```powershell
# 1. 从已验证的 Python 3.11 解释器创建隔离环境
& 'C:\Users\44575\.conda\envs\stem-hub-host\python.exe' -m venv 'env\release'

# 2. 安装固定版本的 PyPI 依赖
& 'env\release\Scripts\python.exe' -m pip install --upgrade pip
& 'env\release\Scripts\python.exe' -m pip install -r requirements-release.txt

# 下载较慢时，用下面命令替换上一条安装命令（二选一）
& 'env\release\Scripts\python.exe' -m pip install `
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple `
    -r requirements-release.txt

# 3. 完整测试后执行干净构建
& 'env\release\Scripts\python.exe' -m pytest tests -q
& 'env\release\Scripts\python.exe' -m PyInstaller --clean --noconfirm stem-hub-host.spec
```

构建完成后还需用 `--fake` 启动 `dist\stem-hub-host.exe`，并检查打包清单
包含四个字体文件和 `style.qss`，且不再包含 `mkl*.dll` 或 `tbb*.dll`。
