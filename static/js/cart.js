// Корзина живёт в браузере. Цены и остатки окончательно проверяет сервер при оформлении заказа.
export const MAX_QTY = 20;
const KEY = "smena.cart";

const valid = (l) => l && Number.isInteger(l.id) && typeof l.name === "string" && Number.isFinite(l.price)
  && Number.isInteger(l.qty) && l.qty >= 1 && l.qty <= MAX_QTY;

function read() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY));
    return Array.isArray(raw) ? raw.filter(valid) : [];
  } catch { return []; }
}

let lines = read();

function persist() {
  try { localStorage.setItem(KEY, JSON.stringify(lines)); } catch { /* приватный режим: корзина живёт до перезагрузки */ }
  if (typeof window !== "undefined") window.dispatchEvent(new Event("cart-changed"));
}

export const getCart = () => lines.map((l) => ({ ...l }));
export const cartCount = () => lines.reduce((a, l) => a + l.qty, 0);
export const cartTotal = () => lines.reduce((a, l) => a + l.qty * l.price, 0);

export function addToCart(p) {
  const line = lines.find((l) => l.id === p.id);
  if (line) {
    if (line.qty >= MAX_QTY) return false;
    line.qty += 1;
  } else {
    lines.push({ id: p.id, name: p.name, price: p.price, qty: 1 });
  }
  persist();
  return true;
}

export function removeLine(id) {
  lines = lines.filter((l) => l.id !== id);
  persist();
}

export function setQty(id, qty) {
  const n = Math.floor(Number(qty));
  if (!(n >= 1)) return removeLine(id);
  lines = lines.map((l) => (l.id === id ? { ...l, qty: Math.min(n, MAX_QTY) } : l));
  persist();
}

export function clearCart() {
  lines = [];
  persist();
}

/** Обновляет имена и цены по актуальному каталогу, убирает снятые с продажи напитки. */
export function syncWithCatalog(products) {
  const byId = new Map(products.map((p) => [p.id, p]));
  lines = lines.filter((l) => byId.has(l.id)).map((l) => ({ ...l, name: byId.get(l.id).name, price: byId.get(l.id).price }));
  persist();
}
