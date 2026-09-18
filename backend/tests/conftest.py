import os

# 兜底：即便 lifespan 被触发也不连 Postgres。
os.environ.setdefault("DATABASE_URL", "sqlite://")

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Hall, SeatHold, Showtime


@pytest.fixture()
def client():
    """TestClient backed by a throwaway in-memory SQLite hall.

    一个 4×8 厅（过道列 4、5），两个场次持座不同：
    - 场次一：R2C2-3、R3C6-7
    - 场次二：R1C8
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    db = TestingSession()
    hall = Hall(name="测试厅", rows=4, cols=8, aisle_cols="4,5")
    db.add(hall)
    db.flush()
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    s1 = Showtime(hall_id=hall.id, film_title="甲片", start_at=now + timedelta(hours=1))
    s2 = Showtime(hall_id=hall.id, film_title="乙片", start_at=now + timedelta(hours=3))
    db.add_all([s1, s2])
    db.flush()
    showtime_ids = (s1.id, s2.id)
    db.add_all(
        [
            SeatHold(showtime_id=s1.id, order_code="T-1001", row=2, start_col=2, end_col=3, party_size=2),
            SeatHold(showtime_id=s1.id, order_code="T-1002", row=3, start_col=6, end_col=7, party_size=2),
            SeatHold(showtime_id=s2.id, order_code="T-1003", row=1, start_col=8, end_col=8, party_size=1),
        ]
    )
    db.commit()
    db.close()

    def override_get_db():
        session = TestingSession()
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
