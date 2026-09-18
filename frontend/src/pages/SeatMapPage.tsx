import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";

type Show = { id: number; film_title: string; hall_name?: string };
// 状态枚举由接口 available_statuses 下发，前端不自行猜
type Cell = {
  row: number;
  col: number;
  status: string;
  is_aisle: boolean;
  occupied: boolean;
  heat: number;
};
type StatusInfo = { status: string; label: string };
type MapOut = {
  showtime_id: number;
  hall_name: string;
  rows: number;
  cols: number;
  cells: Cell[];
  available_statuses: StatusInfo[];
};

export default function SeatMapPage() {
  const [shows, setShows] = useState<Show[]>([]);
  const [sid, setSid] = useState<number | "">("");
  const [map, setMap] = useState<MapOut | null>(null);
  // 选中的状态集合；空集 = 不过滤 = 展示全部。切换场次时保留，高亮按新场次数据重算
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    api<Show[]>("/showtimes").then((s) => {
      setShows(s);
      if (s[0]) setSid(s[0].id);
    });
  }, []);

  useEffect(() => {
    if (sid === "") return;
    // 切场次先清掉旧图，避免把上场次的占用格错带到新场次
    setMap(null);
    let alive = true;
    api<MapOut>(`/seatmap/${sid}`).then((m) => {
      if (alive) setMap(m);
    });
    return () => {
      alive = false;
    };
  }, [sid]);

  const gridStyle = useMemo(
    () => ({ gridTemplateColumns: map ? `repeat(${map.cols}, 28px)` : undefined }),
    [map]
  );

  const counts = useMemo(() => {
    const acc: Record<string, number> = {};
    if (!map) return acc;
    for (const c of map.cells) acc[c.status] = (acc[c.status] ?? 0) + 1;
    return acc;
  }, [map]);

  const allStatuses = useMemo(() => map?.available_statuses ?? [], [map]);
  const allSelected = allStatuses.length > 0 && selected.size === allStatuses.length;
  // 仅当选择了部分状态时才弱化其它格；全不选与全选都不弱化
  const filtering = selected.size > 0 && !allSelected;

  function toggle(status: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return next;
    });
  }

  return (
    <>
      <div className="toolbar">
        <label>
          场次{" "}
          <select value={sid} onChange={(e) => setSid(Number(e.target.value))}>
            {shows.map((s) => (
              <option key={s.id} value={s.id}>
                {s.film_title} · {s.hall_name}
              </option>
            ))}
          </select>
        </label>
        {map && (
          <span className="mono">
            {map.hall_name} · {map.rows}×{map.cols} · 热力座图
          </span>
        )}
      </div>
      {map && (
        <div className="legend">
          <span className="legend-title">状态图例</span>
          {allStatuses.map((s) => {
            const on = selected.has(s.status);
            return (
              <button
                key={s.status}
                type="button"
                className={`legend-chip${on ? " on" : ""}`}
                aria-pressed={on}
                onClick={() => toggle(s.status)}
              >
                <span className={`swatch sw-${s.status}`} />
                {s.label}
                <span className="mono chip-count">{counts[s.status] ?? 0}</span>
              </button>
            );
          })}
          <button
            type="button"
            className="legend-act"
            onClick={() => setSelected(new Set(allStatuses.map((s) => s.status)))}
          >
            全选
          </button>
          <button type="button" className="legend-act" onClick={() => setSelected(new Set())}>
            清空
          </button>
          <span className="legend-hint">
            {selected.size === 0
              ? "未选择状态 · 展示全部（全不选 = 不过滤）"
              : allSelected
                ? "已全选 · 全部高亮"
                : `已选 ${selected.size} 项 · 仅高亮匹配状态，其余弱化`}
          </span>
        </div>
      )}
      <div className="screen">银 幕</div>
      {map ? (
        <div className="seat-grid" style={gridStyle}>
          {map.cells.map((c) => {
            const dim = filtering && !selected.has(c.status);
            const hl = filtering && selected.has(c.status);
            return (
              <div
                key={`${c.row}-${c.col}`}
                className={`seat ${c.is_aisle ? "aisle" : c.occupied ? "occ" : "free"}${dim ? " dim" : ""}${hl ? " hl" : ""}`}
                title={`R${c.row}C${c.col} · ${c.status}`}
                style={
                  !c.is_aisle && c.heat
                    ? { boxShadow: `inset 0 0 0 1px rgba(255,180,80,${Math.min(0.9, c.heat / 10)})` }
                    : undefined
                }
              >
                {c.is_aisle ? "" : c.col}
              </div>
            );
          })}
        </div>
      ) : (
        sid !== "" && <p className="legend-hint">加载中…</p>
      )}
      <p className="legend-hint">
        筛选条件在切换场次后保持，高亮结果按新场次占用重算；全不选与全选均展示全部座位。
      </p>
    </>
  );
}
