/* Клиент API: токен, организация, типовые ошибки. */
const API = (() => {
  const state = {
    token: localStorage.getItem("np_token") || "",
    orgId: Number(localStorage.getItem("np_org") || 0) || null,
    user: null,
    org: null,
    role: "",
    orgs: [],
  };

  function headers(extra = {}) {
    const h = { "Content-Type": "application/json", ...extra };
    if (state.token) h.Authorization = `Bearer ${state.token}`;
    if (state.orgId) h["X-Organization-Id"] = String(state.orgId);
    return h;
  }

  async function request(method, path, body) {
    const res = await fetch(path, {
      method,
      headers: headers(),
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (res.status === 401) {
      clear();
      throw new Error("Сессия истекла, войдите заново");
    }
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = text; }
    if (!res.ok) {
      const detail = data && data.detail ? data.detail : `Ошибка ${res.status}`;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function save(payload) {
    state.token = payload.token;
    state.user = payload.user;
    state.orgs = payload.organizations || [];
    state.orgId = payload.active_org_id;
    localStorage.setItem("np_token", state.token);
    if (state.orgId) localStorage.setItem("np_org", String(state.orgId));
  }

  function clear() {
    state.token = "";
    state.user = null;
    state.org = null;
    state.orgId = null;
    localStorage.removeItem("np_token");
    localStorage.removeItem("np_org");
  }

  return {
    state,
    save,
    clear,
    get: (p) => request("GET", p),
    post: (p, b) => request("POST", p, b),
    patch: (p, b) => request("PATCH", p, b),
    del: (p) => request("DELETE", p),
    async login(email, password) {
      const data = await request("POST", "/api/auth/login", { email, password });
      save(data);
      return data;
    },
    async register(payload) {
      const data = await request("POST", "/api/auth/register", payload);
      save(data);
      return data;
    },
    async loadMe() {
      const data = await request("GET", "/api/auth/me");
      state.user = data.user;
      state.org = data.organization;
      state.role = data.role;
      state.orgs = data.organizations || [];
      if (!state.orgId && data.organization) state.orgId = data.organization.id;
      return data;
    },
    async switchOrg(id) {
      const data = await request("POST", `/api/auth/switch/${id}`);
      save(data);
      return data;
    },
    download(path) {
      const url = path + (path.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(state.token);
      window.open(url, "_blank");
    },
  };
})();
