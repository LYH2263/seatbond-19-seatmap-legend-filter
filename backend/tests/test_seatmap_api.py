"""Seatmap 契约测例：稳定 status、状态筛选、切场次重算。"""

from app.services.seat_status import SeatStatus, derive_status

# 与 conftest 种子数据对应
S1_OCCUPIED = {(2, 2), (2, 3), (3, 6), (3, 7)}
S2_OCCUPIED = {(1, 8)}
AISLE_COLS = (4, 5)
ROWS, COLS = 4, 8


def _cells_by_pos(payload):
    return {(c["row"], c["col"]): c for c in payload["cells"]}


def _matched(payload):
    return {(c["row"], c["col"]) for c in payload["cells"] if c["matched"]}


def test_derive_status_priority():
    # 过道优先于占用；占用优先于空闲
    assert derive_status(is_aisle=True, occupied=True) is SeatStatus.AISLE
    assert derive_status(is_aisle=True, occupied=False) is SeatStatus.AISLE
    assert derive_status(is_aisle=False, occupied=True) is SeatStatus.OCCUPIED
    assert derive_status(is_aisle=False, occupied=False) is SeatStatus.FREE


def test_sampled_cells_match_holds_and_aisles(client):
    http, (s1, _s2) = client
    resp = http.get(f"/api/seatmap/{s1}")
    assert resp.status_code == 200
    payload = resp.json()

    # 图例枚举稳定，且与筛选参数共用同一套值
    assert payload["statuses"] == ["free", "occupied", "aisle"]
    # 不传筛选参数 = 全选，回显实际生效集合
    assert payload["selected_statuses"] == payload["statuses"]

    cells = _cells_by_pos(payload)
    assert len(cells) == ROWS * COLS

    # 抽样：过道列
    for r in range(1, ROWS + 1):
        for c in AISLE_COLS:
            assert cells[(r, c)]["status"] == "aisle"
            assert cells[(r, c)]["is_aisle"] is True
    # 抽样：持座格
    for pos in S1_OCCUPIED:
        assert cells[pos]["status"] == "occupied"
        assert cells[pos]["occupied"] is True
    # 抽样：空闲格
    for pos in [(1, 1), (1, 8), (4, 6)]:
        assert cells[pos]["status"] == "free"
        assert cells[pos]["occupied"] is False

    # 全图不变式：status 与 is_aisle/occupied 标志一致，且取值不出图例枚举
    legend = set(payload["statuses"])
    for cell in cells.values():
        assert cell["status"] in legend
        if cell["is_aisle"]:
            assert cell["status"] == "aisle"
        elif cell["occupied"]:
            assert cell["status"] == "occupied"
        else:
            assert cell["status"] == "free"
        # 无筛选时全部命中
        assert cell["matched"] is True


def test_status_filter_returns_correct_set(client):
    http, (s1, _s2) = client

    payload = http.get(f"/api/seatmap/{s1}", params=[("status", "occupied")]).json()
    assert len(payload["cells"]) == ROWS * COLS  # 几何完整，不丢格
    assert payload["selected_statuses"] == ["occupied"]
    assert _matched(payload) == S1_OCCUPIED
    for cell in payload["cells"]:
        assert cell["matched"] == (cell["status"] == "occupied")

    # 多值集合：free + aisle
    payload = http.get(
        f"/api/seatmap/{s1}", params=[("status", "free"), ("status", "aisle")]
    ).json()
    assert payload["selected_statuses"] == ["free", "aisle"]
    assert _matched(payload) == {
        (c["row"], c["col"]) for c in payload["cells"] if c["status"] in {"free", "aisle"}
    }
    assert S1_OCCUPIED.isdisjoint(_matched(payload))

    # 显式传全部状态 ≈ 不传参数
    payload_all = http.get(
        f"/api/seatmap/{s1}",
        params=[("status", s) for s in ("free", "occupied", "aisle")],
    ).json()
    assert _matched(payload_all) == set(_cells_by_pos(payload_all).keys())


def test_invalid_status_rejected(client):
    http, (s1, _s2) = client
    resp = http.get(f"/api/seatmap/{s1}", params=[("status", "vip")])
    assert resp.status_code == 422


def test_occupancy_follows_showtime_switch(client):
    http, (s1, s2) = client

    first = http.get(f"/api/seatmap/{s1}", params=[("status", "occupied")]).json()
    second = http.get(f"/api/seatmap/{s2}", params=[("status", "occupied")]).json()

    # 占用集合各自按本场次计算，互不携带
    assert _matched(first) == S1_OCCUPIED
    assert _matched(second) == S2_OCCUPIED
    assert S1_OCCUPIED.isdisjoint(S2_OCCUPIED)

    # 同一格在切换场次后 status 跟着变
    c1 = _cells_by_pos(first)
    c2 = _cells_by_pos(second)
    assert c1[(2, 2)]["status"] == "occupied"
    assert c2[(2, 2)]["status"] == "free"
    assert c1[(1, 8)]["status"] == "free"
    assert c2[(1, 8)]["status"] == "occupied"
    # 过道不受场次影响
    assert c2[(1, 4)]["status"] == "aisle"


def test_unknown_showtime_404(client):
    http, _ = client
    assert http.get("/api/seatmap/9999").status_code == 404
