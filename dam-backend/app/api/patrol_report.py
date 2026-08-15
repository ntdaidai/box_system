"""Automatic patrol report APIs."""

import datetime as dt

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_auth
from app.models.user import User
from app.services.patrol_report_service import (
    build_daily_report_context,
    build_period_report_context,
    generate_daily_patrol_report,
    generate_period_patrol_report,
)


router = APIRouter(prefix="/api/patrol-report", tags=["自动巡查报告"])


class DailyReportGenerateRequest(BaseModel):
    report_date: dt.date = Field(default_factory=dt.date.today, description="报告日期")
    user_id: str = "user_001"
    user_name: str = "管理员"


class PeriodReportGenerateRequest(BaseModel):
    report_date: dt.date = Field(default_factory=dt.date.today, description="周期内任意日期")
    user_id: str = "user_001"
    user_name: str = "管理员"


@router.post("/daily/generate")
async def generate_daily_report(
    payload: DailyReportGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    user_id = payload.user_id or str(getattr(user, "id", "user_001"))
    user_name = payload.user_name or getattr(user, "real_name", None) or getattr(user, "username", "管理员")
    return generate_daily_patrol_report(
        db,
        report_date=payload.report_date,
        user_id=user_id,
        user_name=user_name,
    )


@router.get("/daily/summary")
async def get_daily_report_summary(
    report_date: dt.date = Query(default_factory=dt.date.today, description="报告日期"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    return {
        "success": True,
        "data": build_daily_report_context(db, report_date=report_date),
    }


@router.post("/weekly/generate")
async def generate_weekly_report(
    payload: PeriodReportGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    user_id = payload.user_id or str(getattr(user, "id", "user_001"))
    user_name = payload.user_name or getattr(user, "real_name", None) or getattr(user, "username", "管理员")
    return generate_period_patrol_report(
        db,
        report_date=payload.report_date,
        period_type="weekly",
        user_id=user_id,
        user_name=user_name,
    )


@router.get("/weekly/summary")
async def get_weekly_report_summary(
    report_date: dt.date = Query(default_factory=dt.date.today, description="周期内任意日期"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    return {
        "success": True,
        "data": build_period_report_context(db, report_date=report_date, period_type="weekly"),
    }


@router.post("/monthly/generate")
async def generate_monthly_report(
    payload: PeriodReportGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    user_id = payload.user_id or str(getattr(user, "id", "user_001"))
    user_name = payload.user_name or getattr(user, "real_name", None) or getattr(user, "username", "管理员")
    return generate_period_patrol_report(
        db,
        report_date=payload.report_date,
        period_type="monthly",
        user_id=user_id,
        user_name=user_name,
    )


@router.get("/monthly/summary")
async def get_monthly_report_summary(
    report_date: dt.date = Query(default_factory=dt.date.today, description="周期内任意日期"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    return {
        "success": True,
        "data": build_period_report_context(db, report_date=report_date, period_type="monthly"),
    }
