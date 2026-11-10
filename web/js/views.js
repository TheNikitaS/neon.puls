/* Экраны приложения. */
const Views = (() => {
  const { money, num, pct, deltaBadge, esc, toast, modal, ROLE_LABEL, STATUS_LABEL, SEVERITY_LABEL, statusDot } = UI;

  function period(days) {
    const to = new Date();
    to.setDate(to.getDate() - 1);
    const from = new Date(to);
    from.setDate(from.getDate() - (days - 1));
    const iso = (d) => d.toISOString().slice(0, 10);
    return { from: iso(from), to: iso(to) };
  }

  function qs(ctx, extra = {}) {
    const { from, to } = period(ctx.days);
    const params = new URLSearchParams({ date_from: from, date_to: to, ...extra });
    if (ctx.locationId) params.set("location_ids", String(ctx.locationId));
    return params.toString();
  }

  function kpiCard(label, value, delta, spark, color) {
    return `
      <div class="card kpi-card reveal">
        <div class="kpi-label">${esc(label)}</div>
        <div class="kpi-value">${value}</div>
        <div class="kpi-foot">${deltaBadge(delta)}<span>к прошлому периоду</span></div>
        <div class="spark" data-spark="${spark || ""}" data-color="${color || "#35f0d0"}"></div>
      </div>`;
  }

  function paintSparks(root, series) {
    root.querySelectorAll("[data-spark]").forEach((node) => {
      const key = node.dataset.spark;
      if (!key) return;
      const values = series.map((row) => row[key] || 0);
      if (values.length > 1) Charts.sparkline(node, values, node.dataset.color);
    });
  }

  function insightCard(item, withActions = true) {
    const rec = item.recommendation || {};
    const actions = rec.actions || item.actions || [];
    return `
      <div class="insight ${item.severity}">
        <div class="insight-head">
          <span class="pill ${item.severity}">${SEVERITY_LABEL[item.severity] || item.severity}</span>
          <strong>${esc(item.title)}</strong>
        </div>
        <p>${esc(item.summary)}</p>
        ${withActions && actions.length ? `<ul class="actions">${actions.slice(0, 4).map((a) => `<li>${esc(a)}</li>`).join("")}</ul>` : ""}
        <div class="insight-meta">
          <span>Уверенность: <b>${Math.round((item.confidence || 0) * 100)}%</b></span>
          ${item.period_from ? `<span>Период: <b>${item.period_from} — ${item.period_to}</b></span>` : ""}
          ${item.location ? `<span>Точка: <b>${esc(item.location)}</b></span>` : ""}
        </div>
      </div>`;
  }

  /* ---------------- Главная ---------------- */
  async function dashboard(root, ctx) {
    root.innerHTML = UI.skeleton(2);
    const data = await API.get(`/api/analytics/overview?${qs(ctx)}`);
    const cur = data.current;
    const d = data.delta;
    const series = data.series;
    const labels = series.map((row) => row.date.slice(5).replace("-", "."));
    const recs = await API.get("/api/ai/recommendations").catch(() => []);
    const top = data.ranking.slice(0, 6);
    const attention = data.attention_available;

    root.innerHTML = `
      <div class="grid kpi">
        ${kpiCard("Трафик", num(cur.passersby), d.passersby, "passersby", "#35f0d0")}
        ${
          attention
            ? kpiCard("Посмотревшие", num(cur.looked), d.looked, "looked", "#8b7bff")
            : `<div class="card kpi-card reveal">
                <div class="kpi-label">Посмотревшие</div>
                <div class="kpi-value" style="color:var(--dim)">—</div>
                <div class="kpi-foot"><span>нет данных: камера внимания не подключена</span></div>
                <button class="btn small secondary" style="margin-top:10px" id="attention-help">Как включить</button>
              </div>`
        }
        ${kpiCard("Вошедшие", num(cur.entries), d.entries, "entries", "#c8ff4d")}
        ${kpiCard("Купившие (чеки)", num(cur.receipts), d.receipts, "receipts", "#ff4d8d")}
      </div>

      <div class="grid kpi">
        ${kpiCard("Выручка", money(cur.revenue), d.revenue, "revenue", "#c8ff4d")}
        ${kpiCard("Средний чек", money(cur.avg_check), d.avg_check, "avg_check", "#ffb84d")}
        ${kpiCard("Конверсия входа", pct(cur.entry_conversion), d.entry_conversion, "entry_conversion", "#35f0d0")}
        ${kpiCard("Конверсия в чек", pct(cur.purchase_conversion), d.purchase_conversion, "purchase_conversion", "#8b7bff")}
      </div>

      <div class="grid two">
        <div class="card reveal">
          <div class="card-head">
            <h3>Выручка и чеки</h3>
            <span class="hint">${data.period.from} — ${data.period.to}</span>
          </div>
          <div id="chart-revenue"></div>
          <div class="legend" style="margin-top:10px">
            <span><i style="background:#c8ff4d"></i>Выручка, ₽</span>
            <span><i style="background:#8b7bff"></i>Чеки</span>
          </div>
        </div>
        <div class="card reveal">
          <div class="card-head"><h3>Воронка периода</h3><span class="hint">трафик → покупка</span></div>
          <div id="funnel" style="display:flex;flex-direction:column;gap:10px"></div>
        </div>
      </div>

      <div class="grid two">
        <div class="card reveal">
          <div class="card-head"><h3>Трафик и входы</h3><span class="hint">конверсия входа ${pct(cur.entry_conversion)}</span></div>
          <div id="chart-traffic"></div>
          <div class="legend" style="margin-top:10px">
            <span><i style="background:#35f0d0"></i>Проходящий трафик</span>
            <span><i style="background:#ffb84d"></i>Входы</span>
          </div>
        </div>
        <div class="card reveal">
          <div class="card-head">
            <h3>Рейтинг точек</h3>
            <button class="btn small secondary" id="manual-entry">+ Внести вручную</button>
          </div>
          <table class="table">
            <thead><tr><th>#</th><th>Точка</th><th class="num">Выручка</th><th class="num">Конв.</th></tr></thead>
            <tbody>
              ${top
                .map(
                  (row) => `<tr>
                    <td><span class="rank ${row.rank === 1 ? "top" : ""}">${row.rank}</span></td>
                    <td class="name">${esc(row.name)}<div style="color:var(--dim);font-size:10.5px">${esc(row.city)}</div></td>
                    <td class="num">${money(row.revenue)}</td>
                    <td class="num">${pct(row.entry_conversion)}</td>
                  </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>

      <div class="card reveal">
        <div class="card-head">
          <h3>AI-рекомендации</h3>
          <a class="hint" href="#/ai">Все рекомендации →</a>
        </div>
        <div class="grid" style="gap:10px">
          ${
            recs.length
              ? recs.slice(0, 3).map((r) => `
                <div class="insight ${r.status === "done" ? "positive" : "info"}">
                  <div class="insight-head">
                    <span class="pill info">${esc(r.location)}</span>
                    <strong>${esc(r.title)}</strong>
                  </div>
                  <p>${esc(r.rationale)}</p>
                  <div class="insight-meta"><span>Ожидаемый эффект: <b>${esc(r.expected_effect)}</b></span></div>
                </div>`).join("")
              : `<div class="empty">Рекомендаций пока нет — запустите AI-анализ точки.</div>`
          }
        </div>
      </div>`;

    paintSparks(root, series);
    Charts.line(root.querySelector("#chart-revenue"), {
      labels,
      series: [
        { name: "Выручка", values: series.map((r) => r.revenue), color: "#c8ff4d" },
        { name: "Чеки", values: series.map((r) => r.receipts), color: "#8b7bff" },
      ],
      height: 230,
    });
    Charts.line(root.querySelector("#chart-traffic"), {
      labels,
      series: [
        { name: "Трафик", values: series.map((r) => r.passersby), color: "#35f0d0" },
        { name: "Входы", values: series.map((r) => r.entries), color: "#ffb84d" },
      ],
      height: 230,
    });

    const funnel = root.querySelector("#funnel");
    const steps = attention
      ? [
          ["Прошли мимо", cur.passersby, "#35f0d0"],
          ["Посмотрели", cur.looked, "#8b7bff"],
          ["Вошли", cur.entries, "#c8ff4d"],
          ["Купили", cur.receipts, "#ff4d8d"],
        ]
      : [
          ["Прошли мимо", cur.passersby, "#35f0d0"],
          ["Вошли", cur.entries, "#c8ff4d"],
          ["Купили", cur.receipts, "#ff4d8d"],
        ];
    const maxStep = Math.max(...steps.map((s) => s[1]), 1);
    funnel.innerHTML = steps
      .map(
        ([label, value, color]) => `
        <div>
          <div style="display:flex;justify-content:space-between;font-size:11.5px;color:var(--muted);margin-bottom:4px">
            <span>${label}</span><b style="font-family:var(--font-mono);color:var(--text)">${num(value)}</b>
          </div>
          <div style="height:7px;border-radius:4px;background:rgba(255,255,255,.05);overflow:hidden">
            <div style="height:100%;width:${Math.max((value / maxStep) * 100, 1.5)}%;background:${color};border-radius:4px;box-shadow:0 0 12px ${color}55"></div>
          </div>
        </div>`
      )
      .join("");

    const help = root.querySelector("#attention-help");
    if (help) {
      help.onclick = () =>
        UI.modal({
          title: "Как включить показатель «Посмотревшие»",
          subtitle: "внимание к вывеске и витрине",
          body: `
            <p style="color:var(--muted);font-size:12.5px;line-height:1.65;margin:0 0 10px">
              Показатель считается по камере, направленной на входную зону и витрину.
              Нужны ракурс с основного направления движения и зона наблюдения «витрина».
            </p>
            <ul class="actions">
              <li>Подключите камеру внимания в разделе «Интеграции».</li>
              <li>В карточке точки добавьте камеру с назначением «витрина».</li>
              <li>Включите учёт просмотров в настройках точки.</li>
            </ul>
            <div class="demo-hint">
              Пока камера не подключена, платформа показывает «—» и не подставляет
              оценочные значения: лучше честный пропуск, чем выдуманное число.
            </div>`,
          actions: [{ label: "Понятно" }],
        });
    }

    const manualBtn = root.querySelector("#manual-entry");
    if (manualBtn && Views.manualModal) manualBtn.onclick = () => Views.manualModal(ctx);
  }

  /* ---------------- Аналитика ---------------- */
  async function analytics(root, ctx) {
    root.innerHTML = UI.skeleton(2);
    const [overview, hourly, weekday] = await Promise.all([
      API.get(`/api/analytics/overview?${qs(ctx)}`),
      API.get(`/api/analytics/hourly?${qs(ctx)}`),
      API.get(`/api/analytics/weekday?${qs(ctx)}`),
    ]);
    const series = overview.series;
    const labels = series.map((r) => r.date.slice(5).replace("-", "."));
    const cur = overview.current;

    root.innerHTML = `
      <div class="grid kpi">
        ${kpiCard("Внимание к витрине", pct(cur.attention_rate), overview.delta.attention_rate, "attention_rate", "#8b7bff")}
        ${kpiCard("Конверсия входа", pct(cur.entry_conversion), overview.delta.entry_conversion, "entry_conversion", "#35f0d0")}
        ${kpiCard("Конверсия в чек", pct(cur.purchase_conversion), overview.delta.purchase_conversion, "purchase_conversion", "#c8ff4d")}
        ${kpiCard("Выручка на посетителя", money(cur.revenue_per_visitor), overview.delta.revenue_per_visitor, "revenue", "#ffb84d")}
      </div>

      <div class="card reveal">
        <div class="card-head"><h3>Воронка по дням</h3><span class="hint">трафик, внимание, входы, чеки</span></div>
        <div id="chart-funnel"></div>
        <div class="legend" style="margin-top:10px">
          <span><i style="background:#35f0d0"></i>Трафик</span>
          <span><i style="background:#8b7bff"></i>Внимание</span>
          <span><i style="background:#ffb84d"></i>Входы</span>
          <span><i style="background:#c8ff4d"></i>Чеки</span>
        </div>
      </div>

      <div class="grid half">
        <div class="card reveal">
          <div class="card-head"><h3>Профиль по часам</h3><span class="hint">входы</span></div>
          <div id="chart-hourly"></div>
        </div>
        <div class="card reveal">
          <div class="card-head"><h3>Профиль по дням недели</h3><span class="hint">средние значения</span></div>
          <div id="chart-weekday"></div>
        </div>
      </div>

      <div class="grid half">
        <div class="card reveal">
          <div class="card-head"><h3>Выручка по дням</h3><span class="hint">${overview.period.from} — ${overview.period.to}</span></div>
          <div id="chart-rev"></div>
        </div>
        <div class="card reveal">
          <div class="card-head"><h3>Конверсии</h3><span class="hint">доля, %</span></div>
          <div id="chart-conv"></div>
        </div>
      </div>`;

    paintSparks(root, series);
    Charts.line(root.querySelector("#chart-funnel"), {
      labels,
      series: [
        { name: "Трафик", values: series.map((r) => r.passersby), color: "#35f0d0" },
        { name: "Внимание", values: series.map((r) => r.looked), color: "#8b7bff" },
        { name: "Входы", values: series.map((r) => r.entries), color: "#ffb84d" },
        { name: "Чеки", values: series.map((r) => r.receipts), color: "#c8ff4d" },
      ],
      height: 250,
    });
    Charts.bars(root.querySelector("#chart-hourly"), {
      labels: hourly.map((h) => String(h.hour).padStart(2, "0")),
      values: hourly.map((h) => h.entries),
      height: 210,
    });
    Charts.bars(root.querySelector("#chart-weekday"), {
      labels: weekday.map((w) => w.weekday),
      values: weekday.map((w) => w.entries),
      height: 210,
      color: "#8b7bff",
    });
    Charts.line(root.querySelector("#chart-rev"), {
      labels,
      series: [{ name: "Выручка", values: series.map((r) => r.revenue), color: "#c8ff4d" }],
      height: 210,
    });
    Charts.line(root.querySelector("#chart-conv"), {
      labels,
      series: [
        { name: "Вход", values: series.map((r) => r.entry_conversion * 100), color: "#35f0d0" },
        { name: "Чек", values: series.map((r) => r.purchase_conversion * 100), color: "#ff4d8d" },
      ],
      height: 210,
      yFormat: (v) => `${Math.round(v)}%`,
    });
  }

  /* ---------------- Точки ---------------- */
  async function locations(root, ctx) {
    root.innerHTML = UI.skeleton(2);
    const [list, ranking] = await Promise.all([
      API.get("/api/locations"),
      API.get(`/api/analytics/ranking?${qs(ctx)}`),
    ]);
    const byId = Object.fromEntries(ranking.map((r) => [r.location_id, r]));
    const cities = {};
    list.forEach((loc) => {
      (cities[loc.city || "Без города"] ||= []).push(loc);
    });

    root.innerHTML = `
      <div class="card reveal" style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
        <div>
          <div class="kpi-label">Торговые точки</div>
          <div style="font-family:var(--font-display);font-size:24px;margin-top:4px">${list.length} объектов · ${Object.keys(cities).length} города</div>
        </div>
        <button class="btn" id="add-location">+ Добавить точку</button>
      </div>
      ${Object.entries(cities)
        .map(
          ([city, items]) => `
        <div class="card reveal">
          <div class="card-head"><h3>${esc(city)}</h3><span class="hint">${items.length} точек</span></div>
          <div class="loc-grid">
            ${items
              .map((loc) => {
                const r = byId[loc.id] || {};
                const status = loc.status === "active" ? (r.entry_conversion && r.entry_conversion < 0.06 ? "attention" : "active") : "offline";
                return `
                <div class="loc-card" data-loc="${loc.id}">
                  <div class="loc-top">
                    <div>
                      <strong>${esc(loc.name)}</strong>
                      <small>${esc(loc.address)}</small>
                    </div>
                    ${statusDot(status)}
                  </div>
                  <div class="loc-metrics">
                    <div>Выручка<b>${money(r.revenue || 0)}</b></div>
                    <div>Входы<b>${num(r.entries || 0)}</b></div>
                    <div>Конверсия<b>${pct(r.entry_conversion || 0)}</b></div>
                  </div>
                  <div style="display:flex;justify-content:space-between;font-size:10.5px;color:var(--dim)">
                    <span>${loc.cameras} камер</span>
                    <span>${STATUS_LABEL[status] || status}</span>
                  </div>
                </div>`;
              })
              .join("")}
          </div>
        </div>`
        )
        .join("")}`;

    root.querySelectorAll("[data-loc]").forEach((node) => {
      node.onclick = () => ctx.navigate(`#/location/${node.dataset.loc}`);
    });
    root.querySelector("#add-location").onclick = () => locationModal(ctx);
  }

  function locationModal(ctx) {
    modal({
      title: "Новая торговая точка",
      subtitle: "Точка появится в иерархии сети и станет доступна для подключения камер",
      body: `
        <div class="field"><label>Название</label><input class="input" id="loc-name" placeholder="Например, Невский проспект" /></div>
        <div class="form-row">
          <div class="field"><label>Город</label><input class="input" id="loc-city" placeholder="Санкт-Петербург" /></div>
          <div class="field"><label>Площадь, м²</label><input class="input" id="loc-area" type="number" placeholder="80" /></div>
        </div>
        <div class="field"><label>Адрес</label><input class="input" id="loc-address" placeholder="Невский пр., 88" /></div>`,
      actions: [
        { label: "Отмена" },
        {
          label: "Создать",
          kind: "",
          onClick: async (root) => {
            const name = root.querySelector("#loc-name").value.trim();
            if (!name) {
              toast("Укажите название точки", "error");
              return false;
            }
            await API.post("/api/locations", {
              name,
              city: root.querySelector("#loc-city").value.trim(),
              address: root.querySelector("#loc-address").value.trim(),
              area_m2: Number(root.querySelector("#loc-area").value) || null,
            });
            toast("Точка создана", "ok");
            ctx.reload();
          },
        },
      ],
    });
  }

  /* ---------------- Карточка точки ---------------- */
  async function locationDetail(root, ctx, id) {
    root.innerHTML = UI.skeleton(2);
    const loc = await API.get(`/api/locations/${id}`);
    const overview = await API.get(`/api/analytics/overview?${qs({ ...ctx, locationId: id })}`);
    const series = overview.series;
    const labels = series.map((r) => r.date.slice(5).replace("-", "."));
    const cur = overview.current;
    const d = overview.delta;

    root.innerHTML = `
      <div class="card reveal" style="display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;align-items:flex-start">
        <div>
          <div class="kpi-label">${esc(loc.city)} · ${esc(loc.address)}</div>
          <div style="font-family:var(--font-display);font-size:26px;margin:6px 0 4px">${esc(loc.name)}</div>
          <div style="display:flex;gap:14px;font-size:11.5px;color:var(--dim);flex-wrap:wrap">
            <span>${loc.cameras.length} камер</span>
            <span>${loc.area_m2 ? loc.area_m2 + " м²" : "площадь не указана"}</span>
            <span>${STATUS_LABEL[loc.status] || loc.status}</span>
          </div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn" id="run-ai">✦ AI-разбор точки</button>
          <button class="btn secondary" id="add-change">Зафиксировать изменение</button>
        </div>
      </div>

      <div class="grid kpi">
        ${kpiCard("Выручка", money(cur.revenue), d.revenue, "revenue", "#c8ff4d")}
        ${kpiCard("Трафик", num(cur.passersby), d.passersby, "passersby", "#35f0d0")}
        ${kpiCard("Входы", num(cur.entries), d.entries, "entries", "#8b7bff")}
        ${kpiCard("Конверсия входа", pct(cur.entry_conversion), d.entry_conversion, "entry_conversion", "#ffb84d")}
        ${kpiCard("Средний чек", money(cur.avg_check), d.avg_check, "avg_check", "#ff4d8d")}
      </div>

      <div class="grid two">
        <div class="card reveal">
          <div class="card-head"><h3>Динамика точки</h3><span class="hint">${overview.period.from} — ${overview.period.to}</span></div>
          <div id="chart-loc"></div>
          <div class="legend" style="margin-top:10px">
            <span><i style="background:#35f0d0"></i>Трафик</span>
            <span><i style="background:#ffb84d"></i>Входы</span>
            <span><i style="background:#c8ff4d"></i>Выручка</span>
          </div>
        </div>
        <div class="card reveal">
          <div class="card-head"><h3>Камеры и зоны</h3><span class="hint">видеоаналитика</span></div>
          ${
            loc.cameras.length
              ? loc.cameras
                  .map(
                    (cam) => `
              <div style="display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid rgba(255,255,255,.05)">
                <div>
                  <div style="font-size:12.5px">${esc(cam.name)}</div>
                  <div style="font-size:10.5px;color:var(--dim)">${esc(cam.purpose)} · ${esc(cam.provider)} · ${cam.zones.length} зон</div>
                </div>
                ${statusDot(cam.status === "online" ? "active" : "offline")}
              </div>`
                  )
                  .join("")
              : `<div class="empty">Камеры не подключены</div>`
          }
        </div>
      </div>

      <div class="grid half">
        <div class="card reveal">
          <div class="card-head"><h3>История изменений</h3><span class="hint">для замера «до/после»</span></div>
          <div id="changes-list">
            ${
              loc.changes.length
                ? loc.changes
                    .map(
                      (ch) => `
                <div style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,.05)">
                  <div style="display:flex;justify-content:space-between;gap:10px">
                    <strong style="font-size:12.5px">${esc(ch.title)}</strong>
                    <span style="font-size:10.5px;color:var(--dim);font-family:var(--font-mono)">${ch.applied_at.slice(0, 10)}</span>
                  </div>
                  <div style="font-size:11.5px;color:var(--muted);margin-top:3px">${esc(ch.description)}</div>
                  <button class="btn small secondary" style="margin-top:7px" data-ba="${ch.id}">Сравнить до / после</button>
                </div>`
                    )
                    .join("")
                : `<div class="empty">Изменения не зафиксированы</div>`
            }
          </div>
        </div>
        <div class="card reveal">
          <div class="card-head"><h3>Результат «до / после»</h3><span class="hint">выберите изменение</span></div>
          <div id="ba-result"><div class="empty">Нажмите «Сравнить до / после» у любого изменения</div></div>
        </div>
      </div>

      <div class="card reveal">
        <div class="card-head"><h3>AI-выводы по точке</h3><span class="hint">история анализа</span></div>
        <div id="loc-insights" class="grid" style="gap:10px"><div class="empty">Загрузка…</div></div>
      </div>

      <div id="loc-extras"></div>`;

    paintSparks(root, series);
    Charts.line(root.querySelector("#chart-loc"), {
      labels,
      series: [
        { name: "Трафик", values: series.map((r) => r.passersby), color: "#35f0d0" },
        { name: "Входы", values: series.map((r) => r.entries), color: "#ffb84d" },
        { name: "Выручка", values: series.map((r) => r.revenue), color: "#c8ff4d" },
      ],
      height: 240,
    });

    root.querySelector("#run-ai").onclick = async (event) => {
      event.target.disabled = true;
      event.target.textContent = "Анализ…";
      try {
        const data = await API.post(`/api/ai/analyze/${id}`);
        renderInsights(root.querySelector("#loc-insights"), data.insights);
        toast("AI-анализ готов", "ok");
      } catch (err) {
        toast(err.message, "error");
      } finally {
        event.target.disabled = false;
        event.target.textContent = "✦ AI-разбор точки";
      }
    };

    root.querySelector("#add-change").onclick = () => changeModal(ctx, id);
    root.querySelectorAll("[data-ba]").forEach((btn) => {
      btn.onclick = async () => {
        const data = await API.get(`/api/analytics/before-after?location_id=${id}&change_id=${btn.dataset.ba}`);
        renderBeforeAfter(root.querySelector("#ba-result"), data);
      };
    });

    const insights = await API.get(`/api/ai/insights?location_id=${id}&limit=6`).catch(() => []);
    renderInsights(root.querySelector("#loc-insights"), insights);
    if (Views.locationExtras) await Views.locationExtras(root, ctx, id);
  }

  function renderInsights(node, items) {
    if (!items || !items.length) {
      node.innerHTML = `<div class="empty">Анализ ещё не запускался. Нажмите «AI-разбор точки».</div>`;
      return;
    }
    node.innerHTML = items.map((item) => insightCard(item)).join("");
  }

  function renderBeforeAfter(node, data) {
    const rows = [
      ["Трафик", "passersby", num],
      ["Входы", "entries", num],
      ["Чеки", "receipts", num],
      ["Выручка", "revenue", money],
      ["Средний чек", "avg_check", money],
      ["Конверсия входа", "entry_conversion", pct],
      ["Конверсия в чек", "purchase_conversion", pct],
    ];
    node.innerHTML = `
      <div style="font-size:11px;color:var(--dim);margin-bottom:8px">
        База: ${data.baseline.from} — ${data.baseline.to} · После: ${data.result.from} — ${data.result.to}
      </div>
      <table class="table">
        <thead><tr><th>Показатель</th><th class="num">До</th><th class="num">После</th><th class="num">Δ</th></tr></thead>
        <tbody>
          ${rows
            .map(
              ([label, key, fmt]) => `
            <tr>
              <td>${label}</td>
              <td class="num">${fmt(data.baseline.metrics[key])}</td>
              <td class="num">${fmt(data.result.metrics[key])}</td>
              <td class="num">${deltaBadge(data.delta[key])}</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
  }

  function changeModal(ctx, locationId) {
    modal({
      title: "Зафиксировать изменение",
      subtitle: "Система сравнит показатели до и после этой даты",
      body: `
        <div class="field"><label>Что изменилось</label>
          <select class="select" id="ch-kind">
            <option value="signage">Вывеска</option>
            <option value="showcase">Витрина / оформление</option>
            <option value="promo">Акция</option>
            <option value="schedule">Режим работы</option>
            <option value="prices">Цены</option>
            <option value="other">Другое</option>
          </select>
        </div>
        <div class="field"><label>Название</label><input class="input" id="ch-title" placeholder="Например, новая вывеска" /></div>
        <div class="field"><label>Описание</label><textarea class="textarea" id="ch-desc"></textarea></div>
        <div class="field"><label>Дата</label><input class="input" id="ch-date" type="date" value="${new Date().toISOString().slice(0, 10)}" /></div>`,
      actions: [
        { label: "Отмена" },
        {
          label: "Сохранить",
          kind: "",
          onClick: async (root) => {
            const title = root.querySelector("#ch-title").value.trim();
            if (!title) {
              toast("Укажите название изменения", "error");
              return false;
            }
            await API.post(`/api/locations/${locationId}/changes`, {
              location_id: locationId,
              kind: root.querySelector("#ch-kind").value,
              title,
              description: root.querySelector("#ch-desc").value.trim(),
              applied_at: root.querySelector("#ch-date").value + "T00:00:00",
            });
            toast("Изменение зафиксировано", "ok");
            ctx.reload();
          },
        },
      ],
    });
  }

  return { dashboard, analytics, locations, locationDetail, renderInsights, renderBeforeAfter, period, qs, kpiCard, insightCard, paintSparks, changeModal };
})();
