"""传感器数据环形缓冲 + 多通道管理.

每个通道 (e.g. 'batt_v', 'ntc1_c') 存一组 (timestamp, value).
默认保留最近 5 分钟数据, 自动滚动.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class Series:
    """一条曲线的数据."""
    name: str
    color: str
    unit: str
    times: deque[float]  # 相对秒 (从第一个样本起算)
    values: deque[float]

    def append(self, t: float, v: Optional[float]) -> None:
        if v is None:
            return
        self.times.append(t)
        self.values.append(v)

    def trim(self, t_min: float) -> None:
        while self.times and self.times[0] < t_min:
            self.times.popleft()
            self.values.popleft()

    def as_arrays(self) -> tuple[np.ndarray, np.ndarray]:
        return np.array(self.times), np.array(self.values)


class DataBuffer:
    """所有传感数据 buffer.

    t0 是 buffer 创建时刻, 之后所有时间都是 t - t0 的相对秒数.
    """

    WINDOW_SECONDS = 180.0
    MAX_SAMPLES_PER_CHANNEL = 2000

    # 通道定义: name -> (color, unit)
    CHANNELS = {
        "batt_v":   ("#4ade80", "V"),
        "batt_ntc": ("#60a5fa", "°C"),
        "ntc1_c":   ("#facc15", "°C"),
        "ntc2_c":   ("#fb923c", "°C"),
        "ntc3_c":   ("#f87171", "°C"),
        "motor_i":  ("#a78bfa", "A"),
    }

    def __init__(self) -> None:
        self._t0 = time.monotonic()
        self.series: dict[str, Series] = {
            name: Series(
                name=name,
                color=color,
                unit=unit,
                times=deque(maxlen=self.MAX_SAMPLES_PER_CHANNEL),
                values=deque(maxlen=self.MAX_SAMPLES_PER_CHANNEL),
            )
            for name, (color, unit) in self.CHANNELS.items()
        }
        self._last_tick: Optional[int] = None  # 用 SENSE 的 tick 防重复

    def feed_sense(self, sense) -> None:
        """从 SenseData 喂数据. 用 tick 去重."""
        if sense is None:
            return
        if self._last_tick == sense.tick:
            return
        self._last_tick = sense.tick

        t = time.monotonic() - self._t0
        # 用 helper 把字符串转成数值
        from .ui.widgets.battery_card import parse_amps, parse_celsius, parse_volts

        for name, parser in [
            ("batt_v", parse_volts),
            ("batt_ntc", parse_celsius),
            ("ntc1_c", parse_celsius),
            ("ntc2_c", parse_celsius),
            ("ntc3_c", parse_celsius),
            ("motor_i", parse_amps),
        ]:
            raw = getattr(sense, name)
            self.series[name].append(t, parser(raw))

        self.trim_to(t)

    def trim_to(self, elapsed_seconds: float) -> None:
        cutoff = elapsed_seconds - self.WINDOW_SECONDS
        for series in self.series.values():
            series.trim(cutoff)

    def reset(self) -> None:
        for s in self.series.values():
            s.times.clear()
            s.values.clear()
        self._t0 = time.monotonic()
        self._last_tick = None
