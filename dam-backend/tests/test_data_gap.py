#!/usr/bin/env python3
"""测试7天数据中断问题的分析"""

import sys
import types

# 模拟 loguru
class FakeLogger:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None

sys.modules.setdefault("loguru", types.SimpleNamespace(logger=FakeLogger()))

from app.services.iotdb_service import (
    build_history_window,
    aggregate_history_points,
)

def test_data_gap_analysis():
    """演示数据中断的原因"""
    print("=" * 60)
    print("分析7天数据中断问题")
    print("=" * 60)

    # 模拟当前时间: 2026-07-03 12:00:00
    now_ms = 1783056000000  # 2026-07-03 12:00:00 UTC+8

    window = build_history_window("7d", now_ms)
    print(f"\n时间窗口配置:")
    print(f"  范围: 7天")
    print(f"  开始: {window['start_ms']} ({window['start_ms']/1000})")
    print(f"  结束: {window['end_ms']} ({window['end_ms']/1000})")
    print(f"  采样间隔: {window['sample_ms']/1000/60:.0f} 分钟")
    print(f"  最大点数: {window['max_point_count']}")

    # 模拟场景1: 正常数据（所有时间段都有数据）
    print("\n" + "=" * 60)
    print("场景1: 正常情况 - 所有时间段都有数据")
    print("=" * 60)

    sample_ms = window["sample_ms"]
    start_ms = window["start_ms"]
    end_ms = window["end_ms"]

    # 生成完整的7天数据，每小时一个点
    full_data = []
    current = start_ms
    while current <= end_ms:
        full_data.append({
            "timestamp": current / 1000.0,
            "data": {"temperature": 25.0 + (current % 100) / 100}
        })
        current += sample_ms

    result = aggregate_history_points(full_data, "temp_humidity", window)
    print(f"  输入数据点数: {len(full_data)}")
    print(f"  输出数据点数: {len(result)}")
    print(f"  预期点数: {window['max_point_count']}")
    print(f"  数据完整: {'是' if len(result) == window['max_point_count'] else '否'}")

    # 模拟场景2: 中间有3天数据缺失
    print("\n" + "=" * 60)
    print("场景2: 中间有3天数据缺失（模拟服务中断）")
    print("=" * 60)

    gap_data = []
    current = start_ms
    # 假设中间3天（第3-5天）服务中断，没有数据
    gap_start = start_ms + 2 * 24 * 3600 * 1000  # 第3天开始
    gap_end = start_ms + 5 * 24 * 3600 * 1000    # 第5天结束

    while current <= end_ms:
        # 跳过中间3天的数据
        if gap_start <= current <= gap_end:
            current += sample_ms
            continue
        gap_data.append({
            "timestamp": current / 1000.0,
            "data": {"temperature": 25.0 + (current % 100) / 100}
        })
        current += sample_ms

    result_gap = aggregate_history_points(gap_data, "temp_humidity", window)
    print(f"  输入数据点数: {len(gap_data)}")
    print(f"  输出数据点数: {len(result_gap)}")
    print(f"  预期点数: {window['max_point_count']}")
    print(f"  数据缺失: {window['max_point_count'] - len(result_gap)} 个点")
    print(f"  中断时间: 3天 (第3天到第5天)")

    # 分析具体缺失的时间段
    if result_gap:
        timestamps = [p["timestamp"] for p in result_gap]
        gaps = []
        for i in range(1, len(timestamps)):
            diff_hours = (timestamps[i] - timestamps[i-1]) / 3600
            if diff_hours > 1.5:  # 超过1.5小时认为有间隔
                gaps.append({
                    "from": timestamps[i-1],
                    "to": timestamps[i],
                    "hours": diff_hours
                })

        if gaps:
            print(f"\n  检测到的数据间隔:")
            for gap in gaps:
                from_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(gap["from"]))
                to_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(gap["to"]))
                print(f"    {from_time} -> {to_time}: 间隔 {gap['hours']:.1f} 小时")

    # 模拟场景3: 间歇性数据丢失（随机缺失一些点）
    print("\n" + "=" * 60)
    print("场景3: 间歇性数据丢失（传感器偶尔读取失败）")
    print("=" * 60)

    import random
    random.seed(42)  # 固定随机种子以便复现

    intermittent_data = []
    current = start_ms
    missing_count = 0

    while current <= end_ms:
        # 10%的概率丢失数据
        if random.random() < 0.1:
            missing_count += 1
            current += sample_ms
            continue
        intermittent_data.append({
            "timestamp": current / 1000.0,
            "data": {"temperature": 25.0 + (current % 100) / 100}
        })
        current += sample_ms

    result_intermittent = aggregate_history_points(intermittent_data, "temp_humidity", window)
    print(f"  输入数据点数: {len(intermittent_data)}")
    print(f"  输出数据点数: {len(result_intermittent)}")
    print(f"  预期点数: {window['max_point_count']}")
    print(f"  随机缺失点数: {missing_count}")
    print(f"  数据完整率: {len(result_intermittent)/window['max_point_count']*100:.1f}%")

    # 总结
    print("\n" + "=" * 60)
    print("总结: 数据中断的可能原因")
    print("=" * 60)
    print("""
1. 服务中断: 采集服务在某些时间段没有运行
   - 服务器重启、崩溃或维护
   - Docker容器停止或重建
   - 网络问题导致服务不可用

2. 传感器故障: 传感器在某些时间段无法读取数据
   - 串口连接断开
   - 传感器硬件故障
   - 串口权限问题

3. IoTDB写入失败: 数据采集成功但写入数据库失败
   - IoTDB服务不可用
   - 网络连接问题
   - 数据格式错误

4. 数据清理: 历史数据被意外删除或清理
   - IoTDB数据保留策略
   - 手动清理操作

建议排查步骤:
1. 检查服务日志，查看是否有错误或警告
2. 检查IoTDB中的原始数据，确认数据是否真的缺失
3. 检查传感器采集服务的运行状态
4. 检查IoTDB的写入状态（通过 /api/sensor/history/status 接口）
""")


if __name__ == "__main__":
    import time
    test_data_gap_analysis()
