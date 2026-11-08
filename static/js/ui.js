// Общие помощники интерфейса: создание элементов без innerHTML (защита от XSS), уведомления, форматирование.
const SVG_NS = "http://www.w3.org/2000/svg";

/** h("div", {class: "x", onclick: fn}, "текст", другойЭлемент) */
export function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs ?? {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

/** То же для SVG-элементов. */
export function s(tag, attrs = {}, ...kids) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs ?? {})) {
    if (v != null && v !== false) el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

export const money = (n) => `${Number(n).toLocaleString("ru-RU")} ₽`;

export function dateTime(iso) {
  return new Date(iso).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

const TITLES = { input: "Проверьте данные", auth: "Нужен вход", server: "Сбой сервера", network: "Нет связи", ok: "Готово" };

export function toast(message, kind = "info") {
  let box = document.getElementById("toasts");
  if (!box) {
    box = h("div", { id: "toasts" });
    document.body.append(box);
  }
  const alert = kind !== "ok" && kind !== "info";
  const el = h("div", { class: `toast toast--${kind}`, role: alert ? "alert" : "status" },
    TITLES[kind] ? h("strong", {}, TITLES[kind]) : null, h("span", {}, message));
  box.append(el);
  setTimeout(() => el.remove(), kind === "server" || kind === "network" ? 8000 : 5000);
}

/** Показывает ошибку API: ввод, доступ, сбой сервера и обрыв связи выглядят по-разному. */
export function showError(err, target) {
  const kind = err?.kind ?? "server";
  const message = err?.kind ? err.detail : "Что-то пошло не так на странице. Обновите её и попробуйте ещё раз.";
  if (target) {
    target.textContent = message;
    target.className = `form-error form-error--${kind}`;
    target.hidden = false;
    if (kind === "server" || kind === "network") toast(message, kind);
  } else {
    toast(message, kind);
  }
}

export const statusBadge = (order) => h("span", { class: `status st-${order.status}` }, order.status_label);
