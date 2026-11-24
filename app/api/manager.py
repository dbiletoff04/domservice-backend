from datetime import date, datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from app.core.security import CurrentUser, require_roles
from app.schemas.common import RequestStatusCode, standard_error_responses
from app.schemas.reports import GisReportPreviewOut, GisReportRowOut

router = APIRouter(prefix="/manager", tags=["Руководитель УК (F-10)"])


@router.get(
    "/reports/gis",
    response_model=GisReportPreviewOut,
    responses=standard_error_responses(400, 401, 403),
    summary="Сформировать отчёт для ГИС ЖКХ за период",
    description=(
        "**Доступ:** только `manager` (уточнение #10).\n\n"
        "Поддерживает предпросмотр в JSON (`format=json`) и скачивание CSV (`format=csv`). "
        "При наличии незакрытых заявок выставляет `requires_review=true`."
    ),
)
async def export_gis_report(
    period_type: Literal["month", "quarter", "year"] = Query(default="quarter"),
    start_date: date = Query(default=date(2026, 10, 1)),
    end_date: date = Query(default=date(2026, 12, 31)),
    output_format: Literal["json", "csv"] = Query(default="json", alias="format"),
    user: CurrentUser = Depends(require_roles("manager")),
):
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата начала периода не может быть больше даты окончания",
        )

    if output_format == "csv":
        csv_content = (
            "request_number;address;apartment;category;status;created_at;closed_at;note\n"
            "REQ-120;г. Волжский, ул. Ленина, д. 97;42;Отопление;closed;2026-11-04T10:00:00Z;2026-11-05T15:30:00Z;\n"
            "REQ-123;г. Волжский, ул. Ленина, д. 97;42;Сантехника;master_assigned;2026-11-10T15:00:00Z;;Требует проверки\n"
        )
        return Response(
            content=csv_content.encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="gis_report.csv"'},
        )

    return GisReportPreviewOut(
        period_label=period_type,
        start_date=start_date,
        end_date=end_date,
        total_requests=2,
        unclosed_requests=1,
        requires_review=True,
        warning="В периоде есть незакрытые заявки — отчёт помечен как «Требует проверки»",
        rows=[
            GisReportRowOut(
                request_number="REQ-120",
                address="г. Волжский, ул. Ленина, д. 97",
                apartment="42",
                category_name="Отопление",
                status=RequestStatusCode.CLOSED,
                created_at=datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc),
                closed_at=datetime(2026, 11, 5, 15, 30, tzinfo=timezone.utc),
            ),
            GisReportRowOut(
                request_number="REQ-123",
                address="г. Волжский, ул. Ленина, д. 97",
                apartment="42",
                category_name="Сантехника",
                status=RequestStatusCode.MASTER_ASSIGNED,
                created_at=datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc),
                closed_at=None,
            ),
        ],
    )