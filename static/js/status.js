// Публичная страница статуса заказа (открывается по QR с чека).
import { h } from "./ui.js";
import { api } from "./api.js";
import { logoMark } from "./icons.js";

const STEPS = [["new", "Принят"], ["brewing", "Готовится"], ["ready", "Готов"], ["done", "Выдан"]];
const root = document.getElementById("app");
document.getElementById("logo").prepend(logoMark(32));
const token = new URLSearchParams(location.search).get("t");
let timer = null;

function view(st) {
  const cancelled = st.status === "cancelled";
  const at = STEPS.findIndex(([k]) => k === st.status);
  return h("section", { class: "status-card" },
    h("h1", {}, `Заказ № ${String(st.number).padStart(4, "0")}`),
    h("p", { class: "status-now" }, st.status_label),
    cancelled ? h("p", { class: "muted" }, "Заказ отменён. Если это ошибка, подойдите к стойке.")
      : h("ol", { class: "steps" }, STEPS.map(([k, text], i) => h("li", { class: i < at ? "done" : i === at ? "current" : "" }, text))),
    st.queue_ahead > 0 ? h("p", {}, `Перед вами заказов: ${st.queue_ahead}`) : null,
    h("p", { class: "muted" }, `Напитков в заказе: ${st.items_count}. Сумма: ${st.total.toLocaleString("ru-RU")} ₽.`),
    h("p", { class: "muted small" }, "Страница обновляется сама."));
}

async function load() {
  if (!token) return root.replaceChildren(h("p", { class: "empty" }, "В ссылке нет кода заказа. Отсканируйте QR на чеке ещё раз."));
  try {
    const st = await api(`/status/${encodeURIComponent(token)}`);
    root.replaceChildren(view(st));
    if (st.status === "done" || st.status === "cancelled") clearInterval(timer);
  } catch (err) {
    if (err.kind === "input") clearInterval(timer);   // заказ не найден: опрашивать бессмысленно
    root.replaceChildren(h("p", { class: `empty empty--${err.kind}` }, err.detail));
  }
}

await load();
timer = setInterval(load, 8000);
