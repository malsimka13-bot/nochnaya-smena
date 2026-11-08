// Панель администратора: статистика (графики и таблицы), заказы, напитки, блог.
import { h, money, dateTime, toast, showError, statusBadge } from "./ui.js";
import { api } from "./api.js";
import { barChart, hBarChart } from "./charts.js";
import { GLYPH_KEYS } from "./icons.js";

let activeTab = "stats";

export async function renderAdmin(page) {
  const tabs = [["stats", "Статистика", statsTab], ["orders", "Заказы", ordersTab], ["products", "Напитки", productsTab], ["posts", "Блог", postsTab]];
  const content = h("div", { class: "admin-content" });
  const bar = h("div", { class: "tabs", role: "tablist" });

  async function show(key) {
    activeTab = key;
    bar.replaceChildren(...tabs.map(([k, text]) => h("button", {
      type: "button", role: "tab", class: `tab${k === key ? " tab--active" : ""}`, "aria-selected": k === key ? "true" : "false",
      onclick: () => show(k),
    }, text)));
    content.replaceChildren();
    const run = tabs.find(([k]) => k === key)[2];
    try { await run(content); } catch (err) { showError(err); }
  }

  page.append(h("h1", {}, "Панель администратора"), bar, content);
  await show(activeTab);
}

const table = (head, rows) => h("div", { class: "table-wrap" }, h("table", {},
  h("thead", {}, h("tr", {}, head.map((t) => h("th", {}, t)))), h("tbody", {}, rows)));

// ---------- статистика ----------

async function statsTab(box) {
  let days = 30;
  const out = h("div");
  const select = h("select", { "aria-label": "Период", onchange: (e) => { days = Number(e.target.value); load(); } },
    [7, 30, 90].map((d) => h("option", { value: d, selected: d === days }, `${d} дней`)));
  box.append(h("div", { class: "toolbar" }, h("label", {}, "Период: ", select)), out);

  async function load() {
    try {
      const st = await api(`/admin/stats?days=${days}`);
      const sum = st.summary;
      const kpi = (name, value) => h("div", { class: "kpi" }, h("small", {}, name), h("strong", {}, value));
      const ddmm = (iso) => `${iso.slice(8, 10)}.${iso.slice(5, 7)}`;
      out.replaceChildren(
        h("div", { class: "kpis" }, kpi("Выручка", money(sum.revenue)), kpi("Заказов", sum.orders), kpi("Средний чек", money(sum.avg_check)),
          kpi("Напитков продано", sum.items_sold), kpi("Отменено", sum.cancelled)),
        h("h3", {}, "Выручка по дням, ₽"),
        barChart(st.daily, { value: (r) => r.revenue, label: (r) => ddmm(r.date), title: "Выручка по дням", every: Math.ceil(st.daily.length / 10) }),
        h("h3", {}, "Заказы по часам суток"),
        barChart(st.by_hour, { value: (r) => r.orders, label: (r) => String(r.hour), title: "Заказы по часам", fmt: String, every: 2 }),
        h("h3", {}, "Выручка по категориям, ₽"),
        st.by_category.length ? hBarChart(st.by_category, { value: (r) => r.revenue, label: (r) => r.name, title: "Выручка по категориям" })
          : h("p", { class: "empty" }, "Нет данных за период."),
        h("h3", {}, "Топ напитков"),
        st.top_products.length ? table(["Напиток", "Продано, шт.", "Выручка"],
          st.top_products.map((t) => h("tr", {}, h("td", { class: "cmd" }, t.name), h("td", {}, t.qty), h("td", {}, money(t.revenue)))))
          : h("p", { class: "empty" }, "Нет данных за период."),
        h("h3", {}, "Последние 7 дней"),
        table(["Дата", "Заказов", "Выручка"], st.daily.slice(-7).reverse().map((d) =>
          h("tr", {}, h("td", {}, ddmm(d.date)), h("td", {}, d.orders), h("td", {}, money(d.revenue))))));
    } catch (err) { showError(err); }
  }
  await load();
}

// ---------- заказы ----------

const NEXT = { new: ["brewing", "Взять в работу"], brewing: ["ready", "Готов"], ready: ["done", "Выдан"] };
const CAN_CANCEL = new Set(["new", "brewing"]);

