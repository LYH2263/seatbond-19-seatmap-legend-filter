from datetime import datetime
from pydantic import BaseModel, Field

from app.services.seat_status import SeatStatus


class HallOut(BaseModel):
    id: int
    name: str
    rows: int
    cols: int
    aisle_cols: list[int]
    model_config = {"from_attributes": True}


class ShowtimeOut(BaseModel):
    id: int
    hall_id: int
    film_title: str
    start_at: datetime
    hall_name: str | None = None
    model_config = {"from_attributes": True}


class HoldOut(BaseModel):
    id: int
    showtime_id: int
    order_code: str
    row: int
    start_col: int
    end_col: int
    party_size: int
    status: str
    model_config = {"from_attributes": True}


class HoldRequest(BaseModel):
    showtime_id: int
    party_size: int = Field(ge=1, le=12)
    preferred_row: int | None = None


class ConflictOut(BaseModel):
    id: int
    showtime_id: int
    party_size: int
    reason: str
    created_at: datetime
    model_config = {"from_attributes": True}


class SeatMapCell(BaseModel):
    row: int
    col: int
    is_aisle: bool
    occupied: bool
    heat: float
    status: SeatStatus
    matched: bool  # True when the cell's status passes the requested ?status= filter


class SeatMapOut(BaseModel):
    showtime_id: int
    hall_name: str
    rows: int
    cols: int
    # Full status enum — the frontend legend renders from this, same values
    # the ?status= query param accepts. New states appear here automatically.
    statuses: list[SeatStatus]
    # Filter actually applied; equals `statuses` when the param is omitted
    # ("select none" and "select all" both resolve to the full set).
    selected_statuses: list[SeatStatus]
    cells: list[SeatMapCell]
