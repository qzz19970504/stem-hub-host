# 全局串口栏与三页布局精修实施报告

日期：2026-07-24
对应规格：`docs/superpowers/specs/2026-07-24-global-serial-layout-polish-design.md`

## 五项结果

1. 温度仪表
   - 固定 `0–100°C` 液位映射。
   - 水柱整段使用当前五段温区的状态色。
   - 删除生硬的顶部水位横线，保留圆润液面和平滑动画。
   - 负温液位归零、超量程液位封顶，文字保留真实值。

2. 串口状态与动作控件
   - 状态徽章和连接按钮统一为 `140×36`。
   - 两者统一 Rajdhani 13pt 粗体。
   - 状态圆点中心位于 14px，文字左内边距为 34px。
   - 端口框保留 235px，完整显示 `COM1 — Serial Port`。

3. 全局串口栏
   - `MainWindow` 持有唯一串口栏。
   - 串口栏常驻三个页签与昼夜按钮之间。
   - 第一页删除原串口行，2×3 卡片网格向上扩展。
   - `console_tab.serial_bar` 保留为同一实例的兼容别名。

4. 第三页
   - 取消最外层大卡片。
   - 第一排为独立 `UART BRIDGE` 卡。
   - 第二排为独立 `TRANSMIT`、`RECEIVE` 卡。
   - 透传数据与状态机行为未改变。

5. 图表工具栏
   - `SAMPLE RATE` 使用明确的展示字体角色。
   - 采样框使用 JetBrains Mono。
   - `CLEAR DATA` 使用与工具栏一致的展示字体。
   - 数值框和按钮统一为 40px 高并垂直居中。

## 验证证据

- TDD 新增目标断言：先复现 6 个失败，再实现至通过。
- 全量测试：`165 passed`。
- Python 编译：退出码 0。
- 视觉回归：`16 capture(s)` 全部通过。
- PyInstaller：构建成功。
- 打包产物 `--fake`：运行五秒后仍存活。
- EXE 大小：`77,908,634 bytes`，即 `74.30 MiB`。

## 视觉截图

- `docs/iteration_global_header_console_dark.png`
- `docs/iteration_global_header_console_light.png`
- `docs/iteration_global_header_charts_dark.png`
- `docs/iteration_global_header_passthrough_dark.png`

## 保留项

- `env/release` 未删除、未重建，可继续复用。
- 用户已有的视觉路线图修改未被覆盖或回退。
- 当前修改保留在现有工作区，未自动提交或推送。
