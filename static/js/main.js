// Маршрутизатор на хешах (#/...) и шапка сайта.
import { h, toast } from "./ui.js";
import { session, loadUser, setToken } from "./api.js";
import { logoMark } from "./icons.js";
import { cartCount } from "./cart.js";
import { renderHome, renderCart, renderLogin, renderRegister, renderBlog, renderPost } from "./pages_shop.js";
import { renderOrders, renderReceipt } from "./pages_order.js";
import { renderAdmin } from "./pages_admin.js";

const root = document.getElementById("app");
const nav = document.getElementById("nav");

// [шаблон, обработчик, нужная роль]
const routes = [
  [/^#\/?$/, renderHome],
  [/^#\/blog$/, renderBlog],
  [/^#\/blog\/(\d+)$/, renderPost],
  [/^#\/cart$/, renderCart],
  [/^#\/login$/, renderLogin],
  [/^#\/register$/, renderRegister],
  [/^#\/orders$/, renderOrders, "client"],
  [/^#\/order\/(\d+)$/, renderReceipt, "client"],
  [/^#\/admin$/, renderAdmin, "admin"],
];

function renderNav() {
  const here = location.hash || "#/";
  const link = (href, text) => h("a", { href, class: here === href ? "active" : "" }, text);
  const items = [link("#/", "Меню"), link("#/blog", "Блог")];
  if (session.user) items.push(link("#/orders", "Мои заказы"));
  if (session.user?.role === "admin") items.push(link("#/admin", "Админка"));
  items.push(h("a", { href: "#/cart", class: `cart-link${here === "#/cart" ? " active" : ""}` }, "Корзина ", h("span", { class: "badge", id: "cart-badge" }, String(cartCount()))));
  items.push(session.user
    ? h("button", { class: "link-btn", type: "button", onclick: logout }, `Выйти (${session.user.name})`)
    : link("#/login", "Войти"));
  nav.replaceChildren(...items);
}

function logout() {
  setToken(null);
  session.user = null;
  toast("Вы вышли из аккаунта.", "ok");
  if (location.hash === "#/" || location.hash === "") route();
  else location.hash = "#/";
}

function errorBlock(err) {
  const message = err?.kind ? err.detail : "Не удалось показать страницу. Обновите её.";
  const title = { input: "Не найдено", auth: "Нет доступа", server: "Сбой сервера", network: "Нет связи" }[err?.kind] ?? "Ошибка";
  return h("div", { class: `empty empty--${err?.kind ?? "server"}` }, h("h2", {}, title), h("p", {}, message),
    h("button", { class: "btn", type: "button", onclick: route }, "Повторить"), " ", h("a", { class: "btn btn--ghost", href: "#/" }, "На главную"));
}

async function route() {
  const hash = location.hash || "#/";
  renderNav();
  const found = routes.find(([re]) => re.test(hash));
  const page = h("div", { class: "page" });
  root.replaceChildren(page);   // устаревшая отрисовка пишет в уже отсоединённый page и ничего не портит
  window.scrollTo(0, 0);
  if (!found) {
    page.append(errorBlock({ kind: "input", detail: "Такой страницы нет." }));
    return;
  }
  const [re, handler, role] = found;
  if (role && !session.user) {
    session.next = hash;
    toast("Эта страница доступна после входа.", "auth");
    location.hash = "#/login";
    return;
  }
  if (role === "admin" && session.user.role !== "admin") {
    toast("Раздел только для администратора.", "auth");
    location.hash = "#/";
    return;
  }
  try {
    await handler(page, ...hash.match(re).slice(1));
  } catch (err) {
    page.replaceChildren(errorBlock(err));
  }
}

window.addEventListener("hashchange", route);
window.addEventListener("session-changed", renderNav);
window.addEventListener("session-expired", () => {
  toast("Сессия закончилась. Войдите снова.", "auth");
  renderNav();
  location.hash = "#/login";
});
window.addEventListener("cart-changed", () => {
  const badge = document.getElementById("cart-badge");
  if (badge) badge.textContent = String(cartCount());
});

document.getElementById("logo").prepend(logoMark(34));
try { await loadUser(); } catch (err) { toast(err.detail ?? "Сервер недоступен.", err.kind ?? "server"); }
route();
