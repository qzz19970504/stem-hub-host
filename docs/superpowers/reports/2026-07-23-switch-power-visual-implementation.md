# Switch、功率通路与视觉体系实施报告

日期：2026-07-23  
对应设计：
`docs/superpowers/specs/2026-07-23-switch-power-sequence-visual-regression-design.md`

## 1. Switch（B 方案）

右上角五个输出 Switch 已统一为成熟的紧凑比例：

- 轨道：60×36 px
- 拨片：28 px
- 两端间距：4 px
- 宽高比：1.667
- 拨片：100% 不透明白色

几何、边框、焦点、阴影和动画参数均来自
`stem_hub_host/ui/theme.py`。契约测试同时检查 Dark/Light、开/关状态、
尺寸、拨片位置和中心像素不透明度。

## 2. 充放电功率通路

专业命名保持为 `CHARGE`（充电通路）、`DISCHARGE`（放电通路）和
`OFF`（通路关闭）。

进入充电模式严格执行：

```text
AT+MP4317=OFF
等待 OK
AT+LM51770=OFF
等待 OK
AT+LM51770=ON
```

进入放电模式严格执行：

```text
AT+LM51770=OFF
等待 OK
AT+MP4317=OFF
等待 OK
AT+MP4317=ON
```

实现位于 `stem_hub_host/controller.py`。每一步由异步回包驱动，前一条
没有成功便不会发送下一条；任一 OFF 失败会终止后续 ON；目标 ON 失败
会结束状态机并保持 UI 未开启。快速连续切换仍以完整三段序列串行处理。

## 3. 第一阶段：统一设计令牌

`stem_hub_host/ui/theme.py` 现在是共享视觉参数的单一来源，集中维护：

- 日夜主题语义色
- Switch 和通用控件几何
- 圆角、边框、焦点描边
- 4 px 间距体系和布局组合
- 阴影、辉光、禁用透明度
- 快速、标准和遥测动画时长

`stem_hub_host/ui/style.qss` 不再包含十六进制颜色字面量，全部使用具名
占位符；`stem_hub_host/ui/stylesheet.py` 严格解析令牌，遇到未知令牌会
立即报错。Dark/Light 共用同一份 QSS 结构。

## 4. 第五阶段：黄金截图视觉回归

新增工具：

- `tools/update_visual_baselines.py`：显式更新黄金基线
- `tools/check_visual_regression.py`：只读基线并执行回归检查
- `stem_hub_host/visual_audit.py`：固定输入与截图矩阵
- `stem_hub_host/visual_regression.py`：像素差异指标

覆盖矩阵：

- Dark / Light
- Console / Charts / Passthrough
- 固定窗口 1600×900
- 全屏审计尺寸 1920×1080
- Console Connected / Disconnected

共 16 张图片，保存在 `tests/golden/visual/`。每张图片在
`manifest.json` 中记录文件名、SHA-256、像素尺寸、主题、页面、状态、
视图和工具版本。

验收阈值：

- 尺寸完全一致
- 平均 RGB 绝对差 ≤ 3/255
- 任一通道差值 > 12 的像素占比 ≤ 1%

截图工具固定字体、主题、尺寸、fake 遥测、故障、输出和日志，并在截图
前把电量环、温度计和 Switch 直接置于动画终态。普通检查将当前截图放到
`build/visual-regression/current/`，不会覆盖版本控制内的黄金基线。

## 5. 使用方式

```powershell
# 快速行为和视觉契约测试
python -m pytest tests -q

# 完整视觉审计
python tools/check_visual_regression.py

# 仅在人工确认视觉变化后更新基线
python tools/update_visual_baselines.py
```

## 6. 最终验证与发布产物

在合并后的 `master` 上完成验证：

- `pytest tests -q`：139 passed
- `compileall`：通过
- 视觉审计：16/16 通过，当前环境平均 RGB 差异均为 0
- PyInstaller 6.21.0：构建成功
- `--fake` 启动验证：运行 5 秒仍存活，通过
- 发布文件：`dist/stem-hub-host.exe`
- 文件大小：77,905,058 bytes（74.30 MiB）
- SHA-256：
  `97021194CA7954CEF4C310FA29933D3014A84D9D785B82091035AD855181BB71`

构建清单包含 Rajdhani、JetBrains Mono（Regular/Bold）、Noto Sans SC
四个字体文件以及 `style.qss`，未发现 MKL/TBB 文件。发布虚拟环境
`env/release` 已保留，不参与清理，可继续复用。
