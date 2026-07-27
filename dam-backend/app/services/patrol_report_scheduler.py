"""Background scheduler for automatic daily patrol report generation."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Optional

from loguru import logger

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.patrol_report_service import (
    generate_daily_patrol_report,
    generated_report_pair_exists,
)


class PatrolReportScheduler:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if not settings.PATROL_REPORT_AUTO_ENABLED:
            logger.info("自动巡查日报调度未启用")
            return
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"自动巡查日报调度已启动: 每天 {settings.PATROL_REPORT_AUTO_TIME}")

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
        while True:
            await asyncio.sleep(seconds_until_next_run(settings.PATROL_REPORT_AUTO_TIME))
            await asyncio.to_thread(self.generate_today_if_absent)

    def generate_today_if_absent(self) -> None:
        report_date = dt.date.today()
        db = SessionLocal()
        try:
            if generated_report_pair_exists(
                user_id=settings.PATROL_REPORT_USER_ID,
                report_date=report_date,
            ):
                logger.info(f"{report_date} 自动巡查日报已存在，跳过生成")
                return
            generate_daily_patrol_report(
                db,
                report_date=report_date,
                user_id=settings.PATROL_REPORT_USER_ID,
                user_name=settings.PATROL_REPORT_USER_NAME,
            )
            logger.info(f"{report_date} 自动巡查日报已生成")
        except Exception as exc:
            logger.warning(f"{report_date} 自动巡查日报生成失败: {exc}")
        finally:
            db.close()


def seconds_until_next_run(time_text: str) -> float:
    try:
        hour_text, minute_text = time_text.split(":", 1)
        hour = max(0, min(23, int(hour_text)))
        minute = max(0, min(59, int(minute_text)))
    except (TypeError, ValueError):
        hour, minute = 23, 55

    now = dt.datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += dt.timedelta(days=1)
    return (target - now).total_seconds()


patrol_report_scheduler = PatrolReportScheduler()
