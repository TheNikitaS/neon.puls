/* Мелкие помощники интерфейса. */
const UI = (() => {
  const money = (v) =>
    (v === null || v === undefined ? "—" : Math.round(v).toLocaleString("ru-RU")) + " ₽";
  const num = (v) =>
    v === null || v === undefined ? "—" : Math.round(v).toLocaleString("ru-RU");
  const pct = (v, digits = 1) =>
    v === null || v === undefined ? "—" : `${(v * 100).toFixed(digits).replace(".", ",")}%`;
  const signed = (v) =>
    v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(1).replace(".", ",")}%`;

  function deltaBadge(d) {
    if (!d || d.pct === null || d.pct === undefined) return `<span class="delta flat">—</span>`;
    const cls = d.pct > 0.5 ? "up" : d.pct < -0.5 ? "down" : "flat";
    return `<span class="delta ${cls}">${signed(d.pct)}</span>`;
  }

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[ch]));
  }

  function toast(message, kind = "") {
    const root = document.getElementById("toast-root");
    const node = document.createElement("div");
    node.className = `toast ${kind}`;
    node.textContent = message;
    root.appendChild(node);
    setTimeout(() => {
      node.style.opacity = "0";
      node.style.transition = "opacity .25s";
      setTimeout(() => node.remove(), 260);
    }, 3600);
  }

  function modal({ title, subtitle = "", body, actions = [] }) {
    const root = document.getElementById("modal-root");
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true">
        <h2>${esc(title)}</h2>
        ${subtitle ? `<div class="sub">${esc(subtitle)}</div>` : ""}
        <div class="modal-body">${body}</div>
        <div class="modal-foot"></div>
      </div>`;
    const foot = backdrop.querySelector(".modal-foot");
    const close = () => backdrop.remove();
    actions.forEach((action) => {
      const btn = document.createElement("button");
      btn.className = `btn ${action.kind || "secondary"}`;
      btn.textContent = action.label;
      btn.onclick = async () => {
        if (action.onClick) {
          const keep = await action.onClick(backdrop);
          if (keep === false) return;
        }
        close();
      };
      foot.appendChild(btn);
    });
    backdrop.addEventListener("click", (event) => {
      if (event.target === backdrop) close();
    });
    root.appendChild(backdrop);
    return { root: backdrop, close };
  }

  const ROLE_LABEL = {
    ORG_ADMIN: "Администратор компании",
    NETWORK_MANAGER: "Руководитель сети",
    REGIONAL_MANAGER: "Региональный менеджер",
    LOCATION_MANAGER: "Управляющий точкой",
    ANALYST: "Аналитик",
    SUPERADMIN: "Суперадминистратор",
  };

  const STATUS_LABEL = {
    active: "Работает",
    attention: "Нужен анализ",
    offline: "Нет данных",
    connected: "Подключено",
    draft: "Черновик",
    error: "Ошибка",
    disabled: "Отключено",
  };

  const SEVERITY_LABEL = {
    critical: "Критично",
    warning: "Внимание",
    positive: "Рост",
    info: "Инфо",
  };

  function statusDot(status) {
    const cls = status === "active" || status === "connected" ? "active" : status === "offline" || status === "error" ? "offline" : "attention";
    return `<span class="status-dot ${cls}"></span>`;
  }

  function skeleton(rows = 3) {
    return `<div class="empty">Загрузка…</div>`.repeat(rows);
  }

  return { money, num, pct, signed, deltaBadge, esc, toast, modal, ROLE_LABEL, STATUS_LABEL, SEVERITY_LABEL, statusDot, skeleton };
})();
