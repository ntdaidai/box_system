#!/usr/bin/env python3
"""振动数据处理器
实现三轴合成、RMS计算、FFT分析、报警判断等功能
"""

import math
import time
from typing import Dict, Any, List, Tuple, Optional
from loguru import logger

# 关键参数（硬编码）
SAMPLE_RATE = 10  # 底层Modbus轮询约10Hz
RMS_WINDOW = 10  # RMS窗口约1秒（10个采样点）
FFT_POINTS = 64  # FFT点数，约6.4秒低频运动窗口
MAX_BUFFER_POINTS = max(RMS_WINDOW, FFT_POINTS)
HIGHPASS_CUTOFF = 0.5  # 高通截止频率 Hz
CREST_FACTOR_THRESHOLD = 3.5  # 冲击阈值（峰值因子）
FREQ_DRIFT_THRESHOLD = 15  # 主频偏移阈值 %
FREQ_CLUSTER_TOLERANCE_HZ = 1.0  # 多轴同一模态的频率聚合容差
MIN_AXIS_WEIGHT_RATIO = 0.15  # 参与同一模态聚合的最小轴能量占比
LOW_FREQ_MOTION_RMS_G = 0.03  # 手晃/低频运动优先阈值

# 分级报警阈值
ALERT_THRESHOLDS = {
    "正常": 0.05,
    "关注": 0.10,
    "预警": 0.15,
}


def dominant_freq_from_registers(raw_data: Dict[str, Any]) -> float:
    """根据传感器三轴频率寄存器计算综合主频。"""
    candidates = []
    for axis in ("X", "Y", "Z"):
        freq = _to_float_value(raw_data.get(f"频率{axis}"))
        if freq is None or freq <= 0:
            continue
        weight = _axis_weight(raw_data, axis)
        candidates.append({"axis": axis, "freq": freq, "weight": max(weight, 0.0)})

    if not candidates:
        return 0.0

    max_weight = max(item["weight"] for item in candidates)
    if max_weight <= 0:
        return _median([item["freq"] for item in candidates])

    primary = max(candidates, key=lambda item: item["weight"])
    same_mode = [
        item for item in candidates
        if item["weight"] >= max_weight * MIN_AXIS_WEIGHT_RATIO
        and abs(item["freq"] - primary["freq"]) <= FREQ_CLUSTER_TOLERANCE_HZ
    ]
    total_weight = sum(item["weight"] for item in same_mode)
    if total_weight <= 0:
        return primary["freq"]
    return sum(item["freq"] * item["weight"] for item in same_mode) / total_weight


def _axis_weight(raw_data: Dict[str, Any], axis: str) -> float:
    for key in (f"加速度幅值{axis}", f"速度{axis}", f"位移{axis}", f"加速度{axis}"):
        value = _to_float_value(raw_data.get(key))
        if value is not None:
            return abs(value)
    return 0.0


