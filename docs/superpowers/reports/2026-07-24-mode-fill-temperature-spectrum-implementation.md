# 电机模式填充与温度色谱仪表实施报告

日期：2026-07-24
对应规格：`docs/superpowers/specs/2026-07-23-mode-fill-temperature-spectrum-design.md`

## 实施结果

- 电机模式标题框的边框、文字、辉光和内部渐变填充均随当前模式语义色变化。
- 模式填充由主题层混色生成；深色主题使用更克制的混合强度，浅色主题保留足够对比。
- 温度仪表量程固定为 `0–100°C`；负温液位归零，超过 100°C 液位封顶，但文字保留真实读数。
- 温度使用冷色青蓝、正常青绿、偏暖琥珀、警告橙和危险红五段主题色。
- 仪表轨道显示弱化完整温谱，当前液位显示强化温谱。
- 旧版液位顶部发光圆泡已删除，改为窄高亮读数线。
- 温度数值文字跟随当前温区颜色；无数据时仪表保持中性，不显示温谱。
- 视觉审计种子覆盖 `12 / 36 / 58 / 84°C` 四个代表区间。

## 自动验证

最终命令：

```powershell
& 'env\release\Scripts\python.exe' -m compileall -q stem_hub_host
& 'env\release\Scripts\python.exe' -m pytest tests -q
& 'env\release\Scripts\python.exe' tools\check_visual_regression.py
```

结果：

- Python 编译：退出码 0
- pytest：`159 passed`
- 视觉回归：`visual regression passed: 16 capture(s)`

pytest 仅报告一条缓存目录写入权限警告，不影响测试执行或应用行为。

## 打包验证

复用既有 `env\release`，未删除、重建或升级环境。

```text
Build complete
PACKAGED_APP_RUNNING_AFTER_5S=True
EXE_BYTES=77909561
EXE_MIB=74.30
```

产物：`dist/stem-hub-host.exe`

启动测试使用 `--fake`，运行五秒后仅结束该次测试进程，没有连接真实串口。

## 视觉证据

- 深色主题：`docs/iteration_mode_temperature_dark.png`
- 浅色主题：`docs/iteration_mode_temperature_light.png`
- 黄金截图：`tests/golden/visual/`

## 保留项

- `env/release` 原样保留，后续可继续复用。
- 用户原有的 `docs/superpowers/plans/2026-07-23-visual-elevation-roadmap.md` 修改未被覆盖或回退。
