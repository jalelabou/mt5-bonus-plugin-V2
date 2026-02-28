import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import AdminUser
from app.services.report_service import (
    get_bonus_summary,
    get_cancellation_report,
    get_conversion_progress,
    get_leverage_report,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/summary")
async def summary_report(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    campaign_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    return await get_bonus_summary(db, date_from, date_to, campaign_id, broker_id=user.broker_id)


@router.get("/conversions")
async def conversion_report(
    campaign_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    return await get_conversion_progress(db, campaign_id, broker_id=user.broker_id)


@router.get("/cancellations")
async def cancellation_report(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    return await get_cancellation_report(db, date_from, date_to, broker_id=user.broker_id)


@router.get("/leverage")
async def leverage_report(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    return await get_leverage_report(db, broker_id=user.broker_id)


@router.get("/export")
async def export_report(
    report_type: str = Query(..., description="summary, conversions, cancellations, leverage"),
    format: str = Query("csv", description="csv or xlsx"),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    campaign_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    broker_id = user.broker_id
    if report_type == "summary":
        data = await get_bonus_summary(db, date_from, date_to, campaign_id, broker_id=broker_id)
    elif report_type == "conversions":
        data = await get_conversion_progress(db, campaign_id, broker_id=broker_id)
    elif report_type == "cancellations":
        data = await get_cancellation_report(db, date_from, date_to, broker_id=broker_id)
    elif report_type == "leverage":
        data = await get_leverage_report(db, broker_id=broker_id)
    else:
        return {"error": "Invalid report type"}

    if not data:
        return {"error": "No data"}

    if format == "csv":
        output = io.StringIO()
        headers = list(data[0].keys())
        output.write(",".join(headers) + "\n")
        for row in data:
            output.write(",".join(str(row.get(h, "")) for h in headers) + "\n")
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={report_type}_report.csv"},
        )

    if format == "xlsx":
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = report_type
        headers = list(data[0].keys())
        ws.append(headers)
        for row in data:
            ws.append([row.get(h, "") for h in headers])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={report_type}_report.xlsx"},
        )

    return {"error": "Invalid format"}
