#!/usr/bin/env python3
"""翻斗式雨量计数据读取 (Modbus-RTU over RS485)
协议: RS485 Modbus-RTU, 默认地址01, 波特率9600, 无校验, 8数据位, 1停止位
"""

import struct
from app.sensors.base import SensorBase, read_registers, bcd_to_str


class RainSensor(SensorBase):
    NAME = "翻斗式雨量计"
    DEFAULT_PORT = "/dev/ttyCH341USB3"
    DEFAULT_BAUD = 9600
    DEFAULT_ADDR = 0x01
    READ_INTERVAL = 1.0

    def read_once(self) -> dict:
        raw = read_registers(self.serial_port, self.addr, start=0x0000, count=0x0A)
        if len(raw) < 20:
            raise ValueError(f"数据长度不足: 需要20字节, 收到{len(raw)}字节")

        regs = struct.unpack(">HHHHHHHHHH", raw[:20])

        max_time_str = f"{bcd_to_str(regs[7] >> 8)}:{bcd_to_str(regs[7] & 0xFF)}"
        min_time_str = f"{bcd_to_str(regs[9] >> 8)}:{bcd_to_str(regs[9] & 0xFF)}"

        return {
            "today_rain":     round(regs[0] * 0.1, 1),   # 当天降雨量 mm
            "instant_rain":   round(regs[1] * 0.1, 1),   # 瞬时降雨量 mm
            "yesterday_rain": round(regs[2] * 0.1, 1),   # 昨日降雨量 mm
            "total_rain":     round(regs[3] * 0.1, 1),   # 总降雨量 mm
            "hour_rain":      round(regs[4] * 0.1, 1),   # 小时降雨量 mm
            "last_hour_rain": round(regs[5] * 0.1, 1),   # 上小时降雨量 mm
            "max_24h_rain":   round(regs[6] * 0.1, 1),   # 24h最大降雨量 mm
            "max_24h_time":   max_time_str,               # 24h最大降雨时间
            "min_24h_rain":   round(regs[8] * 0.1, 1),   # 24h最小降雨量 mm
            "min_24h_time":   min_time_str,               # 24h最小降雨时间
        }
