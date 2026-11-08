// Страницы магазина: каталог, корзина, вход и регистрация, блог.
import { h, money, toast, showError, debounce } from "./ui.js";
import { api, session, setToken } from "./api.js";
import { glyph } from "./icons.js";
import { addToCart, getCart, setQty, removeLine, clearCart, syncWithCatalog, cartTotal, MAX_QTY } from "./cart.js";

// ---------- каталог ----------

function productCard(p) {
  const soldOut = !p.available;
  const btn = h("button", { class: "btn", type: "button", disabled: soldOut }, soldOut ? "Нет в наличии" : "В корзину");
  btn.addEventListener("click", () => {
    if (!addToCart(p)) return toast(`Не больше ${MAX_QTY} шт. одного напитка.`, "input");
    btn.textContent = "Добавлено ✓";
    setTimeout(() => { btn.textContent = "В корзину"; }, 900);
  });
  return h("article", { class: `card${soldOut ? " card--sold" : ""}` },
    h("div", { class: "card-icon" }, glyph(p.glyph, 64)),
    h("h3", { class: "cmd" }, p.name),
    h("p", { class: "muted" }, p.description),
    h("div", { class: "card-foot" },
      h("strong", {}, money(p.price)),
      !soldOut && p.stock <= 5 ? h("small", { class: "warn" }, `осталось ${p.stock}`) : null,
      btn));
}

export async function renderHome(page) {
  const state = { category: null, q: "", sort: "name" };
  const grid = h("div", { class: "grid", "aria-live": "polite" });
  const chips = h("div", { class: "chips" });
  const cats = await api("/categories");

  async function load() {
    try {
      const params = new URLSearchParams({ sort: state.sort });
      if (state.category) params.set("category", state.category);
      if (state.q) params.set("q", state.q);
      const items = await api(`/products?${params}`);
      grid.replaceChildren(...(items.length ? items.map(productCard)
        : [h("p", { class: "empty" }, "Ничего не нашлось. Попробуйте другой запрос.")]));
    } catch (err) { showError(err); }
  }

  function drawChips() {
    const make = (id, text) => h("button", {
      type: "button", class: `chip${state.category === id ? " chip--active" : ""}`,
      onclick: () => { state.category = id; drawChips(); load(); },
    }, text);
    chips.replaceChildren(make(null, "Все"), ...cats.map((c) => make(c.id, c.name)));
  }

  const search = h("input", {
    type: "search", placeholder: "Поиск по названию и описанию", maxlength: 60, "aria-label": "Поиск напитков",
    oninput: debounce((e) => { state.q = e.target.value.trim(); load(); }, 250),
  });
  const sort = h("select", { "aria-label": "Сортировка", onchange: (e) => { state.sort = e.target.value; load(); } },
    h("option", { value: "name" }, "По названию"),
    h("option", { value: "price_asc" }, "Сначала дешёвые"),
    h("option", { value: "price_desc" }, "Сначала дорогие"));

  page.append(
    h("section", { class: "hero" },
      h("h1", {}, "Ночная смена"),
      h("p", {}, "Кофейня для тех, кто ещё не спит. Открыто с 16:00 до 04:00."),
      h("p", { class: "cmd small" }, "$ sudo make coffee")),
    h("section", {}, h("h2", {}, "Меню"),
      h("div", { class: "toolbar" }, search, sort), chips, grid));
  drawChips();
  await load();
}

// ---------- корзина ----------

export async function renderCart(page) {
  page.append(h("h1", {}, "Корзина"));
  const body = h("div");
  page.append(body);

  let products = [];
  try {
    products = await api("/products");
    syncWithCatalog(products);
  } catch (err) { showError(err); }
  const stock = new Map(products.map((p) => [p.id, p.stock]));

  function draw() {
    const lines = getCart();
    if (!lines.length) {
      body.replaceChildren(h("p", { class: "empty" }, "В корзине пусто. "), h("a", { class: "btn", href: "#/" }, "К меню"));
      return;
    }
    const errBox = h("p", { class: "form-error", hidden: true, role: "alert" });
    const comment = h("textarea", { rows: 2, maxlength: 200, placeholder: "Комментарий к заказу (необязательно)", "aria-label": "Комментарий к заказу" });
    const checkoutBtn = h("button", { class: "btn btn--big", type: "button" }, "Оформить заказ");
    checkoutBtn.addEventListener("click", async () => {
      if (!session.user) {
        session.next = "#/cart";
        toast("Войдите, чтобы оформить заказ.", "auth");
        location.hash = "#/login";
        return;
      }
      checkoutBtn.disabled = true;
      try {
        const order = await api("/orders", {
          method: "POST",
          body: { items: getCart().map((l) => ({ product_id: l.id, qty: l.qty })), comment: comment.value },
        });
        clearCart();
        toast(`Заказ № ${order.number} принят.`, "ok");
        location.hash = `#/order/${order.id}`;
      } catch (err) {
        showError(err, errBox);
      } finally {
        checkoutBtn.disabled = false;
      }
    });

    const rows = lines.map((l) => {
      const left = stock.get(l.id);
      return h("tr", {},
        h("td", {}, h("span", { class: "cmd" }, l.name),
          left !== undefined && l.qty > left ? h("small", { class: "warn" }, left > 0 ? ` в наличии только ${left}` : " закончился") : null),
        h("td", {}, money(l.price)),
        h("td", {}, h("div", { class: "stepper" },
          h("button", { type: "button", "aria-label": "Меньше", onclick: () => { setQty(l.id, l.qty - 1); draw(); } }, "−"),
          h("span", {}, l.qty),
          h("button", { type: "button", "aria-label": "Больше", disabled: l.qty >= MAX_QTY, onclick: () => { setQty(l.id, l.qty + 1); draw(); } }, "+"))),
        h("td", {}, money(l.price * l.qty)),
        h("td", {}, h("button", { type: "button", class: "link-btn", onclick: () => { removeLine(l.id); draw(); } }, "Убрать")));
    });
    body.replaceChildren(
      h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, ...["Напиток", "Цена", "Кол-во", "Сумма", ""].map((t) => h("th", {}, t)))),
        h("tbody", {}, rows))),
      h("p", { class: "total" }, `Итого: ${money(cartTotal())}`),
      comment, errBox, checkoutBtn);
  }
  draw();
}

