#!/usr/bin/env python3
"""风速风向传感器数据读取 (Modbus-RTU over RS485)
协议: RS485 Modbus-RTU, 默认地址01, 波特率9600, 无校验, 8数据位, 1停止位
"""

import struct
from app.sensors.base import SensorBase, read_registers


# 风向方位映射表
WIND_DIRECTION_16 = {
    0x00: "北",     0x01: "北东北", 0x02: "东北",   0x03: "东东北",
    0x04: "东",     0x05: "东东南", 0x06: "东南",   0x07: "南东南",
    0x08: "南",     0x09: "南西南", 0x0A: "西南",   0x0B: "西西南",
    0x0C: "西",     0x0D: "西西北", 0x0E: "西北",   0x0F: "北西北",
}


class WindSensor(SensorBase):
    NAME = "风速风向传感器"
    DEFAULT_PORT = "/dev/ttyCH341USB2"
    DEFAULT_BAUD = 9600
    DEFAULT_ADDR = 0x01
    READ_INTERVAL = 1.0

    def read_once(self) -> dict:
        raw = read_registers(self.serial_port, self.addr, start=0x0000, count=5)
        if len(raw) < 10:
            raise ValueError(f"数据长度不足: 需要10字节, 收到{len(raw)}字节")

        regs = struct.unpack(">HHHHH", raw[:10])
        wind_speed_ms  = round(regs[0] * 0.1,  1)   # 风速 m/s
        wind_level     = regs[1]                     # 风级
        wind_speed_kmh = round(regs[2] * 0.01, 2)   # 风速 km/h
        wind_angle     = round(regs[3] * 0.1,  1)   # 风向角度
        wind_dir_code  = regs[4]                     # 风向编码
        wind_direction = WIND_DIRECTION_16.get(wind_dir_code, f"未知({wind_dir_code})")

        return {
            "wind_speed_ms":  wind_speed_ms,
            "wind_level":     wind_level,
            "wind_speed_kmh": wind_speed_kmh,
            "wind_angle":     wind_angle,
            "wind_direction": wind_direction,
            "wind_dir_code":  wind_dir_code,
        }
