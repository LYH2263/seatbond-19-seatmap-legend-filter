"""Seatmap 契约测例：抽样格 status 与持座/过道一致；status 集合过滤正确；切场次占用跟着变。"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Hall, SeatHold, Showtime

# 厅：4 排 × 6 列，第 3 列为过道
# 场次 s1 持座：R2C1-2、R4C5-6；场次 s2 持座：R1C4
S1_OCCUPIED = {(2, 1), (2, 2), (4, 5), (4, 6)}
S2_OCCUPIED = {(1, 4)}


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    hall = Hall(name="契约厅", rows=4, cols=6, aisle_cols="3")
    db.add(hall)
    db.flush()
    now = datetime.utcnow()
    s1 = Showtime(hall_id=hall.id, film_title="甲片", start_at=now + timedelta(hours=1))
    s2 = Showtime(hall_id=hall.id, film_title="乙片", start_at=now + timedelta(hours=3))
    db.add_all([s1, s2])
    db.flush()
    db.add_all(
        [
            SeatHold(showtime_id=s1.id, order_code="T-1", row=2, start_col=1, end_col=2, party_size=2),
            SeatHold(showtime_id=s1.id, order_code="T-2", row=4, start_col=5, end_col=6, party_size=2),
            SeatHold(showtime_id=s2.id, order_code="T-3", row=1, start_col=4, end_col=4, party_size=1),
        ]
    )
    db.commit()
    showtime_ids = (s1.id, s2.id)
    db.close()

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), showtime_ids
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _cells_by_pos(payload) -> dict[tuple[int, int], dict]:
    return {(c["row"], c["col"]): c for c in payload["cells"]}


def test_cell_status_matches_holds_and_aisles(client):
    http, (s1, _) = client
    res = http.get(f"/api/seatmap/{s1}")
    assert res.status_code == 200
    body = res.json()
    assert body["rows"] == 4 and body["cols"] == 6
    assert len(body["cells"]) == 24

    # 图例与前端筛选共用同一套枚举
    legend = {s["status"]: s["label"] for s in body["available_statuses"]}
    assert set(legend) == {"free", "occupied", "aisle"}
    assert all(label for label in legend.values())

    cells = _cells_by_pos(body)
    # 抽样：过道列
    for r in (1, 2, 3, 4):
        assert cells[(r, 3)]["status"] == "aisle"
    # 抽样：持座格
    for pos in S1_OCCUPIED:
        assert cells[pos]["status"] == "occupied"
    # 抽样：空闲格
    for pos in [(1, 1), (3, 4), (4, 4)]:
        assert cells[pos]["status"] == "free"
    # 旧字段与 status 保持一致，前端不必二选一猜
    for c in body["cells"]:
        assert c["is_aisle"] == (c["status"] == "aisle")
        assert c["occupied"] == (c["status"] == "occupied")


def test_status_filter_returns_matching_subset(client):
    http, (s1, _) = client
    full = http.get(f"/api/seatmap/{s1}").json()
    total = len(full["cells"])

    res = http.get(f"/api/seatmap/{s1}", params=[("status", "occupied")])
    assert res.status_code == 200
    occ = res.json()["cells"]
    assert {c["status"] for c in occ} == {"occupied"}
    assert {(c["row"], c["col"]) for c in occ} == S1_OCCUPIED

    # 多值取并集
    res = http.get(f"/api/seatmap/{s1}", params=[("status", "free"), ("status", "aisle")])
    assert res.status_code == 200
    subset = res.json()["cells"]
    assert len(subset) == total - len(S1_OCCUPIED)
    assert {c["status"] for c in subset} == {"free", "aisle"}

    # 省略参数 = 不过滤 = 返回全部格子（「全不选」语义，不会出现空白厅）
    assert total == 24


def test_unknown_status_rejected(client):
    http, (s1, _) = client
    res = http.get(f"/api/seatmap/{s1}", params=[("status", "vip")])
    assert res.status_code == 422


def test_occupancy_follows_showtime_switch(client):
    http, (s1, s2) = client
    m1 = _cells_by_pos(http.get(f"/api/seatmap/{s1}").json())
    m2 = _cells_by_pos(http.get(f"/api/seatmap/{s2}").json())

    occ1 = {pos for pos, c in m1.items() if c["status"] == "occupied"}
    occ2 = {pos for pos, c in m2.items() if c["status"] == "occupied"}
    assert occ1 == S1_OCCUPIED
    assert occ2 == S2_OCCUPIED

    # 上场次的占用格不得错带到下场次
    assert m2[(2, 1)]["status"] == "free"
    assert m1[(1, 4)]["status"] == "free"

    # 厅图几何（过道）跨场次稳定
    for r in (1, 2, 3, 4):
        assert m1[(r, 3)]["status"] == m2[(r, 3)]["status"] == "aisle"

    # 筛选参数同样按新场次占用计算
    occ2_filtered = http.get(f"/api/seatmap/{s2}", params=[("status", "occupied")]).json()["cells"]
    assert {(c["row"], c["col"]) for c in occ2_filtered} == S2_OCCUPIED
