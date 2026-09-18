"""Seat cell status vocabulary shared by the seatmap API and the frontend filter.

Live states today: free / occupied / aisle. The hall model has no blocked /
wheelchair / couple markers yet — to add one later:
  1. add a SeatStatus member,
  2. add its Chinese label in STATUS_LABELS,
  3. add one rule in cell_status().
The seatmap legend (available_statuses) and the frontend filter chips are
derived from this enum, so both pick up the new state without further changes.
"""

from __future__ import annotations

from enum import Enum


class SeatStatus(str, Enum):
    FREE = "free"
    OCCUPIED = "occupied"
    AISLE = "aisle"


STATUS_LABELS: dict[SeatStatus, str] = {
    SeatStatus.FREE: "空闲",
    SeatStatus.OCCUPIED: "占用",
    SeatStatus.AISLE: "过道",
}


def cell_status(*, is_aisle: bool, occupied: bool) -> SeatStatus:
    """Single computation point for a cell's stable status.

    Precedence: aisle (hall geometry) beats occupied (per-showtime holds).
    Future markers (blocked / wheelchair / couple) slot in here.
    """
    if is_aisle:
        return SeatStatus.AISLE
    if occupied:
        return SeatStatus.OCCUPIED
    return SeatStatus.FREE
