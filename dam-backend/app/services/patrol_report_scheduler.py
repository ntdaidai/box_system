"""Generate the previous natural day's patrol report at local midnight."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Optional

from loguru import logger

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.patrol_report_service import (
    generate_daily_patrol_report,
    generated_report_exists,
)


class PatrolReportScheduler:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if not settings.PATROL_REPORT_AUTO_ENABLED:
            logger.info("自动巡检日报调度未启用")
            return
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop(), name="patrol-report-scheduler")
        logger.info(
            f"自动巡检日报调度已启动: 每天 {settings.PATROL_REPORT_AUTO_TIME} "
            "汇总前一自然日"
        )

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run_loop(self) -> None:
        # 服务若在午夜后重启，先补偿昨日缺失的日报，再等待下一次午夜。
        await asyncio.to_thread(self.generate_previous_day_if_absent)
        while True:
            delay = seconds_until_next_run(settings.PATROL_REPORT_AUTO_TIME)
            await asyncio.sleep(delay)
            await asyncio.to_thread(self.generate_previous_day_if_absent)

    def generate_previous_day_if_absent(self, *, today: Optional[dt.date] = None) -> None:
        current_date = today or dt.date.today()
        report_date = current_date - dt.timedelta(days=1)
        db = SessionLocal()
        try:
            if generated_report_exists(
                user_id=settings.PATROL_REPORT_USER_ID,
                report_date=report_date,
            ):
                logger.info(f"{report_date} 每日巡检报告已存在，跳过生成")
                return
            result = generate_daily_patrol_report(
                db,
                report_date=report_date,
                user_id=settings.PATROL_REPORT_USER_ID,
                user_name=settings.PATROL_REPORT_USER_NAME,
            )
            document = result["data"]["document"]
            logger.info(f"{report_date} 每日巡检报告已生成: {document['title']}")
        except Exception:
            logger.exception(f"{report_date} 每日巡检报告生成失败")
        finally:
            db.close()


def seconds_until_next_run(time_text: str, *, now: Optional[dt.datetime] = None) -> float:
    try:
        hour_text, minute_text = str(time_text).split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError
    except (TypeError, ValueError):
        hour, minute = 0, 0
    current = now or dt.datetime.now()
    target = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= current:
        target += dt.timedelta(days=1)
    return (target - current).total_seconds()


patrol_report_scheduler = PatrolReportScheduler()
