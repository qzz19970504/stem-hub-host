workspace "stem-hub-host" "STM32 stem-hub 固件的 PySide6 上位机（当前架构模型）" {

    model {

        operator = person "运维/调试人员" {
            description "通过桌面上位机监控电源路径、控制输出、透传 UART"
        }

        firmware = softwareSystem "stem-hub 固件 (release-v3.3)" "STM32 下位机：电源路径管理、电机驱动、传感采集" {
            tags "ExternalSystem"
        }

        winport = softwareSystem "Windows 串口设备" "QSerialPort 枚举的物理 / 虚拟 COM 口" {
            tags "ExternalSystem"
        }

        host = softwareSystem "stem-hub-host 上位机" "Qt Python 桌面应用：控制台 / 实时图表 / UART 透传" {

            container "主程序" "stem_hub_host 包" "Python 3.11 + PySide6 + pyqtgraph + numpy" "desktop-app" {

                entry = component "入口与装配" "main.py / app.py / branding.py" "进程入口、QApplication 单例、品牌与字体资源"

                uiLayer = component "UI 层" "ui/ + ui/widgets/" "MainWindow + 三个页面 + 13 个自定义控件"

                themeModule = component "视觉与主题" "theme.py / stylesheet.py / style.qss / fonts.py / native_chrome.py" "颜色/间距/圆角令牌、QSS、Windows 原生标题栏"

                controller = component "控制器" "controller.py" "握手状态机、周期轮询、电源路径转换串行化、透传桥接"

                worker = component "串口工作层" "serial_worker.py" "FIFO 命令队列 + 行切分 + 响应归属 + 超时重同步"

                transport = component "传输抽象" "transport.py" "Transport Protocol：RealSerialTransport / FakeSerialTransport"

                protocol = component "AT 协议层" "at_protocol.py" "AT 命令构造、LineSplitter、ParsedResponse"

                models = component "数据模型" "models.py" "冻结 dataclass：SenseData / OutputState / MotorState / FaultState / DiagInfo"

                buffer = component "数据缓冲" "data_buffer.py" "180 秒滚动环形缓冲，8 通道时序曲线"

                fake = component "假固件" "fake_firmware.py" "无硬件联调时的固件模拟器（--fake）"

            }
        }

        operator -> host "连接串口、控制电源路径与电机、查看遥测与图表、UART 透传"
        host -> firmware "UART1 (9600 8N1)：AT 命令 / \\r\\n 文本响应" "UART1 串口"
        host -> winport "通过 QSerialPort 读写" "QSerialPort"

    }

    views {

        systemContext host "SystemContext" {
            include *
            autoLayout
            title "L1 系统上下文"
        }

        container host "Containers" {
            include *
            autoLayout
            title "L2 容器视图"
        }

        component host.mainProgram "Components" {
            include ->host.mainProgram.*
            include operator
            include firmware
            include winport
            autoLayout
            title "L3 组件视图（当前架构）"
        }

        styles {
            element "ExternalSystem" {
                color #666666
            }
            element "component" {
                shape roundedBox
            }
        }

        theme default
    }

}
