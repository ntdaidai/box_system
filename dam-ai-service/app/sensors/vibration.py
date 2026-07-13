#!/usr/bin/env python3
"""WTVB05-485 振动传感器数据读取
通过 VB05 SDK 以后台线程持续读取加速度、速度、角度、位移、频率等数据。
"""

import time
import logging

from app.sensors.device_model import DeviceModel

logger = logging.getLogger(__name__)

# (寄存器地址, 名称, 单位, 小数位数)
# 寄存器映射来源: VB05新版说明书-1021x 6.1.3 寄存器地址表
REGISTERS = [
    # 三轴加速度 (瞬时值)
    (0x34, "加速度X",     "g",    4),
    (0x35, "加速度Y",     "g",    4),
    (0x36, "加速度Z",     "g",    4),
    # 三轴加速度幅值 (峰值)
    (0x37, "加速度幅值X",  "g",    4),
    (0x38, "加速度幅值Y",  "g",    4),
    (0x39, "加速度幅值Z",  "g",    4),
    # 三轴振动速度幅值
    (0x3A, "速度X",       "mm/s", 2),
    (0x3B, "速度Y",       "mm/s", 2),
    (0x3C, "速度Z",       "mm/s", 2),
    # 温度
    (0x40, "温度",        "℃",   2),
    # 三轴振动位移幅值
    (0x41, "位移X",       "mm",   3),
    (0x42, "位移Y",       "mm",   3),
    (0x43, "位移Z",       "mm",   3),
    # 三轴振动频率
    (0x44, "频率X",       "Hz",   1),
    (0x45, "频率Y",       "Hz",   1),
    (0x46, "频率Z",       "Hz",   1),
]


class VibrationSensor:
    """振动传感器封装"""

    NAME = "振动传感器"
    DEFAULT_PORT = "/dev/ttyCH341USB0"
    DEFAULT_BAUD = 9600
    DEFAULT_ADDR = 0x50
    READ_INTERVAL = 1.0

    def __init__(self, port: str = None, addr: int = None):
        self.port = port or self.DEFAULT_PORT
        self.addr = addr or self.DEFAULT_ADDR
        self.device = None

    def open(self):
        """打开设备"""
        try:
            self.device = DeviceModel(
                "VB05振动传感器", self.port, self.DEFAULT_BAUD, self.addr
            )
            self.device.openDevice()
            self.device.startLoopRead()
            time.sleep(0.5)  # 等待数据稳定
            logger.info(f"{self.NAME} 设备已打开: {self.port}")
            return True
        except Exception as e:
            logger.error(f"{self.NAME} 设备打开失败: {e}")
            return False

    def close(self):
        """关闭设备"""
        if self.device:
            try:
                self.device.closeDevice()
                logger.info(f"{self.NAME} 设备已关闭")
            except Exception as e:
                logger.warning(f"{self.NAME} 设备关闭时出错: {e}")

    def read_once(self) -> dict:
        """读取一次振动数据"""
        if not self.device:
            raise RuntimeError("设备未打开")

        data = {}
        for addr, name, unit, decimals in REGISTERS:
            value = self.device.get(str(addr))
            data[name] = value
        return data

    def read_loop(self, callback=None):
        """循环读取数据"""
        if not self.open():
            return

        try:
            while True:
                try:
                    data = self.read_once()
                    ts = time.strftime("%Y-%m-%d %H:%M:%S")
                    logger.debug(f"[{ts}] {self.NAME}: {data}")
                    if callback:
                        callback(data)
                except Exception as e:
                    logger.warning(f"{self.NAME} 读取失败: {e}")

                time.sleep(self.READ_INTERVAL)
        except KeyboardInterrupt:
            logger.info(f"{self.NAME} 已停止")
        finally:
            self.close()
