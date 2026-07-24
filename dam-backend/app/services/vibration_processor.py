#!/usr/bin/env python3
"""振动数据处理器
实现三轴合成、RMS计算、FFT分析、报警判断等功能
"""

import math
import time
from typing import Dict, Any, List, Tuple
from loguru import logger

# 关键参数（硬编码）
SAMPLE_RATE = 100  # 采样率 100Hz
RMS_WINDOW = 100  # RMS窗口 1秒（100个采样点）
FFT_POINTS = 256  # FFT点数
HIGHPASS_CUTOFF = 0.5  # 高通截止频率 Hz
CREST_FACTOR_THRESHOLD = 3.5  # 冲击阈值（峰值因子）
FREQ_DRIFT_THRESHOLD = 15  # 主频偏移阈值 %

# 分级报警阈值
ALERT_THRESHOLDS = {
    "正常": 0.05,
    "关注": 0.10,
    "预警": 0.15,
}


class VibrationProcessor:
    """振动数据处理器"""

    def __init__(self):
        # 数据缓冲区
        self.accel_buffer: List[float] = []  # 加速度合成值缓冲区
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
        # 1. 三轴合成
        total_accel = self.calc_total_acceleration(raw_data)

        # 2. 更新缓冲区
        self.accel_buffer.append(total_accel)
        if len(self.accel_buffer) > RMS_WINDOW:
            self.accel_buffer.pop(0)

        # 3. 计算RMS
        rms = self.calc_rms(self.accel_buffer)

        # 4. 计算峰值因子
        crest_factor = self.calc_crest_factor(self.accel_buffer, rms)

        # 5. FFT求主频
        dominant_freq = self.calc_dominant_freq(self.accel_buffer)

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
        ax = data.get("加速度X", 0) or 0
        ay = data.get("加速度Y", 0) or 0
        az = data.get("加速度Z", 0) or 0
        return math.sqrt(ax**2 + ay**2 + az**2)

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

    def calc_dominant_freq(self, data: List[float]) -> float:
        """FFT求主频

        取256点加Hanning窗，做FFT，在1~20Hz范围内找幅值最大的频率

        Args:
            data: 加速度数据列表

        Returns:
            主频 Hz
        """
        if len(data) < FFT_POINTS:
            return 0.0

        # 取最近256点
        recent = data[-FFT_POINTS:]

        # 加Hanning窗
        window = [0.5 * (1 - math.cos(2 * math.pi * i / (FFT_POINTS - 1))) for i in range(FFT_POINTS)]
        windowed = [recent[i] * window[i] for i in range(FFT_POINTS)]

        # 使用numpy进行FFT
        try:
            import numpy as np

            fft_result = np.fft.fft(windowed)
            freqs = np.fft.fftfreq(FFT_POINTS, 1.0/SAMPLE_RATE)

            # 只取正频率部分，在1-20Hz范围内找最大值
            max_magnitude = 0
            max_freq = 0.0

            for i in range(FFT_POINTS // 2):
                freq = freqs[i]
                if 1.0 <= freq <= 20.0:
                    magnitude = abs(fft_result[i])
                    if magnitude > max_magnitude:
                        max_magnitude = magnitude
                        max_freq = freq

            return max_freq

        except ImportError:
            # 如果没有numpy，使用简化的DFT
            logger.warning("numpy未安装，使用简化DFT算法")
            return self._calc_dominant_freq_dft(recent)

    def _calc_dominant_freq_dft(self, data: List[float]) -> float:
        """简化的DFT算法（不依赖numpy）

        Args:
            data: 数据列表（长度应为FFT_POINTS）

        Returns:
            主频 Hz
        """
        if len(data) < FFT_POINTS:
            return 0.0

        max_magnitude = 0
        max_freq = 0.0

        # 只检查1-20Hz范围
        for freq in range(1, 21):
            # 计算该频率的幅值
            real = 0.0
            imag = 0.0
            for i in range(FFT_POINTS):
                angle = 2 * math.pi * freq * i / SAMPLE_RATE
                real += data[i] * math.cos(angle)
                imag -= data[i] * math.sin(angle)

            magnitude = math.sqrt(real**2 + imag**2)
            if magnitude > max_magnitude:
                max_magnitude = magnitude
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
