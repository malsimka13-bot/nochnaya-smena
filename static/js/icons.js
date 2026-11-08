// Иконки напитков, стикеры чека и логотип. Всё рисуется SVG, внешних картинок нет.
import { s } from "./ui.js";

const STEAM = ["M19 17v-5", "M27 17v-10", "M35 17v-7"];  // «пар» в виде эквалайзера
const GLYPHS = {
  cup: ["M12 22h30v12a12 12 0 0 1-12 12H24A12 12 0 0 1 12 34z", "M42 26h3a6 6 0 0 1 0 12h-3", ...STEAM],
  shot: ["M16 26h22v8a9 9 0 0 1-9 9h-4a9 9 0 0 1-9-9z", "M10 46h34", "M22 20v-4", "M27 20v-8", "M32 20v-5"],
  mug: ["M12 20h26v22a4 4 0 0 1-4 4H16a4 4 0 0 1-4-4z", "M38 25h3a5 5 0 0 1 0 10h-3", "M19 14v-3", "M25 14v-7", "M31 14v-5"],
  filter: ["M12 12h32l-9 16H21z", "M21 34h14v9a3 3 0 0 1-3 3h-8a3 3 0 0 1-3-3z", "M28 28v6"],
  iced: ["M14 14h28l-4 32H18z", "M22 24h12", "M36 8l-4 14", "M21 29h8v8h-8z"],
  leaf: ["M10 28h36a18 18 0 0 1-36 0z", "M28 24c-9-2-11-10-11-15 9 0 15 5 11 15z"],
  pastry: ["M6 38c3-14 14-22 22-22s19 8 22 22c-6-4-10-3-13 1-2-5-5-6-9-6s-7 1-9 6c-3-4-7-5-13-1z", "M20 24l4 8M36 24l-4 8"],
  cake: ["M8 42V28l40-8v22z", "M8 35h40", "M35 14a3 3 0 1 0 6 0a3 3 0 1 0-6 0z"],
};
export const GLYPH_KEYS = Object.keys(GLYPHS);

export function glyph(name, size = 56) {
  const paths = GLYPHS[name] ?? GLYPHS.cup;
  return s("svg", {
    viewBox: "0 0 56 56", width: size, height: size, fill: "none", stroke: "currentColor",
    "stroke-width": 3, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true", class: "glyph",
  }, paths.map((d) => s("path", { d })));
}

// Стикеры: viewBox 100x100, цвета в тон Aroma Craft
const label = (text, size, fill) => s("text", {
  x: 50, y: 50, "text-anchor": "middle", "dominant-baseline": "central", "font-family": "monospace",
  "font-weight": "700", "font-size": size, fill,
}, text);

const STICKER_ART = {
  sudo: () => [s("rect", { x: 5, y: 28, width: 90, height: 44, rx: 9, fill: "#2c2523" }), label("sudo", 28, "#faedcd")],
  lgtm: () => [s("rect", { x: 5, y: 28, width: 90, height: 44, rx: 9, fill: "#4f7a3a" }), label("LGTM", 26, "#ffffff")],
  bug: () => [
    s("ellipse", { cx: 50, cy: 58, rx: 20, ry: 26, fill: "#7b4425" }), s("circle", { cx: 50, cy: 26, r: 11, fill: "#583018" }),
    s("path", { d: "M30 48H14M30 62H12M32 76L18 86M70 48h16M70 62h18M68 76l14 10M44 17l-6-8M56 17l6-8", stroke: "#583018", "stroke-width": 4, "stroke-linecap": "round", fill: "none" }),
    s("path", { d: "M50 34v50", stroke: "#faedcd", "stroke-width": 3 }),
  ],
  ship: () => [s("rect", { x: 5, y: 28, width: 90, height: 44, rx: 22, fill: "#d4a373", stroke: "#583018", "stroke-width": 3 }), label("SHIP IT", 20, "#2c2523")],
  zzz: () => [s("circle", { cx: 50, cy: 50, r: 44, fill: "#3a2517" }), label("Zzz", 34, "#faedcd")],
  fire: () => [
    s("path", { d: "M50 6C58 28 78 38 78 62a28 28 0 0 1-56 0c0-14 8-22 14-30 2 10 8 14 12 14-4-14-2-26 2-40z", fill: "#e0662b" }),
    s("path", { d: "M50 48c6 10 14 14 14 26a14 14 0 0 1-28 0c0-8 6-12 14-26z", fill: "#f5b041" }),
  ],
  star: () => [s("polygon", { points: "50,6 61,37 94,38 68,58 77,90 50,71 23,90 32,58 6,38 39,37", fill: "#e8b923", stroke: "#583018", "stroke-width": 3, "stroke-linejoin": "round" })],
  heart: () => [s("path", { d: "M50 88C20 64 8 48 8 32a21 21 0 0 1 42-6 21 21 0 0 1 42 6c0 16-12 32-42 56z", fill: "#c0392b" })],
};

export function stickerArt(code, size = 72) {
  const parts = (STICKER_ART[code] ?? STICKER_ART.star)();
  return s("svg", { viewBox: "0 0 100 100", width: size, height: size, class: "sticker-art", "aria-hidden": "true" }, parts);
}

/** Логотип: чашка, над которой «пар» превращён в эквалайзер. */
export function logoMark(size = 36) {
  const bars = [[16, 8], [24, 16], [32, 12], [40, 6]].map(([x, hgt]) =>
    s("rect", { x, y: 26 - hgt, width: 5, height: hgt, rx: 2.5, fill: "#d4a373" }));
  return s("svg", { viewBox: "0 0 64 64", width: size, height: size, class: "logo-mark", "aria-hidden": "true" },
    ...bars,
    s("path", { d: "M12 30h36v8a16 16 0 0 1-16 16h-4A16 16 0 0 1 12 38z", fill: "#7b4425" }),
    s("path", { d: "M48 34h3a7 7 0 0 1 0 14h-4", fill: "none", stroke: "#7b4425", "stroke-width": 4, "stroke-linecap": "round" }));
}
