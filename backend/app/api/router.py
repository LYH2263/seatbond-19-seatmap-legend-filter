from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import ConflictLog, Hall, SeatHold, Showtime
from app.schemas.schemas import (
    ConflictOut,
    HallOut,
    HoldOut,
    HoldRequest,
    SeatMapCell,
    SeatMapOut,
    ShowtimeOut,
)
from app.services.bond_engine import (
    HoldSpan,
    SeatCell,
    conflicts_with,
    find_bond_across_rows,
    find_contiguous_block,
)
from app.services.seat_status import SeatStatus, derive_status

api_router = APIRouter()


def _aisles(hall: Hall) -> list[int]:
    if not hall.aisle_cols.strip():
        return []
    return [int(x) for x in hall.aisle_cols.split(",") if x.strip()]


def _hall_out(h: Hall) -> HallOut:
    return HallOut(id=h.id, name=h.name, rows=h.rows, cols=h.cols, aisle_cols=_aisles(h))


@api_router.get("/health")
def health():
    return {"status": "ok"}


@api_router.get("/halls", response_model=list[HallOut])
def list_halls(db: Session = Depends(get_db)):
    return [_hall_out(h) for h in db.scalars(select(Hall).order_by(Hall.id)).all()]


@api_router.get("/showtimes", response_model=list[ShowtimeOut])
def list_showtimes(db: Session = Depends(get_db)):
    rows = db.scalars(select(Showtime).order_by(Showtime.start_at)).all()
    out = []
    for s in rows:
        hall = db.get(Hall, s.hall_id)
        out.append(
            ShowtimeOut(
                id=s.id,
                hall_id=s.hall_id,
                film_title=s.film_title,
                start_at=s.start_at,
                hall_name=hall.name if hall else None,
            )
        )
    return out


@api_router.get(
    "/seatmap/{showtime_id}",
    response_model=SeatMapOut,
    summary="场次座位图（含稳定 status 与状态筛选）",
    description=(
        "每个单元格返回稳定 `status`（free 空闲 / occupied 占用 / aisle 过道，"
        "与图例字段 `statuses` 同一枚举，后续新增遮挡、轮椅、情侣等标记会并入该枚举）。\n\n"
        "筛选：重复查询参数 `?status=free&status=occupied` 指定状态集合，"
        "命中格 `matched=true`，未命中格 `matched=false`；**始终返回完整厅图几何**，"
        "由前端负责弱化未命中格。\n\n"
        "语义约定：不传 `status` 参数 = 全选 = 全不选，三者都视为展示全部"
        "（`selected_statuses` 回显实际生效集合），不会出现空白厅。"
        "占用按场次实时计算，切换场次重新请求即可，不要复用上一场次的占用结果。"
    ),
)
def seatmap(
    showtime_id: int,
    status: list[SeatStatus] | None = Query(
        default=None,
        description="按状态集合筛选（可重复传参）。省略=全选=全不选，均展示全部。",
    ),
    db: Session = Depends(get_db),
):
    st = db.get(Showtime, showtime_id)
    if not st:
        raise HTTPException(404, "场次不存在")
    hall = db.get(Hall, st.hall_id)
    assert hall
    aisles = set(_aisles(hall))
    holds = db.scalars(select(SeatHold).where(SeatHold.showtime_id == showtime_id)).all()
    occupied: set[tuple[int, int]] = set()
    for h in holds:
        for c in range(h.start_col, h.end_col + 1):
            occupied.add((h.row, c))
    all_statuses = list(SeatStatus)
    # 不传参数、全选、全不选三者同义：展示全部状态。
    selected = set(status) if status else set(all_statuses)
    cells: list[SeatMapCell] = []
    for r in range(1, hall.rows + 1):
        for c in range(1, hall.cols + 1):
            is_aisle = c in aisles
            occ = (r, c) in occupied
            cell_status = derive_status(is_aisle=is_aisle, occupied=occ)
            cells.append(
                SeatMapCell(
                    row=r,
                    col=c,
                    is_aisle=is_aisle,
                    occupied=occ,
                    heat=1.0 if occ else (0.15 if is_aisle else 0.0),
                    status=cell_status,
                    matched=cell_status in selected,
                )
            )
    return SeatMapOut(
        showtime_id=showtime_id,
        hall_name=hall.name,
        rows=hall.rows,
        cols=hall.cols,
        statuses=all_statuses,
        selected_statuses=[s for s in all_statuses if s in selected],
        cells=cells,
    )


@api_router.get("/holds", response_model=list[HoldOut])
def list_holds(db: Session = Depends(get_db)):
    return db.scalars(select(SeatHold).order_by(SeatHold.id.desc())).all()


@api_router.get("/conflicts", response_model=list[ConflictOut])
def list_conflicts(db: Session = Depends(get_db)):
    return db.scalars(select(ConflictLog).order_by(ConflictLog.id.desc())).all()


@api_router.post("/holds", response_model=HoldOut)
def create_hold(body: HoldRequest, db: Session = Depends(get_db)):
    st = db.get(Showtime, body.showtime_id)
    if not st:
        raise HTTPException(404, "场次不存在")
    hall = db.get(Hall, st.hall_id)
    assert hall
    aisles = set(_aisles(hall))
    existing = db.scalars(select(SeatHold).where(SeatHold.showtime_id == body.showtime_id)).all()
    holds = [HoldSpan(row=h.row, start_col=h.start_col, end_col=h.end_col) for h in existing]
    seats_by_row: dict[int, list[SeatCell]] = {}
    for r in range(1, hall.rows + 1):
        seats_by_row[r] = [
            SeatCell(row=r, col=c, is_aisle=c in aisles) for c in range(1, hall.cols + 1)
        ]

    block = None
    if body.preferred_row:
        block = find_contiguous_block(
            seats_by_row.get(body.preferred_row, []), holds, body.preferred_row, body.party_size
        )
    if block is None:
        block = find_bond_across_rows(seats_by_row, holds, body.party_size)
    if block is None:
        db.add(
            ConflictLog(
                showtime_id=body.showtime_id,
                party_size=body.party_size,
                reason=f"无足够连续空座（人数 {body.party_size}）",
            )
        )
        db.commit()
        raise HTTPException(409, "无足够连续空座")

    hits = conflicts_with(holds, block)
    if hits:
        db.add(
            ConflictLog(
                showtime_id=body.showtime_id,
                party_size=body.party_size,
                reason=f"与既有持座重叠：第{hits[0].row}排 {hits[0].start_col}-{hits[0].end_col}",
            )
        )
        db.commit()
        raise HTTPException(409, "与既有持座冲突")

    code = f"SB-{int(datetime.utcnow().timestamp()) % 100000:05d}"
    hold = SeatHold(
        showtime_id=body.showtime_id,
        order_code=code,
        row=block.row,
        start_col=block.start_col,
        end_col=block.end_col,
        party_size=body.party_size,
    )
    db.add(hold)
    db.commit()
    db.refresh(hold)
    return hold
