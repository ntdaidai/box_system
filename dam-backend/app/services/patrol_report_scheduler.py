"""Background scheduler for automatic daily patrol report generation."""

from __future__ import annotations

from loguru import logger


class PatrolReportScheduler:
    def __init__(self):
        self._task = None

    async def start(self) -> None:
        logger.info("自动巡查日报调度已暂停：等待新版报告模板")

    async def stop(self) -> None:
        self._task = None


patrol_report_scheduler = PatrolReportScheduler()
