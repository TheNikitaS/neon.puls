/* Точка входа SPA: авторизация, маршрутизация, состояние. */
(() => {
  const state = { days: 28, locationId: null, locations: [], route: "dashboard" };
  const appEl = document.getElementById("app");
  const authEl = document.getElementById("auth");
  const viewEl = document.getElementById("view");

  const TITLES = {
    dashboard: ["Главная", "Сводка по сети"],
    analytics: ["Аналитика", "Трафик, внимание, посещаемость и продажи"],
    locations: ["Торговые точки", "Иерархия объектов сети"],
    location: ["Торговая точка", "Показатели, камеры и изменения"],
    ai: ["AI-аналитик", "Выводы, рекомендации и история"],
    compare: ["Сравнение", "Эффективность точек сети"],
    reports: ["Отчёты", "Выгрузка результатов"],
    integrations: ["Интеграции", "Integration Hub: источники данных"],
    notifications: ["Уведомления", "Аномалии и состояние интеграций"],
    settings: ["Настройки", "Пользователи, роли и доступы"],
    admin: ["Платформа", "Административная панель Неон.Пульс"],
  };

  function ctx() {
    return {
      days: state.days,
      locationId: state.locationId,
      locations: state.locations,
      navigate: (hash) => {
        location.hash = hash;
      },
      reload: () => render(),
    };
  }

  /* ---------- авторизация ---------- */
  function renderAuth(mode = "login") {
    appEl.hidden = true;
    authEl.hidden = false;
    authEl.innerHTML = `
      <div class="auth-hero">
        <div>
          <div class="brand" style="margin-bottom:44px">
            <div class="brand-mark">
              <svg viewBox="0 0 32 32" fill="none">
                <path d="M3 22 L9 10 L15 22 L21 6 L29 22" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <div class="brand-text"><strong>НЕОН<span>.</span>ПУЛЬС</strong><small>revenue intelligence</small></div>
          </div>
          <h1>Видеть,<br>что происходит<br><em>в каждой точке</em></h1>
          <p>
            Платформа объединяет видеоаналитику, посещаемость, внимание к рекламе,
            продажи и финансовые показатели. Показывает, что происходит в каждой
            торговой точке, почему это происходит и какие действия помогут увеличить результат.
          </p>
          <div class="auth-chain">
            <span><b>01</b> Трафик</span>
            <span><b>02</b> Внимание</span>
            <span><b>03</b> Посещение</span>
            <span><b>04</b> Покупка</span>
            <span><b>05</b> Выручка</span>
            <span><b>06</b> AI</span>
          </div>
        </div>
        <div style="font-size:11px;color:var(--dim);letter-spacing:.08em;text-transform:uppercase">
          B2B SaaS · AI Analytics · Computer Vision
        </div>
      </div>
      <div class="auth-form-wrap">
        <div class="auth-form">
          <h2>${mode === "login" ? "Вход в платформу" : "Создать компанию"}</h2>
          <div class="sub">${mode === "login" ? "Личный кабинет компании" : "Регистрация организации и администратора"}</div>
          <div class="auth-tabs">
            <button data-mode="login" class="${mode === "login" ? "active" : ""}">Вход</button>
            <button data-mode="register" class="${mode === "register" ? "active" : ""}">Регистрация</button>
          </div>
          <form id="auth-form">
            ${
              mode === "register"
                ? `<div class="field"><label>Компания</label><input class="input" name="company_name" placeholder="Сеть кофеен «Неон»" required /></div>
                   <div class="field"><label>Ваше имя</label><input class="input" name="full_name" placeholder="Имя и фамилия" required /></div>`
                : ""
            }
            <div class="field"><label>Email</label><input class="input" name="email" type="email" placeholder="you@company.ru" required /></div>
            <div class="field"><label>Пароль</label><input class="input" name="password" type="password" placeholder="Минимум 8 символов" required /></div>
            <button class="btn" type="submit" style="width:100%;margin-top:6px">
              ${mode === "login" ? "Войти" : "Создать компанию"}
            </button>
          </form>
          ${
            mode === "login"
              ? `<div class="demo-hint">
                  Демо-доступ: <b>demo@neonpulse.ru</b> / <b>Demo2026!</b><br>
                  Администратор платформы: <b>admin@neonpulse.ru</b> / <b>NeonPulse2026!</b>
                </div>`
              : ""
          }
        </div>
      </div>`;

    authEl.querySelectorAll("[data-mode]").forEach((btn) => {
      btn.onclick = () => renderAuth(btn.dataset.mode);
    });
    authEl.querySelector("#auth-form").onsubmit = async (event) => {
      event.preventDefault();
      const form = new FormData(event.target);
      const submit = event.target.querySelector("button[type=submit]");
      submit.disabled = true;
      try {
        if (mode === "login") {
          await API.login(form.get("email"), form.get("password"));
        } else {
          await API.register({
            email: form.get("email"),
            password: form.get("password"),
            full_name: form.get("full_name"),
            company_name: form.get("company_name"),
            industry: "retail",
          });
        }
        await boot();
      } catch (err) {
        UI.toast(err.message, "error");
      } finally {
        submit.disabled = false;
      }
    };
  }

  /* ---------- каркас ---------- */
  async function boot() {
    if (!API.state.token) {
      renderAuth("login");
      return;
    }
    try {
      await API.loadMe();
    } catch {
      renderAuth("login");
      return;
    }
    authEl.hidden = true;
    appEl.hidden = false;
    document.getElementById("org-name").textContent = API.state.org?.name || "—";
    document.getElementById("org-role").textContent = UI.ROLE_LABEL[API.state.role] || API.state.role;
    document.getElementById("nav-admin").hidden = !API.state.user?.is_superadmin;
    await loadLocations();
    await refreshBadge();
    if (!location.hash) location.hash = "#/dashboard";
    render();
  }

  async function loadLocations() {
    try {
      state.locations = await API.get("/api/locations");
    } catch {
      state.locations = [];
    }
    const select = document.getElementById("location-filter");
    select.innerHTML =
      `<option value="">Вся сеть</option>` +
      state.locations.map((loc) => `<option value="${loc.id}">${UI.esc(loc.name)}</option>`).join("");
    select.value = state.locationId ? String(state.locationId) : "";
  }

  async function refreshBadge() {
    try {
      const items = await API.get("/api/notifications?unread_only=true");
      const badge = document.getElementById("nav-badge");
      badge.hidden = items.length === 0;
      badge.textContent = items.length > 99 ? "99+" : String(items.length);
    } catch {
      /* тихо */
    }
  }

  function setActiveNav(route) {
    document.querySelectorAll("#nav a").forEach((link) => {
      link.classList.toggle("active", link.dataset.route === route);
    });
  }

  function setTitle(route) {
    const [title, sub] = TITLES[route] || TITLES.dashboard;
    document.getElementById("page-title").textContent = title;
    document.getElementById("page-sub").textContent = sub;
  }

  async function render() {
    const hash = location.hash.replace(/^#\/?/, "") || "dashboard";
    const [route, param] = hash.split("/");
    state.route = route;
    setActiveNav(route);
    setTitle(route);
    viewEl.innerHTML = UI.skeleton(2);
    try {
      if (route === "location" && param) {
        await Views.locationDetail(viewEl, ctx(), Number(param));
      } else if (Views[route]) {
        await Views[route](viewEl, ctx());
      } else {
        await Views.dashboard(viewEl, ctx());
      }
    } catch (err) {
      viewEl.innerHTML = `<div class="card"><div class="empty">Не удалось загрузить раздел: ${UI.esc(err.message)}</div></div>`;
    }
    refreshBadge();
  }

  /* ---------- события ---------- */
  window.addEventListener("hashchange", render);

  document.getElementById("period-switch").addEventListener("click", (event) => {
    const btn = event.target.closest("button[data-days]");
    if (!btn) return;
    state.days = Number(btn.dataset.days);
    document.querySelectorAll("#period-switch button").forEach((b) => b.classList.toggle("active", b === btn));
    render();
  });

  document.getElementById("location-filter").addEventListener("change", (event) => {
    state.locationId = event.target.value ? Number(event.target.value) : null;
    render();
  });

  document.getElementById("refresh").addEventListener("click", () => {
    loadLocations().then(render);
  });

  document.getElementById("logout").addEventListener("click", () => {
    API.clear();
    location.hash = "";
    renderAuth("login");
  });

  document.getElementById("org-chip").addEventListener("click", async () => {
    const orgs = API.state.orgs || [];
    if (orgs.length < 2) return;
    UI.modal({
      title: "Переключить организацию",
      subtitle: "Доступные вам компании",
      body: orgs
        .map(
          (org) => `<button class="btn secondary" style="width:100%;margin-bottom:8px;text-align:left" data-org="${org.id}">
            ${UI.esc(org.name)} · ${UI.ROLE_LABEL[org.role] || org.role}
          </button>`
        )
        .join(""),
      actions: [{ label: "Закрыть" }],
    });
    document.querySelectorAll("[data-org]").forEach((btn) => {
      btn.onclick = async () => {
        await API.switchOrg(Number(btn.dataset.org));
        document.querySelector(".modal-backdrop")?.remove();
        await boot();
      };
    });
  });

  boot();
})();