async function ordersTab(box) {
  let filter = "";
  const list = h("div");
  const select = h("select", { "aria-label": "Фильтр по статусу", onchange: (e) => { filter = e.target.value; load(); } },
    h("option", { value: "" }, "Все статусы"),
    ...[["new", "Принят"], ["brewing", "Готовится"], ["ready", "Готов"], ["done", "Выдан"], ["cancelled", "Отменён"]].map(([v, t]) => h("option", { value: v }, t)));
  box.append(h("div", { class: "toolbar" }, select, h("button", { class: "btn btn--ghost", type: "button", onclick: () => load() }, "Обновить")), list);

  async function setStatus(id, status) {
    try {
      await api(`/admin/orders/${id}/status`, { method: "PUT", body: { status } });
      await load();
    } catch (err) { showError(err); }
  }

  async function load() {
    try {
      const orders = await api(`/admin/orders${filter ? `?status=${filter}` : ""}`);
      if (!orders.length) return list.replaceChildren(h("p", { class: "empty" }, "Заказов нет."));
      list.replaceChildren(table(["№", "Время", "Клиент", "Состав", "Сумма", "Статус", ""], orders.map((o) => h("tr", {},
        h("td", {}, o.number), h("td", {}, dateTime(o.created)), h("td", {}, o.customer.name),
        h("td", {}, o.items.map((i) => `${i.name} ×${i.qty}`).join(", ")),
        h("td", {}, money(o.total)), h("td", {}, statusBadge(o)),
        h("td", { class: "row-actions" },
          NEXT[o.status] ? h("button", { class: "btn btn--small", type: "button", onclick: () => setStatus(o.id, NEXT[o.status][0]) }, NEXT[o.status][1]) : null,
          CAN_CANCEL.has(o.status) ? h("button", { class: "link-btn", type: "button", onclick: () => setStatus(o.id, "cancelled") }, "Отменить") : null)))));
    } catch (err) { showError(err); }
  }
  await load();
}

// ---------- форма редактирования ----------

function editorForm(fields, initial, { onSave, onCancel }) {
  const err = h("p", { class: "form-error", hidden: true, role: "alert" });
  const inputs = {};
  const rows = fields.map((f) => {
    let input;
    if (f.type === "textarea") input = h("textarea", { rows: 4, maxlength: f.max });
    else if (f.type === "select") input = h("select", {}, f.options.map(([v, t]) => h("option", { value: v }, t)));
    else if (f.type === "checkbox") input = h("input", { type: "checkbox" });
    else input = h("input", { type: f.type === "number" ? "number" : "text", maxlength: f.max, step: f.type === "number" ? 1 : null });
    if (f.type === "checkbox") input.checked = Boolean(initial[f.key]);
    else input.value = String(initial[f.key] ?? "");
    inputs[f.key] = input;
    return h("label", { class: f.type === "checkbox" ? "check" : "" }, f.label, input);
  });

  const collect = () => Object.fromEntries(fields.map((f) => {
    const el = inputs[f.key];
    let v = f.type === "checkbox" ? el.checked : el.value;
    if (f.type === "number" && v !== "") v = Number(v);
    if (f.type === "select" && f.numeric) v = v === "" ? null : Number(v);
    return [f.key, v];
  }));

  const form = h("form", { class: "editor" }, rows, err,
    h("div", { class: "actions" }, h("button", { class: "btn", type: "submit" }, "Сохранить"),
      h("button", { class: "btn btn--ghost", type: "button", onclick: onCancel }, "Отмена")));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    err.hidden = true;
    try { await onSave(collect()); } catch (error) { showError(error, err); }
  });
  return form;
}

// ---------- напитки ----------

