# SeatBond

影院连座锁座：按场次厅图查找连续空座，过道列断开，冲突检测既有持座。

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4100 |
| API | http://localhost:9100 |
| API 文档 | http://localhost:9100/docs |
| Postgres | localhost:5442 |

健康检查：`GET http://localhost:9100/api/health`

## 页面

- `/halls` — 影厅
- `/showtimes` — 场次
- `/seatmap` — 座位图（大网格热力）
- `/hold` — 锁座
- `/orders` — 订单
- `/conflicts` — 冲突

## 使用说明

1. 在影厅与场次页确认厅图与排期。
2. 打开座位图查看占用热力，在锁座页输入连座人数并提交。
3. 订单页查看持座结果；冲突页查看重叠请求。

## 座位图状态与筛选

每个座位格带稳定 `status`：`free`（空闲）/ `occupied`（占用）/ `aisle`（过道）。
枚举由 `GET /api/seatmap/{showtime_id}` 响应的 `available_statuses` 下发（含中文标签），
前端图例与筛选 chips 直接据此渲染，不自行猜状态。新增状态（如遮挡、轮椅、情侣座）
只需在 `backend/app/services/seat_status.py` 的枚举、标签表与 `cell_status()` 各加一处。

- **接口过滤**：`GET /api/seatmap/{id}?status=free&status=aisle`，参数可重复，取并集；
  省略参数返回全部格子；非法状态值返回 422。占用状态始终按所查场次的持座实时计算。
- **页面筛选**：图例 chips 多选，选中部分状态时仅高亮匹配格，其余格弱化但厅图几何保持可读。
  - **全不选 = 不过滤 = 展示全部**（页面有提示，不会出现空白厅）；
  - **全选 = 全部高亮**，同样不弱化任何格。
- **切换场次**：筛选条件保持，但高亮按新场次占用重算，不会把上场次的占用格带过来。

## 开发与测试

```bash
docker compose exec api pytest -q
```
