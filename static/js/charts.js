// Графики на чистом SVG, без библиотек.
import { s } from "./ui.js";

const W = 640, H = 240, PAD = { l: 52, r: 12, t: 12, b: 30 };

function niceMax(v) {
  if (!(v > 0)) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}

export const shortNum = (n) => (n >= 1000 ? `${Math.round(n / 100) / 10}к` : String(Math.round(n)));

/** Вертикальные столбцы. rows: массив объектов; value(r) и label(r) берут из них число и подпись. */
export function barChart(rows, { value, label, title, fmt = shortNum, every = 1 }) {
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img", "aria-label": title });
  if (!rows.length) return svg;
  const max = niceMax(Math.max(0, ...rows.map(value)));
  const iw = W - PAD.l - PAD.r, ih = H - PAD.t - PAD.b, bw = iw / rows.length;
  for (let i = 0; i <= 4; i++) {
    const y = PAD.t + ih - (ih * i) / 4;
    svg.append(
      s("line", { x1: PAD.l, x2: W - PAD.r, y1: y, y2: y, class: "chart-grid" }),
      s("text", { x: PAD.l - 6, y: y + 4, class: "chart-axis", "text-anchor": "end" }, fmt((max * i) / 4)));
  }
  rows.forEach((r, i) => {
    const v = value(r), bh = (v / max) * ih;
    svg.append(s("rect", {
      x: PAD.l + i * bw + bw * 0.12, y: PAD.t + ih - bh, width: bw * 0.76, height: bh, rx: 2, class: "chart-bar",
    }, s("title", {}, `${label(r)}: ${fmt(v)}`)));
    if (i % every === 0) {
      svg.append(s("text", { x: PAD.l + i * bw + bw / 2, y: H - 10, class: "chart-axis", "text-anchor": "middle" }, label(r)));
    }
  });
  return svg;
}

/** Горизонтальные столбцы: удобно для категорий и топа напитков. */
export function hBarChart(rows, { value, label, title, fmt = shortNum }) {
  const rowH = 34, left = 150, right = 70, height = rows.length * rowH + 10;
  const svg = s("svg", { viewBox: `0 0 ${W} ${height}`, class: "chart", role: "img", "aria-label": title });
  const max = niceMax(Math.max(0, ...rows.map(value)));
  rows.forEach((r, i) => {
    const y = 6 + i * rowH, w = (value(r) / max) * (W - left - right);
    svg.append(
      s("text", { x: left - 8, y: y + 17, class: "chart-axis", "text-anchor": "end" }, label(r)),
      s("rect", { x: left, y, width: w, height: 22, rx: 3, class: "chart-bar" }, s("title", {}, `${label(r)}: ${fmt(value(r))}`)),
      s("text", { x: left + w + 6, y: y + 17, class: "chart-axis" }, fmt(value(r))));
  });
  return svg;
}