async function productsTab(box) {
  const formBox = h("div");
  const list = h("div");
  box.append(h("div", { class: "toolbar" }, h("button", { class: "btn", type: "button", onclick: () => edit({ price: 200, stock: 20, glyph: "cup", active: true }) }, "Новый напиток")), formBox, list);
  const cats = await api("/categories");

  function edit(item) {
    const fields = [
      { key: "name", label: "Название (команда)", type: "text", max: 60 },
      { key: "description", label: "Описание", type: "textarea", max: 300 },
      { key: "category_id", label: "Категория", type: "select", numeric: true, options: cats.map((c) => [c.id, c.name]) },
      { key: "price", label: "Цена, ₽ (1–100000)", type: "number" },
      { key: "stock", label: "Остаток (0–10000)", type: "number" },
      { key: "glyph", label: "Иконка", type: "select", options: GLYPH_KEYS.map((g) => [g, g]) },
      { key: "active", label: "Показывать в меню", type: "checkbox" },
    ];
    formBox.replaceChildren(h("h3", {}, item.id ? "Изменить напиток" : "Новый напиток"), editorForm(fields, { category_id: cats[0]?.id, ...item }, {
      onCancel: () => formBox.replaceChildren(),
      onSave: async (body) => {
        await api(item.id ? `/admin/products/${item.id}` : "/admin/products", { method: item.id ? "PUT" : "POST", body });
        toast("Напиток сохранён.", "ok");
        formBox.replaceChildren();
        await load();
      },
    }));
    formBox.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
  }

  async function load() {
    try {
      const items = await api("/admin/products");
      list.replaceChildren(table(["Название", "Категория", "Цена", "Остаток", "В меню", ""], items.map((p) => h("tr", {},
        h("td", { class: "cmd" }, p.name), h("td", {}, p.category), h("td", {}, money(p.price)), h("td", {}, p.stock),
        h("td", {}, p.active ? "да" : "нет"),
        h("td", { class: "row-actions" },
          h("button", { class: "btn btn--small", type: "button", onclick: () => edit(p) }, "Изменить"),
          p.active ? h("button", { class: "link-btn", type: "button", onclick: async () => {
            if (!confirm(`Убрать «${p.name}» из меню?`)) return;
            try { await api(`/admin/products/${p.id}`, { method: "DELETE" }); await load(); } catch (err) { showError(err); }
          } }, "Скрыть") : null)))));
    } catch (err) { showError(err); }
  }
  await load();
}

// ---------- блог ----------

async function postsTab(box) {
  const formBox = h("div");
  const list = h("div");
  box.append(h("div", { class: "toolbar" }, h("button", { class: "btn", type: "button", onclick: () => edit({ published: true }) }, "Новая запись")), formBox, list);
  const products = await api("/admin/products");

  function edit(post) {
    const fields = [
      { key: "title", label: "Заголовок (3–120)", type: "text", max: 120 },
      { key: "body", label: "Текст (10–5000)", type: "textarea", max: 5000 },
      { key: "playlist", label: "Что слушать (по треку на строку)", type: "textarea", max: 500 },
      { key: "product_id", label: "Напиток недели", type: "select", numeric: true, options: [["", "— без напитка —"], ...products.map((p) => [p.id, p.name])] },
      { key: "published", label: "Опубликовано", type: "checkbox" },
    ];
    const initial = { ...post, playlist: (post.playlist ?? []).join("\n"), product_id: post.product?.id ?? "" };
    formBox.replaceChildren(h("h3", {}, post.id ? "Изменить запись" : "Новая запись"), editorForm(fields, initial, {
      onCancel: () => formBox.replaceChildren(),
      onSave: async (body) => {
        await api(post.id ? `/admin/posts/${post.id}` : "/admin/posts", { method: post.id ? "PUT" : "POST", body });
        toast("Запись сохранена.", "ok");
        formBox.replaceChildren();
        await load();
      },
    }));
  }

  async function load() {
    try {
      const posts = await api("/admin/posts");
      list.replaceChildren(table(["Дата", "Заголовок", "Статус", ""], posts.map((p) => h("tr", {},
        h("td", {}, p.created), h("td", {}, p.title), h("td", {}, p.published ? "опубликовано" : "черновик"),
        h("td", { class: "row-actions" },
          h("button", { class: "btn btn--small", type: "button", onclick: () => edit(p) }, "Изменить"),
          h("button", { class: "link-btn", type: "button", onclick: async () => {
            if (!confirm(`Удалить запись «${p.title}»?`)) return;
            try { await api(`/admin/posts/${p.id}`, { method: "DELETE" }); await load(); } catch (err) { showError(err); }
          } }, "Удалить"))))));
    } catch (err) { showError(err); }
  }
  await load();
}
