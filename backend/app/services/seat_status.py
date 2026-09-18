"""Stable per-cell status taxonomy for the seat map.

This module is the single source of truth for seat-cell states. The seatmap
endpoint's ``?status=`` filter and the frontend legend both share this enum,
so neither side guesses the heat mapping on its own.

Base states (derived from hall geometry + per-showtime holds):
- ``FREE``     — regular seat, not held for this showtime
- ``OCCUPIED`` — covered by a hold for this showtime
- ``AISLE``    — aisle column of the hall (never a sellable seat)

Extension point: warehouse markers such as blocked / wheelchair / couple
seats plug in here — add an enum member and extend ``derive_status`` (and
its inputs). The filter query param, the response legend field, and the
frontend multi-select all pick new members up automatically because they
are driven by this enum rather than a hard-coded list.
"""

from __future__ import annotations

from enum import Enum


class SeatStatus(str, Enum):
    FREE = "free"
    OCCUPIED = "occupied"
    AISLE = "aisle"
    # Reserved for future warehouse markers (not produced yet):
    # BLOCKED = "blocked"
    # WHEELCHAIR = "wheelchair"
    # COUPLE = "couple"


def derive_status(*, is_aisle: bool, occupied: bool) -> SeatStatus:
    """Map raw cell facts to a stable status.

    Aisle wins over occupied: aisle columns are hall geometry and can never
    be held, so a stray hold span crossing an aisle column still reports
    ``AISLE`` for that cell.
    """
    if is_aisle:
        return SeatStatus.AISLE
    if occupied:
        return SeatStatus.OCCUPIED
    return SeatStatus.FREE
