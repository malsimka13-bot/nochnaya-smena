// Мои заказы и страница чека: QR на статус и стикеры, которые перетаскиваются мышью или пальцем.
import { h, money, dateTime, toast, showError, statusBadge } from "./ui.js";
import { api } from "./api.js";
import { logoMark, stickerArt } from "./icons.js";

const MAX_STICKERS = 12;   // как на сервере
const MAX_ROT = 45;
const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
const pad = (n) => String(n).padStart(4, "0");

export async function renderOrders(page) {
  const orders = await api("/orders/my");
  page.append(h("h1", {}, "Мои заказы"));
  if (!orders.length) {
    page.append(h("p", { class: "empty" }, "Заказов пока нет. "), h("a", { class: "btn", href: "#/" }, "К меню"));
    return;
  }
  page.append(h("div", { class: "orders" }, orders.map((o) => h("a", { class: "order-card", href: `#/order/${o.id}` },
    h("strong", {}, `№ ${pad(o.number)}`),
    h("span", { class: "muted" }, dateTime(o.created)),
    statusBadge(o),
    h("b", {}, money(o.total))))));
}

export async function renderReceipt(page, id) {
  const order = await api(`/orders/${id}`);
  const placed = order.stickers.map((st, i) => ({ ...st, uid: i + 1 }));
  let nextUid = placed.length + 1;
  let dirty = false;
  const els = new Map();          // uid -> элемент стикера на чеке
  const layer = h("div", { class: "sticker-layer" });
  const saveBtn = h("button", { class: "btn", type: "button" }, "Сохранить стикеры");
  const counter = h("small", { class: "muted" });

  function markDirty() {
    dirty = true;
    saveBtn.textContent = "Сохранить стикеры •";
    counter.textContent = `Стикеров: ${placed.length} из ${MAX_STICKERS}`;
  }

  function position(el, st) {
    el.style.left = `${st.x * 100}%`;
    el.style.top = `${st.y * 100}%`;
    el.style.transform = `translate(-50%, -50%) rotate(${st.rot}deg)`;
  }

  function select(uid) {
    for (const [key, el] of els) el.classList.toggle("selected", key === uid);
  }

  function addSticker(code, x, y) {
    if (placed.length >= MAX_STICKERS) return toast(`На чеке не больше ${MAX_STICKERS} стикеров.`, "input");
    const st = { uid: nextUid++, code, x: clamp(x), y: clamp(y), rot: Math.round(Math.random() * 30 - 15) };
    placed.push(st);
    layer.append(makeStickerEl(st));
    select(st.uid);
    markDirty();
  }

  function removeSticker(st) {
    placed.splice(placed.indexOf(st), 1);
    els.get(st.uid)?.remove();
    els.delete(st.uid);
    markDirty();
  }

  function rotate(st, delta) {
    st.rot = clamp(st.rot + delta, -MAX_ROT, MAX_ROT);
    position(els.get(st.uid), st);
    markDirty();
  }

  function makeStickerEl(st) {
    const controls = h("div", { class: "sticker-controls" },
      h("button", { type: "button", title: "Повернуть влево", "aria-label": "Повернуть влево", onclick: () => rotate(st, -10) }, "⟲"),
      h("button", { type: "button", title: "Повернуть вправо", "aria-label": "Повернуть вправо", onclick: () => rotate(st, 10) }, "⟳"),
      h("button", { type: "button", title: "Убрать", "aria-label": "Убрать стикер", onclick: () => removeSticker(st) }, "×"));
    const el = h("div", { class: "sticker" }, stickerArt(st.code, 72), controls);
    position(el, st);
    els.set(st.uid, el);

    el.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".sticker-controls")) return;
      e.preventDefault();
      select(st.uid);
      el.setPointerCapture(e.pointerId);
      const move = (ev) => {
        const r = layer.getBoundingClientRect();
        st.x = clamp((ev.clientX - r.left) / r.width);
        st.y = clamp((ev.clientY - r.top) / r.height);
        position(el, st);
        markDirty();
      };
      const up = () => {
        el.removeEventListener("pointermove", move);
        el.removeEventListener("pointerup", up);
        el.removeEventListener("pointercancel", up);
      };
      el.addEventListener("pointermove", move);
      el.addEventListener("pointerup", up);
      el.addEventListener("pointercancel", up);
    });
    return el;
  }

  // Перетаскивание из набора на чек. Короткое нажатие кладёт стикер в центр.
  function trayTile(code, text) {
    const tile = h("button", { class: "tile", type: "button", title: `${text}: перетащите на чек`, "aria-label": `Добавить стикер «${text}»` },
      stickerArt(code, 56), h("small", {}, text));
    tile.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      const start = { x: e.clientX, y: e.clientY };
      const ghost = h("div", { class: "ghost" }, stickerArt(code, 72));
      const moveGhost = (ev) => { ghost.style.left = `${ev.clientX}px`; ghost.style.top = `${ev.clientY}px`; };
      moveGhost(e);
      document.body.append(ghost);
      const finish = () => {
        window.removeEventListener("pointermove", moveGhost);
        window.removeEventListener("pointerup", up);
        window.removeEventListener("pointercancel", finish);
        ghost.remove();
      };
      const up = (ev) => {
        finish();
        const r = layer.getBoundingClientRect();
        const inside = ev.clientX >= r.left && ev.clientX <= r.right && ev.clientY >= r.top && ev.clientY <= r.bottom;
        const moved = Math.hypot(ev.clientX - start.x, ev.clientY - start.y) > 6;
        if (inside) addSticker(code, (ev.clientX - r.left) / r.width, (ev.clientY - r.top) / r.height);
        else if (!moved) addSticker(code, 0.5, 0.5);
      };
      window.addEventListener("pointermove", moveGhost);
      window.addEventListener("pointerup", up);
      window.addEventListener("pointercancel", finish);
    });
    // клавиатура: Enter и Space дают click с detail === 0 (мышь даёт detail >= 1, её обрабатывает pointerdown)
    tile.addEventListener("click", (e) => { if (e.detail === 0) addSticker(code, 0.5, 0.5); });
    return tile;
  }

  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    try {
      await api(`/orders/${order.id}/stickers`, {
        method: "PUT",
        body: { stickers: placed.map((st) => ({ code: st.code, x: Math.round(st.x * 1000) / 1000, y: Math.round(st.y * 1000) / 1000, rot: Math.round(st.rot) })) },
      });
      dirty = false;
      saveBtn.textContent = "Сохранить стикеры";
      toast("Стикеры сохранены.", "ok");
    } catch (err) { showError(err); } finally { saveBtn.disabled = false; }
  });

  const receipt = h("div", { class: "receipt", id: "receipt" },
    h("div", { class: "receipt-head" }, logoMark(32), h("strong", {}, "НОЧНАЯ СМЕНА"), h("small", {}, "16:00–04:00")),
    h("div", { class: "receipt-meta" }, h("span", {}, `Чек № ${pad(order.number)}`), h("span", {}, dateTime(order.created))),
    h("ul", { class: "receipt-lines" }, order.items.map((i) => h("li", {},
      h("span", { class: "rl-name" }, i.name),
      h("span", { class: "rl-calc" }, `${i.qty} × ${money(i.price)}`),
      h("b", {}, money(i.sum))))),
    h("div", { class: "receipt-total" }, h("span", {}, "ИТОГО"), h("span", {}, money(order.total))),
    order.comment ? h("p", { class: "receipt-note" }, `Комментарий: ${order.comment}`) : null,
    h("div", { class: "receipt-qr" },
      h("img", { src: `/api/status/${order.token}/qr.svg`, alt: "QR-код: статус заказа", width: 140, height: 140 }),
      h("small", {}, "Сканируйте, чтобы следить за заказом")),
    h("p", { class: "receipt-foot" }, "exit 0: спасибо, что не спите с нами"),
    layer);
  placed.forEach((st) => layer.append(makeStickerEl(st)));
  counter.textContent = `Стикеров: ${placed.length} из ${MAX_STICKERS}`;

  const stickerList = await api("/stickers");
  const cancelBtn = order.status === "new"
    ? h("button", { class: "btn btn--ghost", type: "button", onclick: async () => {
      if (!confirm("Отменить заказ?")) return;
      try {
        await api(`/orders/${order.id}/cancel`, { method: "POST" });
        toast("Заказ отменён.", "ok");
        page.replaceChildren();
        await renderReceipt(page, id);
      } catch (err) { showError(err); }
    } }, "Отменить заказ")
    : null;

  page.append(
    h("a", { href: "#/orders" }, "← Мои заказы"),
    h("div", { class: "receipt-page" },
      h("div", { class: "receipt-col" }, receipt),
      h("aside", { class: "side" },
        h("h2", {}, `Заказ № ${pad(order.number)}`),
        h("p", {}, "Статус: ", statusBadge(order)),
        h("p", {}, h("a", { href: `/status?t=${order.token}`, target: "_blank", rel: "noopener" }, "Открыть страницу статуса")),
        h("h3", {}, "Украсьте чек"),
        h("p", { class: "muted small" }, "Перетащите стикер на чек. Выберите стикер на чеке, чтобы повернуть или убрать его."),
        h("div", { class: "tray" }, stickerList.map((st) => trayTile(st.code, st.label))),
        counter,
        h("div", { class: "actions" }, saveBtn, h("button", { class: "btn btn--ghost", type: "button", onclick: () => window.print() }, "Печать"), cancelBtn))));

  // клик мимо стикера снимает выделение
  receipt.addEventListener("pointerdown", (e) => { if (!e.target.closest(".sticker")) select(null); });
  window.addEventListener("beforeunload", (e) => { if (dirty) e.preventDefault(); }, { once: true });
}
