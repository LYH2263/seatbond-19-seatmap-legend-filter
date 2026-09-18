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

`GET /api/seatmap/{showtime_id}` 为每个单元格返回稳定 `status`，与图例、筛选参数共用同一枚举
（`backend/app/services/seat_status.py`，后续新增遮挡/轮椅/情侣等标记时在此扩展）：

| status | 含义 |
| --- | --- |
| `free` | 空闲 |
| `occupied` | 占用（本场次已持座） |
| `aisle` | 过道列 |

- **筛选参数**：`GET /api/seatmap/{showtime_id}?status=free&status=occupied`（可重复传参，
  非法值返回 422）。响应始终包含完整厅图几何；命中格 `matched=true`，未命中格
  `matched=false`，由前端弱化显示。`statuses` 字段返回完整枚举供图例渲染，
  `selected_statuses` 回显实际生效的筛选集合。
- **全选 / 全不选语义**：不传 `status` 参数 = 全选 = 全不选，三者均视为展示全部，
  不会出现空白厅。座位图页图例旁也写有同样约定。
- **切换场次**：占用按场次实时计算；前端切场次会清空旧图并按新场次重新请求，
  筛选勾选保持不变，高亮结果以新场次响应为准。

## 开发与测试

```bash
docker compose exec api pytest -q
```