// ---------- вход и регистрация ----------

function authPage(page, { title, path, submitText, fields, footer }) {
  const err = h("p", { class: "form-error", hidden: true, role: "alert" });
  const inputs = fields.map((f) => h("input", {
    name: f.name, type: f.type, autocomplete: f.autocomplete, maxlength: f.max, placeholder: f.placeholder, required: true, "aria-label": f.label,
  }));
  const form = h("form", { class: "auth" },
    h("h1", {}, title),
    ...fields.map((f, i) => h("label", {}, f.label, inputs[i])),
    err, h("button", { class: "btn btn--big", type: "submit" }, submitText), footer);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    err.hidden = true;
    const body = Object.fromEntries(fields.map((f, i) => [f.name, inputs[i].value]));
    try {
      const res = await api(path, { method: "POST", body });
      setToken(res.token);
      session.user = res.user;
      window.dispatchEvent(new Event("session-changed"));
      const next = session.next || "#/";
      session.next = null;
      location.hash = next;
    } catch (error) { showError(error, err); }
  });
  page.append(form);
}

export function renderLogin(page) {
  authPage(page, {
    title: "Вход", path: "/login", submitText: "Войти",
    fields: [
      { name: "email", type: "email", label: "Email", autocomplete: "email", max: 120 },
      { name: "password", type: "password", label: "Пароль", autocomplete: "current-password", max: 200 },
    ],
    footer: h("p", { class: "muted" }, "Нет аккаунта? ", h("a", { href: "#/register" }, "Зарегистрироваться")),
  });
}

export function renderRegister(page) {
  authPage(page, {
    title: "Регистрация", path: "/register", submitText: "Создать аккаунт",
    fields: [
      { name: "name", type: "text", label: "Имя (2–60 символов)", autocomplete: "name", max: 60 },
      { name: "email", type: "email", label: "Email", autocomplete: "email", max: 120 },
      { name: "password", type: "password", label: "Пароль (6–72 символа)", autocomplete: "new-password", max: 72 },
    ],
    footer: h("p", { class: "muted" }, "Уже есть аккаунт? ", h("a", { href: "#/login" }, "Войти")),
  });
}

// ---------- блог ----------

const playlistBlock = (tracks) => tracks.length
  ? h("div", { class: "playlist" }, h("strong", {}, "Что слушать"), h("ul", {}, tracks.map((t) => h("li", {}, t))))
  : null;

export async function renderBlog(page) {
  const posts = await api("/posts");
  page.append(h("h1", {}, "Блог"), h("p", { class: "muted" }, "Напиток недели и музыка к нему."));
  if (!posts.length) page.append(h("p", { class: "empty" }, "Пока записей нет."));
  page.append(h("div", { class: "posts" }, posts.map((p) => h("article", { class: "post" },
    h("small", { class: "muted" }, p.created),
    h("h2", {}, h("a", { href: `#/blog/${p.id}` }, p.title)),
    h("p", {}, p.summary),
    p.product ? h("span", { class: "chip" }, p.product.name) : null,
    playlistBlock(p.playlist)))));
}

export async function renderPost(page, id) {
  const p = await api(`/posts/${id}`);
  page.append(
    h("a", { href: "#/blog" }, "← Все записи"),
    h("article", { class: "post post--full" },
      h("small", { class: "muted" }, p.created),
      h("h1", {}, p.title),
      p.body.split(/\n+/).map((para) => h("p", {}, para)),
      playlistBlock(p.playlist),
      p.product ? h("p", {}, h("a", { class: "btn", href: "#/" }, `Заказать: ${p.product.name}`)) : null));
}
