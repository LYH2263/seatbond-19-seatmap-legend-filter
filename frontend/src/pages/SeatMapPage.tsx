import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";

type Show = { id: number; film_title: string; hall_name?: string };
type Cell = {
  row: number;
  col: number;
  is_aisle: boolean;
  occupied: boolean;
  heat: number;
  status: string;
  matched: boolean;
};
type MapOut = {
  showtime_id: number;
  hall_name: string;
  rows: number;
  cols: number;
  statuses: string[];
  selected_statuses: string[];
  cells: Cell[];
};

// 展示名：已知状态给中文名，未来新增状态（遮挡/轮椅/情侣…）回退为原始枚举值，
// 图例与筛选仍由接口 statuses 枚举驱动，前端不自行猜测。
const STATUS_LABELS: Record<string, string> = {
  free: "空闲",
  occupied: "占用",
  aisle: "过道",
};

function swatchClass(status: string): string {
  if (status === "free") return "sw-free";
  if (status === "occupied") return "sw-occ";
  if (status === "aisle") return "sw-aisle";
  return "sw-unknown";
}

export default function SeatMapPage() {
  const [shows, setShows] = useState<Show[]>([]);
  const [sid, setSid] = useState<number | "">("");
  const [map, setMap] = useState<MapOut | null>(null);
  const [err, setErr] = useState("");
  // 勾选状态以「排除集」记录：新出现的状态默认勾选；切换场次时排除集保持不变。
  const [excluded, setExcluded] = useState<ReadonlySet<string>>(new Set());
  // 最近一次响应带回的状态枚举，用于拼筛选参数（首次加载前为空 → 不带参数）。
  const statusesRef = useRef<string[]>([]);
  // 请求序号：切场次/改筛选后，旧响应一律丢弃，杜绝上场次占用串入下一场次。
  const reqSeq = useRef(0);

  useEffect(() => {
    api<Show[]>("/showtimes").then((s) => {
      setShows(s);
      if (s[0]) setSid(s[0].id);
    });
  }, []);

  useEffect(() => {
    if (sid === "") return;
    setMap(null); // 先清旧图：新场次数据回来前不渲染任何占用格
    setErr("");
    const seq = ++reqSeq.current;
    const known = statusesRef.current;
    const selected = known.filter((s) => !excluded.has(s));
    // 全选（excluded 为空）与全不选（selected 为空）同义：不带参数，后端返回全集。
    const qs =
      excluded.size > 0 && selected.length > 0
        ? "?" + selected.map((s) => `status=${encodeURIComponent(s)}`).join("&")
        : "";
    api<MapOut>(`/seatmap/${sid}${qs}`)
      .then((m) => {
        if (reqSeq.current !== seq) return; // 过期响应
        statusesRef.current = m.statuses;
        setMap(m);
      })
      .catch((e) => {
        if (reqSeq.current !== seq) return;
        setErr(e instanceof Error ? e.message : String(e));
      });
  }, [sid, excluded]);

  const gridStyle = useMemo(
    () => ({ gridTemplateColumns: map ? `repeat(${map.cols}, 28px)` : undefined }),
    [map]
  );

  // 仅当响应与当前选中场次一致时才渲染，避免旧场次占用格串场。
  const current = map && map.showtime_id === sid ? map : null;
  const matchedCount = useMemo(
    () => (current ? current.cells.filter((c) => c.matched).length : 0),
    [current]
  );
  const allExcluded =
    current !== null &&
    current.statuses.length > 0 &&
    current.statuses.every((s) => excluded.has(s));

  function toggle(status: string) {
    setExcluded((prev) => {
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
        {current && (
          <span className="mono">
            {current.hall_name} · {current.rows}×{current.cols} · 高亮 {matchedCount}/
            {current.cells.length}
          </span>
        )}
      </div>
      {current && (
        <div className="legend" aria-label="状态图例与筛选">
          {current.statuses.map((s) => (
            <label key={s} className="legend-item">
              <input
                type="checkbox"
                checked={!excluded.has(s)}
                onChange={() => toggle(s)}
              />
              <span className={`legend-swatch ${swatchClass(s)}`} />
              {STATUS_LABELS[s] ?? s}
            </label>
          ))}
          <button
            type="button"
            className="legend-btn"
            onClick={() => setExcluded(new Set())}
          >
            全选
          </button>
          <button
            type="button"
            className="legend-btn"
            onClick={() => setExcluded(new Set(current.statuses))}
          >
            全不选
          </button>
          <span className="legend-hint">
            勾选的状态高亮、未勾选弱化，厅图几何不变；「全不选」与「全选」均视为展示全部。
          </span>
          {allExcluded && (
            <span className="legend-hint legend-hint--strong">
              当前未勾选任何状态 — 按约定「全不选 = 展示全部」，厅图不会空白。
            </span>
          )}
        </div>
      )}
      {err && <div className="err">{err}</div>}
      <div className="screen">银 幕</div>
      {current ? (
        <div className="seat-grid" style={gridStyle}>
          {current.cells.map((c) => (
            <div
              key={`${c.row}-${c.col}`}
              className={`seat ${c.is_aisle ? "aisle" : c.occupied ? "occ" : "free"}${
                c.matched ? "" : " dim"
              }`}
              title={`R${c.row}C${c.col} · ${STATUS_LABELS[c.status] ?? c.status}`}
              style={
                !c.is_aisle && c.heat
                  ? { boxShadow: `inset 0 0 0 1px rgba(255,180,80,${Math.min(0.9, c.heat / 10)})` }
                  : undefined
              }
            >
              {c.is_aisle ? "" : c.col}
            </div>
          ))}
        </div>
      ) : (
        !err && <p className="mono">加载中…</p>
      )}
    </>
  );
}