def _to_float_value(value: Any) -> Optional[float]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _median(values: List[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


class VibrationProcessor:
    """振动数据处理器"""

    def __init__(self, sample_rate: float = SAMPLE_RATE):
        # 数据缓冲区
        self.accel_buffer: List[float] = []  # 加速度合成值缓冲区
        self.axis_buffers: Dict[str, List[float]] = {"x": [], "y": [], "z": []}  # 三轴原始加速度缓冲
        self.sample_rate = float(sample_rate) if sample_rate > 0 else SAMPLE_RATE
        self.rms_history: List[Dict[str, Any]] = []  # RMS历史记录
        self.event_list: List[Dict[str, Any]] = []  # 事件列表

        # 基线主频（初始值，后续可动态更新）
        self.baseline_freq: float = None
        self.baseline_freq_samples: List[float] = []  # 用于计算基线的样本

        # 当前报警状态
        self.current_alert_level = "正常"
        self.alert_start_time = None

        # 最大历史点数
        self.max_history_points = 1440  # 24小时，每分钟一个点
        self.max_events = 100  # 最多保存100个事件

        # 模拟模式标志
        self.simulation_mode = False
        self.simulation_time = 0

    def process_raw_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理原始数据，返回处理后的结果

        Args:
            raw_data: 原始传感器数据，包含加速度X/Y/Z、温度等字段

        Returns:
            处理后的数据字典
        """
        # 1. 三轴合成并更新缓冲区。RMS 使用合成幅值；频谱分析使用三轴原始值，避免幅值化导致主频翻倍。
        total_accel = self.calc_total_acceleration(raw_data)
        self._append_sample(raw_data, total_accel)

        # 3. 计算RMS
        rms = self.calc_rms(self.accel_buffer)

        # 4. 计算峰值因子
        crest_factor = self.calc_crest_factor(self.accel_buffer, rms)

        # 5. 综合主频：优先采用传感器三轴频率寄存器的主振动轴结果；缺失时使用三轴能量合成FFT兜底。
        dominant_freq = self.calc_dominant_freq(raw_data, rms)

        # 6. 更新基线主频
        self._update_baseline_freq(dominant_freq)

        # 7. 计算主频偏移
        freq_drift = self.calc_freq_drift(dominant_freq)

        # 8. 报警判断
        alert_level, alert_reason = self.judge_alert(rms, crest_factor, freq_drift)

        # 9. 记录事件
        self._record_event(alert_level, alert_reason, rms)

        # 10. 记录RMS历史
        self._record_rms_history(rms, dominant_freq)

        return {
            "total_rms": round(rms, 4),
            "dominant_freq": round(dominant_freq, 2),
            "freq_drift_percent": round(freq_drift, 2),
            "crest_factor": round(crest_factor, 2),
            "peak_accel": round(max(self.accel_buffer[-RMS_WINDOW:]) if self.accel_buffer else 0, 4),
            "temperature": raw_data.get("温度", 0),
            "alert_level": alert_level,
            "alert_reason": alert_reason,
            "timestamp": time.time(),
        }

    def calc_total_acceleration(self, data: Dict[str, Any]) -> float:
        """三轴合成：A_total = √(A_x² + A_y² + A_z²)

        Args:
            data: 包含加速度X/Y/Z的数据字典

        Returns:
            合成加速度值
        """
        ax = _to_float_value(data.get("加速度X")) or 0
        ay = _to_float_value(data.get("加速度Y")) or 0
        az = _to_float_value(data.get("加速度Z")) or 0
        return math.sqrt(ax**2 + ay**2 + az**2)

    def _append_sample(self, raw_data: Dict[str, Any], total_accel: float):
        self.accel_buffer.append(total_accel)
        if len(self.accel_buffer) > MAX_BUFFER_POINTS:
            self.accel_buffer.pop(0)

        axis_values = {
            "x": _to_float_value(raw_data.get("加速度X")) or 0.0,
            "y": _to_float_value(raw_data.get("加速度Y")) or 0.0,
            "z": _to_float_value(raw_data.get("加速度Z")) or 0.0,
        }
        for axis, value in axis_values.items():
            self.axis_buffers[axis].append(value)
            if len(self.axis_buffers[axis]) > MAX_BUFFER_POINTS:
                self.axis_buffers[axis].pop(0)

    def calc_rms(self, data: List[float]) -> float:
        """滑动窗口RMS：A_RMS = √( (a₁² + a₂² + ... + aₙ²) / N )

        Args:
            data: 加速度数据列表

        Returns:
            RMS值
        """
        if not data:
            return 0.0

        # 取最近N个点
        n = min(len(data), RMS_WINDOW)
        recent = data[-n:]

        # 计算RMS
        sum_sq = sum(x**2 for x in recent)
        return math.sqrt(sum_sq / n)

    def calc_crest_factor(self, data: List[float], rms: float) -> float:
        """峰值因子：C_f = 窗口内最大幅值 / RMS值

        Args:
            data: 加速度数据列表
            rms: RMS值

        Returns:
            峰值因子
        """
        if rms == 0 or not data:
            return 0.0

        # 取最近N个点
        n = min(len(data), RMS_WINDOW)
        recent = data[-n:]

        # 计算峰值（绝对值最大）
        peak = max(abs(x) for x in recent)
        return peak / rms

    def calc_dominant_freq(self, raw_data: Optional[Dict[str, Any]] = None, rms: Optional[float] = None) -> float:
        """计算综合主频

        传感器已经提供三轴主频寄存器时，综合主频取主振动轴所在模态：
        - 按加速度幅值/速度/位移选择能量最大的轴
        - 如果其它轴频率接近该轴，按能量做小范围加权稳定
        - 不把相距较远的多个频率简单平均，避免产生物理上不存在的主频

        寄存器缺失时，使用三轴原始加速度分别去均值、加Hanning窗、做FFT，
        再按频点合成三轴频谱能量，在1~20Hz范围内找能量峰。

        Returns:
            主频 Hz
        """
        register_freq = self.calc_register_dominant_freq(raw_data or {})
        fft_freq = self.calc_fft_dominant_freq()

        # 手动晃动和低频摆动通常不会稳定写入传感器频率寄存器；
        # 当低频能量明显时，优先展示实际采样序列的低频主频。
        if fft_freq > 0 and (rms or 0) >= LOW_FREQ_MOTION_RMS_G:
            return fft_freq
        if register_freq > 0:
            return register_freq
        return fft_freq

    def calc_register_dominant_freq(self, raw_data: Dict[str, Any]) -> float:
        """根据传感器三轴频率寄存器计算综合主频。"""
        return dominant_freq_from_registers(raw_data)

    def calc_fft_dominant_freq(self) -> float:
        """三轴能量合成FFT求主频。"""
        if any(len(values) < FFT_POINTS for values in self.axis_buffers.values()):
            return 0.0

        window = [0.5 * (1 - math.cos(2 * math.pi * i / (FFT_POINTS - 1))) for i in range(FFT_POINTS)]
        axis_windows = []
        for axis in ("x", "y", "z"):
            recent = self.axis_buffers[axis][-FFT_POINTS:]
            mean_value = sum(recent) / FFT_POINTS
            axis_windows.append([(recent[i] - mean_value) * window[i] for i in range(FFT_POINTS)])

        try:
            import numpy as np

            fft_results = [np.fft.rfft(values) for values in axis_windows]
            freqs = np.fft.rfftfreq(FFT_POINTS, 1.0 / self.sample_rate)
            combined_power = sum(np.abs(result) ** 2 for result in fft_results)

            max_power = 0
            max_freq = 0.0
            max_search_freq = min(20.0, self.sample_rate / 2.0)
            for i in range(1, len(freqs)):
                freq = freqs[i]
                if 1.0 <= freq <= max_search_freq:
                    power = combined_power[i]
                    if power > max_power:
                        max_power = power
                        max_freq = freq

            return float(max_freq)

        except ImportError:
            logger.warning("numpy未安装，使用简化DFT算法")
            return self._calc_dominant_freq_dft(axis_windows)

    def _calc_dominant_freq_dft(self, axis_windows: List[List[float]]) -> float:
        """简化的DFT算法（不依赖numpy）

        Args:
            axis_windows: 三轴去均值加窗后的数据

        Returns:
            主频 Hz
        """
        if not axis_windows or any(len(data) < FFT_POINTS for data in axis_windows):
            return 0.0

        max_power = 0
        max_freq = 0.0
        max_search_freq = min(20, int(self.sample_rate / 2))

        for freq in range(1, max_search_freq + 1):
            power = 0.0
            for data in axis_windows:
                real = 0.0
                imag = 0.0
                for i in range(FFT_POINTS):
                    angle = 2 * math.pi * freq * i / self.sample_rate
                    real += data[i] * math.cos(angle)
                    imag -= data[i] * math.sin(angle)
                power += real**2 + imag**2

            if power > max_power:
                max_power = power
                max_freq = float(freq)

        return max_freq

    def _update_baseline_freq(self, current_freq: float):
        """更新基线主频

        使用前100个有效样本计算平均值作为基线

        Args:
            current_freq: 当前主频
        """
        if current_freq <= 0:
            return

        # 如果还没有基线，收集样本
        if self.baseline_freq is None:
            self.baseline_freq_samples.append(current_freq)
            # 收集100个样本后计算基线
            if len(self.baseline_freq_samples) >= 100:
                self.baseline_freq = sum(self.baseline_freq_samples) / len(self.baseline_freq_samples)
                logger.info(f"基线主频已确定: {self.baseline_freq:.2f} Hz")

    def calc_freq_drift(self, current_freq: float) -> float:
        """计算主频偏移百分比

        Args:
            current_freq: 当前主频

        Returns:
            偏移百分比
        """
        if self.baseline_freq is None or self.baseline_freq == 0:
            return 0.0

        return ((current_freq - self.baseline_freq) / self.baseline_freq) * 100

    def judge_alert(self, rms: float, crest_factor: float, freq_drift: float) -> Tuple[str, str]:
        """报警判断逻辑

        Args:
            rms: RMS值
            crest_factor: 峰值因子
            freq_drift: 主频偏移百分比

        Returns:
            (报警等级, 报警原因)
        """
        level = "正常"
        reason = ""

        # RMS报警判断
        if rms > ALERT_THRESHOLDS["预警"]:
            level = "报警"
            reason = f"振动总RMS={rms:.3f}g"
        elif rms > ALERT_THRESHOLDS["关注"]:
            level = "预警"
            reason = f"振动总RMS={rms:.3f}g"
        elif rms > ALERT_THRESHOLDS["正常"]:
            # 检查是否有冲击信号
            if crest_factor > CREST_FACTOR_THRESHOLD:
                level = "预警"
                reason = f"冲击信号，峰值因子={crest_factor:.1f}"
            else:
                level = "关注"
                reason = f"振动总RMS={rms:.3f}g"
        else:
            level = "正常"
            reason = ""

        # 主频偏移报警（如果已经有更高的报警级别，不降级）
        if abs(freq_drift) > FREQ_DRIFT_THRESHOLD:
            if level in ["正常", "关注"]:
                level = "预警"
            if reason:
                reason += f"，主频偏移{freq_drift:+.1f}%"
            else:
                reason = f"主频偏移{freq_drift:+.1f}%"

        return level, reason

    def _record_event(self, level: str, reason: str, rms: float):
        """记录报警事件

        Args:
            level: 报警等级
            reason: 报警原因
            rms: RMS值
        """
        now = time.time()

        # 检查状态是否变化
        if level != self.current_alert_level:
            # 如果之前是报警状态，记录结束时间
            if self.current_alert_level != "正常" and self.alert_start_time:
                duration = now - self.alert_start_time
                # 更新最后一个事件的持续时间
                if self.event_list:
                    self.event_list[-1]["duration"] = round(duration)

            # 如果新的状态不是正常，记录新事件
            if level != "正常":
                event = {
                    "timestamp": now,
                    "level": level,
                    "reason": reason,
                    "rms": round(rms, 4),
                    "duration": 0,  # 持续时间会在状态变化时更新
                }
                self.event_list.append(event)

                # 限制事件列表长度
                if len(self.event_list) > self.max_events:
                    self.event_list.pop(0)

                self.alert_start_time = now
            else:
                self.alert_start_time = None

            self.current_alert_level = level

    def _record_rms_history(self, rms: float, freq: float):
        """记录RMS历史

        每分钟记录一个点

        Args:
            rms: RMS值
            freq: 主频
        """
        now = time.time()

        # 每60秒记录一个点
        if not self.rms_history or (now - self.rms_history[-1]["timestamp"]) >= 60:
            self.rms_history.append({
                "timestamp": now,
                "rms": round(rms, 4),
                "freq": round(freq, 2),
            })

            # 限制历史点数
            if len(self.rms_history) > self.max_history_points:
                self.rms_history.pop(0)

    def get_rms_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取RMS历史数据

        Args:
            hours: 获取最近N小时的数据

        Returns:
            历史数据列表
        """
        cutoff = time.time() - hours * 3600
        return [p for p in self.rms_history if p["timestamp"] >= cutoff]

    def get_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取事件列表

        Args:
            limit: 返回的最大事件数

        Returns:
            事件列表
        """
        return self.event_list[-limit:]

    def get_status_summary(self) -> Dict[str, Any]:
        """获取状态摘要

        Returns:
            状态摘要字典
        """
        return {
            "current_level": self.current_alert_level,
            "baseline_freq": round(self.baseline_freq, 2) if self.baseline_freq else None,
            "buffer_size": len(self.accel_buffer),
            "history_points": len(self.rms_history),
            "event_count": len(self.event_list),
        }


# 全局单例
vibration_processor = VibrationProcessor()
