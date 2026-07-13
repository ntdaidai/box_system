#!/usr/bin/env python3
"""温湿度传感器 (WS3000-485) 数据读取
协议: Modbus RTU, 功能码 03, 读保持寄存器
波特率: 9600, 数据位: 8, 停止位: 1, 无校验
"""

import struct
from app.sensors.base import SensorBase, read_registers


class TempHumiditySensor(SensorBase):
    NAME = "温湿度传感器"
    DEFAULT_PORT = "/dev/ttyCH341USB1"
    DEFAULT_BAUD = 9600
    DEFAULT_ADDR = 0x01
    READ_INTERVAL = 1.0

    def read_once(self) -> dict:
        raw = read_registers(self.serial_port, self.addr, start=0x0000, count=2)
        if len(raw) < 4:
            raise ValueError(f"数据长度不足: 需要4字节, 收到{len(raw)}字节")

        temp_raw = struct.unpack('>h', raw[0:2])[0]
        humi_raw = struct.unpack('>H', raw[2:4])[0]

        return {
            "temperature": round(temp_raw / 10.0, 1),  # 温度 ℃
            "humidity": round(humi_raw / 10.0, 1),     # 湿度 %
        }
