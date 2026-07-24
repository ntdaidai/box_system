#!/usr/bin/env python3
"""传感器公共基础模块
提供统一的 Modbus CRC16 计算、串口读寄存器、传感器基类。
"""

import struct
import time
import serial
from loguru import logger


# ─── Modbus CRC16 ────────────────────────────────────────────

def calc_crc16(data: bytes) -> int:
    """计算 Modbus CRC16 校验码"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def bcd_to_str(bcd: int) -> str:
    """将 BCD 字节转为十进制字符串"""
    high = (bcd >> 4) & 0x0F
    low = bcd & 0x0F
    return f"{high}{low}"


# ─── 通用 Modbus 03 读寄存器 ──────────────────────────────────

def read_registers(ser: serial.Serial, addr: int = 0x01,
                   start: int = 0x0000, count: int = 1) -> bytes:
    """发送 Modbus 03 功能码读取寄存器，返回寄存器原始数据 (不含协议头尾)"""
    req = struct.pack(">BBBBH", addr, 0x03, start >> 8, start & 0xFF, count)
    crc = calc_crc16(req)
    req += struct.pack("<H", crc)

    ser.write(req)
    ser.flush()

    # 响应: 地址(1) + 功能码(1) + 字节数(1) + data(N) + CRC(2)
    resp_header = ser.read(3)
    if len(resp_header) < 3:
        raise ValueError(f"响应不完整: 仅收到 {len(resp_header)} 字节")

    byte_count = resp_header[2]
    resp_body = ser.read(byte_count + 2)
    if len(resp_body) < byte_count + 2:
        raise ValueError(
            f"响应数据不完整: 需要 {byte_count + 2} 字节, 收到 {len(resp_body)}"
        )

    full_resp = resp_header + resp_body
    received_crc = struct.unpack("<H", resp_body[byte_count:byte_count + 2])[0]
    calc = calc_crc16(full_resp[:-2])
    if received_crc != calc:
        raise ValueError(
            f"CRC 校验失败: 收到 {received_crc:#06x}, 计算 {calc:#06x}"
        )

    return full_resp[3:3 + byte_count]


# ─── 传感器基类 ──────────────────────────────────────────────

class SensorBase:
    """所有传感器的统一基类，提供串口管理、循环读取框架。"""

    # 子类需覆盖
    NAME = "传感器"
    DEFAULT_PORT = "/dev/ttyCH341USB0"
    DEFAULT_BAUD = 9600
    DEFAULT_ADDR = 0x01
    READ_INTERVAL = 2.0

    def __init__(self, port: str = None, addr: int = None, interval: float = None):
        self.port = port or self.DEFAULT_PORT
        self.addr = addr or self.DEFAULT_ADDR
        self.interval = interval or self.READ_INTERVAL
        self.serial_port = None

    def open(self):
        """打开串口连接"""
        try:
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.DEFAULT_BAUD,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=2.0,
            )
            logger.info(f"{self.NAME} 串口已打开: {self.port}")
            return True
        except serial.SerialException as e:
            logger.error(f"{self.NAME} 串口打开失败: {e}")
            return False

    def close(self):
        """关闭串口连接"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            logger.info(f"{self.NAME} 串口已关闭")

    def read_once(self) -> dict:
        """读取一次数据，返回 dict。子类必须实现。"""
        raise NotImplementedError

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
                except (TimeoutError, ValueError) as e:
                    logger.warning(f"{self.NAME} 读取失败: {e}")
                except serial.SerialException as e:
                    logger.error(f"{self.NAME} 串口错误: {e}")

                time.sleep(self.interval)
        except KeyboardInterrupt:
            logger.info(f"{self.NAME} 已停止")
        finally:
            self.close()
