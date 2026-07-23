# stem-hub 上位机

STM32 `stem-hub` 固件的 Qt Python 上位机（PySide6）。功能详见固件仓的
[上位机AT命令文档](../stem-hub/上位机AT命令文档.md)。

## 功能（规划中）

- **控制台 (Tab 1)**：电池电量 / 温度 / NTC 框图，充放电模式切换，电机驱动状态 + 控制，NMOS1/2 与 MP4317/LM51770 开关，nFAULT/nFLT 状态，AT 指令输入框
- **实时图表 (Tab 2)**：可调频率（默认 2 Hz）拉取 `AT+SENSE?` 滚动绘图，可选显示哪些量
- **UART 透传 (Tab 3)**：UART2 / UART3 / 2&3 桥接开关 + 透传收发面板

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

见固件仓 [上位机AT命令文档.md](../stem-hub/上位机AT命令文档.md)。

简要：
- 串口 UART1 = 115200 8N1，AT 命令必须大写、**无空格**、`\r\n` 结尾
- 握手：`AT+VERSION?` → 收到 `+VERSION:...` + `OK` 即握手成功
- 周期查询：`AT+SENSE?` 返回 `+SENSE:...` + `OK`
- 控制命令单条发完等回包

## 状态

🚧 **早期开发中**。当前只搭好工程骨架，能弹个空窗。

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
