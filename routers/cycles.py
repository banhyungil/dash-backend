"""사이클 데이터 조회 API."""
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from repos.cycles_repo import get_months as repo_get_months, get_dates as repo_get_dates
from services.daily_data_service import build_daily_data, build_cycle_detail
from services.excel_export import generate_daily_report

router = APIRouter(prefix="/api")


@router.get("/months")
def get_months():
    """적재된 월 목록 조회."""
    rows = repo_get_months()
    return [
        {"month": r["month"], "label": f"20{r['month'][:2]}년 {r['month'][2:]}월"}
        for r in rows
    ]


@router.get("/dates")
def get_dates(month: str = Query(...)):
    """특정 월의 날짜 목록 조회."""
    rows = repo_get_dates(month)
    return [
        {
            "date": r["date"],
            "label": f"{r['date'][:2]}/{r['date'][2:4]}/{r['date'][4:]} ({r['cycle_count']} cycles)",
            "cycle_count": r["cycle_count"],
            "high_vib_events": r["high_vib_events"],
        }
        for r in rows
    ]


@router.get("/cycles/daily")
def get_daily_data(month: str = Query(...), date: str = Query(...)):
    """일별 사이클 데이터 조회."""
    return build_daily_data(month, date)


@router.get("/cycles/export-excel")
def export_excel(month: str = Query(...), date: str = Query(...)):
    """일일 리포트 Excel 다운로드."""
    data = build_daily_data(month, date)
    buf = generate_daily_report(data["cycles"], date)
    filename = f"Report_{date}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/cycles/detail")
def get_cycle_detail(
    date: str = Query(...),
    session: str = Query(...),
    cycle_index: int = Query(...),
):
    """개별 사이클의 원시 파형 데이터 반환."""
    result = build_cycle_detail(date, session, cycle_index)
    if not result:
        return {"error": "cycle not found"}
    return result
