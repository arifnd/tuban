import asyncio
from datetime import date, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import Response

from src.auth.dependencies import DbDep
from src.exceptions import BadRequestError
from src.reports import exporters
from src.reports import service as reports_service
from src.reports.service import REPORT_KEYS
from src.templating import templates
from src.users.dependencies import AgentUser

router = APIRouter(prefix="/reports", tags=["reports"])

MAX_RANGE_DAYS = 366


def _default_range() -> tuple[date, date]:
    end = date.today()
    return end - timedelta(days=29), end


def _parse_range(start: str | None, end: str | None) -> tuple[date, date]:
    default_start, default_end = _default_range()
    try:
        start_date = date.fromisoformat(start) if start else default_start
        end_date = date.fromisoformat(end) if end else default_end
    except ValueError:
        raise BadRequestError(detail="Invalid date") from None
    if end_date < start_date:
        raise BadRequestError(detail="End date must be after start date")
    if (end_date - start_date).days > MAX_RANGE_DAYS:
        raise BadRequestError(detail=f"Date range must be at most {MAX_RANGE_DAYS} days")
    return start_date, end_date


async def _all_reports(db, start: date, end: date) -> dict:
    reports: dict[str, dict] = {}
    for key in REPORT_KEYS:
        title, columns, rows = await reports_service.build_report(db, key, start, end)
        reports[key] = {"key": key, "title": title, "columns": columns, "rows": rows}
    return reports


@router.get("")
async def reports_page(request: Request, db: DbDep, _: AgentUser, start: str = "", end: str = ""):
    start_date, end_date = _parse_range(start, end)
    return templates.TemplateResponse(
        request,
        "reports/index.html",
        {"reports": await _all_reports(db, start_date, end_date), "start": start_date.isoformat(), "end": end_date.isoformat()},
    )


@router.get("/partials/{report}")
async def report_partial(request: Request, db: DbDep, _: AgentUser, report: str, start: str = "", end: str = ""):
    if report not in REPORT_KEYS:
        raise BadRequestError(detail="Unknown report")
    start_date, end_date = _parse_range(start, end)
    title, columns, rows = await reports_service.build_report(db, report, start_date, end_date)
    return templates.TemplateResponse(request, "reports/partials/report_table.html", {"title": title, "columns": columns, "rows": rows})


@router.get("/export")
async def export_report(db: DbDep, _: AgentUser, report: str, format: str = "csv", start: str = "", end: str = ""):
    if report not in REPORT_KEYS:
        raise BadRequestError(detail="Unknown report")
    start_date, end_date = _parse_range(start, end)
    title, columns, rows = await reports_service.build_report(db, report, start_date, end_date)
    subtitle = f"{start_date.isoformat()} to {end_date.isoformat()}"

    if format == "csv":
        data = await asyncio.to_thread(exporters.build_csv, columns, rows)
        media_type, extension = "text/csv", "csv"
    elif format == "xlsx":
        data = await asyncio.to_thread(exporters.build_xlsx, title, columns, rows)
        media_type, extension = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    elif format == "pdf":
        data = await asyncio.to_thread(exporters.build_pdf, title, subtitle, columns, rows)
        media_type, extension = "application/pdf", "pdf"
    else:
        raise BadRequestError(detail="Unsupported format")

    filename = f"batik-{report}-{date.today():%Y%m%d}.{extension}"
    return Response(content=data, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
