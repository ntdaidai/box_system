"""健康检查与系统运行状态接口"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict
from loguru import logger
import httpx
import os
import time
import threading

# 记录服务启动时间
_SERVICE_START_TIME = time.time()

# 记录第一个请求时间（用于计算系统运行时长）
_first_request_time = None
_lock = threading.Lock()

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    services: Dict[str, str]


class SystemInfoResponse(BaseModel):
    code: int
    data: dict = {}


# ── 健康检查 ────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health_check(req: Request):
    """服务健康检查"""
    services = {}
    all_healthy = True

    # 检查 Qwen3-VL-8B
    from app.core.config import settings
    try:
        client = req.app.state.http_client
        resp = await client.get(f"{settings.VLLM_QWEN3VL_URL}/v1/models")
        if resp.status_code == 200:
            services["qwen3-vl-8b"] = "healthy"
        else:
            services["qwen3-vl-8b"] = "unhealthy"
            all_healthy = False
    except Exception as e:
        services["qwen3-vl-8b"] = "unreachable"
        all_healthy = False
        logger.warning(f"Qwen3-VL-8B 不可达: {e}")

    if not all_healthy:
        raise HTTPException(
            status_code=503,
            detail={"status": "unhealthy", "services": services}
        )

    return HealthResponse(status="healthy", services=services)


# ── 系统运行状态 ────────────────────────────────────────────

def _get_cpu_percent() -> float:
    """获取 CPU 使用率（非阻塞，取 1 秒间隔）"""
    try:
        import psutil
        return round(psutil.cpu_percent(interval=0.5), 1)
    except Exception:
        # psutil 不可用时，从 /proc/stat 粗略估算
        try:
            with open("/proc/stat", "r") as f:
                for line in f:
                    if line.startswith("cpu "):
                        parts = line.split()
                        # idle / total 的简化计算
                        total = sum(int(x) for x in parts[1:])
                        idle = int(parts[4])
                        # 无法精确算实时利用率，返回占位值
                        return 0.0
        except Exception:
            return 0.0


def _get_memory_info() -> dict:
    """获取内存信息"""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024 ** 3), 1),
            "used_gb": round(mem.used / (1024 ** 3), 1),
            "available_gb": round(mem.available / (1024 ** 3), 1),
            "percent": round(mem.percent, 1),
        }
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "available_gb": 0, "percent": 0.0}


def _get_disk_info() -> dict:
    """获取磁盘信息（根目录）"""
    try:
        import psutil
        disk = psutil.disk_usage("/")
        return {
            "total_gb": round(disk.total / (1024 ** 3), 1),
            "used_gb": round(disk.used / (1024 ** 3), 1),
            "free_gb": round(disk.free / (1024 ** 3), 1),
            "percent": round(disk.percent, 1),
        }
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0.0}


def _get_system_uptime() -> float:
    """获取系统运行时长（小时），从 /proc/uptime 读取"""
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])
        return round(uptime_seconds / 3600, 1)
    except Exception:
        return 0.0


def _get_gpu_info() -> dict:
    """获取 GPU 状态信息（Jetson 平台使用 tegrastats，通用平台回退 nvidia-smi）

    返回字段：
      - available: 是否获取成功
      - vendor: GPU 厂商（如 "NVIDIA Jetson Orin"）
      - utilization_percent: GPU 使用率（0-100）
      - memory: {total_mb, used_mb, percent}
      - temperature_c: 温度（摄氏度）
      - power_w: 当前功耗（瓦）
      - source: 数据来源（"tegrastats" / "nvidia-smi" / "none"）
    """
    result = {
        "available": False,
        "vendor": "unknown",
        "utilization_percent": 0.0,
        "memory": {"total_mb": 0, "used_mb": 0, "percent": 0.0},
        "temperature_c": 0.0,
        "power_w": 0.0,
        "source": "none",
    }

    # ── 方案一：Jetson 平台使用 tegrastats ────────────────────
    # tegrastats 是持续输出命令，需要读取一行就立刻关闭
    # 输出格式示例：
    #   06-30-2026 13:06:01 RAM 54671/62828MB (lfb 5x2MB) SWAP ... GR3D_FREQ 0% cpu@47.281C ... VDD_GPU_SOC 2783mW/2783mW
    try:
        import subprocess
        import re
        import select

        proc = subprocess.Popen(
            ["tegrastats", "--interval", "1000"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, start_new_session=True,
        )

        # 等待最多 2 秒读取第一行输出
        line = ""
        deadline = time.time() + 2.0
        while time.time() < deadline:
            ready, _, _ = select.select([proc.stdout], [], [], 0.2)
            if ready:
                line = proc.stdout.readline()
                if line:
                    break

        # 终止 tegrastats
        proc.kill()
        try:
            proc.wait(timeout=1)
        except Exception:
            pass

        line = line.strip()
        if line and ("GR3D_FREQ" in line or "RAM" in line):
            result["source"] = "tegrastats"
            result["vendor"] = "NVIDIA Jetson"
            result["available"] = True

            # 解析 GPU 使用率 (GR3D_FREQ xx%)
            m = re.search(r"GR3D_FREQ\s+(\d+)%", line)
            if m:
                result["utilization_percent"] = float(m.group(1))

            # 解析 RAM（单位 MB）
            m = re.search(r"RAM\s+(\d+)/(\d+)MB", line)
            if m:
                used = int(m.group(1))
                total = int(m.group(2))
                result["memory"] = {
                    "used_mb": used,
                    "total_mb": total,
                    "percent": round(used / total * 100, 1) if total else 0.0,
                }

            # 解析温度（cpu@xxC 是 Jetson Orin 上的 GPU 温度命名）
            m = re.search(r"cpu[@]?([0-9.]+)C", line)
            if m:
                result["temperature_c"] = float(m.group(1))

            # 解析 GPU 功耗 (VDD_GPU_SOC xxxmW)
            m = re.search(r"VDD_GPU_SOC\s+(\d+)mW", line)
            if m:
                result["power_w"] = round(int(m.group(1)) / 1000, 2)

            return result
    except FileNotFoundError:
        pass  # tegrastats 不存在，走 nvidia-smi 兜底
    except Exception as e:
        logger.warning(f"tegrastats 读取失败: {e}")

    # ── 方案二：兜底使用 nvidia-smi（独立显卡环境） ─────────
    try:
        import subprocess
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,utilization.gpu,memory.total,memory.used,temperature.gpu,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        )
        if out.returncode == 0 and out.stdout.strip():
            line = out.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                result.update({
                    "source": "nvidia-smi",
                    "vendor": parts[0] or "NVIDIA",
                    "available": True,
                    "utilization_percent": float(parts[1]) if parts[1] != "[Not Supported]" else 0.0,
                    "memory": {
                        "total_mb": int(float(parts[2])),
                        "used_mb": int(float(parts[3])),
                        "percent": round(int(float(parts[3])) / int(float(parts[2])) * 100, 1) if parts[2] != "0" else 0.0,
                    },
                    "temperature_c": float(parts[4]) if parts[4] not in ("[Not Supported]", "") else 0.0,
                    "power_w": float(parts[5]) if parts[5] not in ("[Not Supported]", "") else 0.0,
                })
                return result
    except Exception as e:
        logger.warning(f"nvidia-smi 读取失败: {e}")

    return result


@router.get("/system/info", response_model=SystemInfoResponse)
async def get_system_info(req: Request):
    """获取系统运行状态信息"""
    # 检查 AI 模型状态
    ai_model_status = "unknown"
    try:
        from app.core.config import settings
        client = req.app.state.http_client
        resp = await client.get(f"{settings.VLLM_QWEN3VL_URL}/v1/models")
        ai_model_status = "healthy" if resp.status_code == 200 else "unhealthy"
    except Exception:
        ai_model_status = "unreachable"

    # 检查传感器采集器状态
    from app.services.sensor_collector import sensor_collector
    collector_running = sensor_collector.running if sensor_collector else False

    # 获取传感器设备状态
    sensor_status = sensor_collector.get_all_devices_status() if sensor_collector else {}
    total_sensors = len(sensor_status)
    online_sensors = sum(1 for s in sensor_status.values() if s.get("status") == "online")
    offline_sensors = total_sensors - online_sensors

    # 组装响应数据
    data = {
        "cpu_percent": _get_cpu_percent(),
        "gpu": _get_gpu_info(),
        "memory": _get_memory_info(),
        "disk": _get_disk_info(),
        "system_uptime_hours": _get_system_uptime(),
        "service_uptime_hours": round((time.time() - _SERVICE_START_TIME) / 3600, 1),
        "sensor_collector_running": collector_running,
        "ai_model": ai_model_status,
        "sensor_count": {
            "total": total_sensors,
            "online": online_sensors,
            "offline": offline_sensors,
        },
        "sensor_status": sensor_status,
    }

    return SystemInfoResponse(code=200, data=data)
