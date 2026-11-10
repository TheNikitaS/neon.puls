/* Дополнительные экраны: сравнение, AI, отчёты, интеграции, уведомления, настройки, админ. */
Object.assign(
  Views,
  (() => {
    const { money, num, pct, deltaBadge, esc, toast, modal, ROLE_LABEL, STATUS_LABEL, SEVERITY_LABEL, statusDot } = UI;
    const { period, qs, kpiCard, insightCard } = Views;

    /* ---------------- Сравнение ---------------- */
    async function compare(root, ctx) {
      root.innerHTML = UI.skeleton(2);
      const [list, ranking] = await Promise.all([
        API.get("/api/locations"),
        API.get(`/api/analytics/ranking?${qs(ctx)}`),
      ]);
      const selected = new Set(ranking.slice(0, 3).map((r) => r.location_id));

      root.innerHTML = `
        <div class="card reveal">
          <div class="card-head"><h3>Выберите точки для сравнения</h3><span class="hint">минимум две</span></div>
          <div style="display:flex;flex-wrap:wrap;gap:8px" id="cmp-picker">
            ${list
              .map(
                (loc) => `<button class="btn small secondary" data-pick="${loc.id}"
                  style="${selected.has(loc.id) ? "border-color:rgba(53,240,208,.5);color:var(--cyan)" : ""}">${esc(loc.name)}</button>`
              )
              .join("")}
          </div>
        </div>
        <div class="card reveal">
          <div class="card-head"><h3>Сравнение показателей</h3><span class="hint">за период</span></div>
          <div id="cmp-table"></div>
        </div>
        <div class="grid half">
          <div class="card reveal">
            <div class="card-head"><h3>Выручка</h3><span class="hint">по точкам</span></div>
            <div id="cmp-rev"></div>
          </div>
          <div class="card reveal">
            <div class="card-head"><h3>Конверсия входа</h3><span class="hint">доля, %</span></div>
            <div id="cmp-conv"></div>
          </div>
        </div>`;

      const draw = () => {
        const rows = ranking.filter((r) => selected.has(r.location_id));
        const table = root.querySelector("#cmp-table");
        if (rows.length < 2) {
          table.innerHTML = `<div class="empty">Выберите минимум две точки</div>`;
          root.querySelector("#cmp-rev").innerHTML = "";
          root.querySelector("#cmp-conv").innerHTML = "";
          return;
        }
        table.innerHTML = `
          <table class="table">
            <thead><tr><th>Точка</th><th class="num">Трафик</th><th class="num">Входы</th><th class="num">Чеки</th><th class="num">Выручка</th><th class="num">Ср. чек</th><th class="num">Конв. входа</th><th class="num">Конв. в чек</th></tr></thead>
            <tbody>
              ${rows
                .map(
                  (r) => `<tr>
                    <td class="name">${esc(r.name)}<div style="color:var(--dim);font-size:10.5px">${esc(r.city)}</div></td>
                    <td class="num">${num(r.passersby)}</td>
                    <td class="num">${num(r.entries)}</td>
                    <td class="num">${num(r.receipts)}</td>
                    <td class="num">${money(r.revenue)}</td>
                    <td class="num">${money(r.avg_check)}</td>
                    <td class="num">${pct(r.entry_conversion)}</td>
                    <td class="num">${pct(r.purchase_conversion)}</td>
                  </tr>`
                )
                .join("")}
            </tbody>
          </table>`;
        Charts.bars(root.querySelector("#cmp-rev"), {
          labels: rows.map((r) => r.name.split(" ")[0]),
          values: rows.map((r) => r.revenue),
          height: 210,
          color: "#c8ff4d",
        });
        Charts.bars(root.querySelector("#cmp-conv"), {
          labels: rows.map((r) => r.name.split(" ")[0]),
          values: rows.map((r) => r.entry_conversion * 100),
          height: 210,
          color: "#35f0d0",
          yFormat: (v) => `${Math.round(v)}%`,
        });
      };

      root.querySelectorAll("[data-pick]").forEach((btn) => {
        btn.onclick = () => {
          const id = Number(btn.dataset.pick);
          if (selected.has(id)) selected.delete(id);
          else selected.add(id);
          btn.style.borderColor = selected.has(id) ? "rgba(53,240,208,.5)" : "";
          btn.style.color = selected.has(id) ? "var(--cyan)" : "";
          draw();
        };
      });
      draw();
    }

    /* ---------------- AI-аналитик ---------------- */
    async function ai(root, ctx) {
      root.innerHTML = UI.skeleton(2);
      const [recs, insights] = await Promise.all([
        API.get("/api/ai/recommendations").catch(() => []),
        API.get("/api/ai/insights?limit=12").catch(() => []),
      ]);

      root.innerHTML = `
        <div class="grid two">
          <div class="card reveal">
            <div class="card-head"><h3>Спросить AI-аналитика</h3><span class="hint">ответ по данным компании</span></div>
            <div class="chat">
              <div class="chat-log" id="chat-log">
                <div class="msg ai">Здравствуйте. Я аналитик Неон.Пульс. Спросите про трафик, конверсию, выручку, средний чек или сравнение точек. Отвечаю по данным вашей сети и показываю источники.</div>
              </div>
              <div class="chat-input">
                <input class="input" id="chat-q" placeholder="Например: почему упала выручка на Невском?" />
                <button class="btn" id="chat-send">Спросить</button>
              </div>
            </div>
          </div>
          <div class="card reveal">
            <div class="card-head"><h3>Быстрые действия</h3><span class="hint">анализ по кнопке</span></div>
            <div style="display:flex;flex-direction:column;gap:9px">
              <button class="btn secondary" id="net-analyze">Проанализировать сеть</button>
              <button class="btn secondary" id="scan-anomalies">Проверить аномалии</button>
              <div class="demo-hint">
                AI не выдаёт гипотезу за доказанную причину: у каждого вывода есть уверенность,
                источники данных и ограничения измерений.
              </div>
            </div>
          </div>
        </div>

        <div class="card reveal">
          <div class="card-head"><h3>Рекомендации</h3><span class="hint">${recs.length} в истории</span></div>
          <div class="grid" style="gap:10px">
            ${
              recs.length
                ? recs
                    .map(
                      (r) => `
                <div class="insight ${r.status === "done" ? "positive" : "info"}">
                  <div class="insight-head">
                    <span class="pill info">${esc(r.location)}</span>
                    <strong>${esc(r.title)}</strong>
                    <span class="pill" style="margin-left:auto">${esc(r.status)}</span>
                  </div>
                  <p>${esc(r.rationale)}</p>
                  <ul class="actions">${(r.actions || []).map((a) => `<li>${esc(a)}</li>`).join("")}</ul>
                  <div class="insight-meta">
                    <span>Эффект: <b>${esc(r.expected_effect)}</b></span>
                    <span>Замер: <b>${esc(r.measurement_plan)}</b></span>
                  </div>
                  <div style="display:flex;gap:7px;margin-top:4px;flex-wrap:wrap">
                    <button class="btn small secondary" data-rec="${r.id}" data-status="accepted">Принять</button>
                    <button class="btn small secondary" data-rec="${r.id}" data-status="in_progress">В работу</button>
                    <button class="btn small secondary" data-rec="${r.id}" data-status="done">Выполнено</button>
                    <button class="btn small secondary" data-rec="${r.id}" data-status="rejected">Отклонить</button>
                  </div>
                </div>`
                    )
                    .join("")
                : `<div class="empty">Рекомендаций пока нет — запустите анализ точки или сети.</div>`
            }
          </div>
        </div>

        <div class="card reveal">
          <div class="card-head"><h3>История выводов AI</h3><span class="hint">с уверенностью и ограничениями</span></div>
          <div class="grid" style="gap:10px">
            ${insights.length ? insights.map((i) => insightCard(i, false)).join("") : `<div class="empty">Выводов пока нет</div>`}
          </div>
        </div>`;

      const log = root.querySelector("#chat-log");
      const send = async () => {
        const input = root.querySelector("#chat-q");
        const question = input.value.trim();
        if (!question) return;
        input.value = "";
        log.insertAdjacentHTML("beforeend", `<div class="msg user">${esc(question)}</div>`);
        log.scrollTop = log.scrollHeight;
        try {
          const data = await API.post("/api/ai/ask", { question, location_id: ctx.locationId || null });
          log.insertAdjacentHTML(
            "beforeend",
            `<div class="msg ai">${esc(data.answer)}<span class="src">Источники: ${data.sources.map(esc).join(" · ")} · уверенность ${Math.round(data.confidence * 100)}%</span></div>`
          );
        } catch (err) {
          log.insertAdjacentHTML("beforeend", `<div class="msg ai">Не удалось получить ответ: ${esc(err.message)}</div>`);
        }
        log.scrollTop = log.scrollHeight;
      };
      root.querySelector("#chat-send").onclick = send;
      root.querySelector("#chat-q").addEventListener("keydown", (event) => {
        if (event.key === "Enter") send();
      });

      root.querySelector("#net-analyze").onclick = async (event) => {
        event.target.disabled = true;
        try {
          const data = await API.post("/api/ai/analyze-network");
          toast(`Готово: ${data.insights.length} выводов по сети`, "ok");
          ctx.reload();
        } catch (err) {
          toast(err.message, "error");
        } finally {
          event.target.disabled = false;
        }
      };
      root.querySelector("#scan-anomalies").onclick = async () => {
        const data = await API.post("/api/notifications/scan");
        toast(`Проверка завершена: новых уведомлений ${data.created}`, "ok");
      };
      root.querySelectorAll("[data-rec]").forEach((btn) => {
        btn.onclick = async () => {
          await API.patch(`/api/ai/recommendations/${btn.dataset.rec}`, { status: btn.dataset.status });
          toast("Статус рекомендации обновлён", "ok");
          ctx.reload();
        };
      });
    }

    /* ---------------- Отчёты ---------------- */
    async function reports(root, ctx) {
      root.innerHTML = UI.skeleton(2);
      const ranking = await API.get(`/api/analytics/ranking?${qs(ctx)}`);
      root.innerHTML = `
        <div class="card reveal">
          <div class="card-head"><h3>Выгрузка отчётов</h3><span class="hint">CSV, разделитель «;», UTF-8</span></div>
          <div style="display:flex;gap:9px;flex-wrap:wrap">
            <button class="btn" id="dl-daily">Дневная детализация по точкам</button>
            <button class="btn secondary" id="dl-ranking">Рейтинг точек</button>
          </div>
          <div class="demo-hint">Отчёт формируется по выбранному периоду и доступным вам точкам. Данные других компаний недоступны.</div>
        </div>
        <div class="card reveal">
          <div class="card-head"><h3>Сводка за период</h3><span class="hint">${ranking.length} точек</span></div>
          <table class="table">
            <thead><tr><th>#</th><th>Точка</th><th class="num">Трафик</th><th class="num">Входы</th><th class="num">Чеки</th><th class="num">Выручка</th><th class="num">Ср. чек</th></tr></thead>
            <tbody>
              ${ranking
                .map(
                  (r) => `<tr>
                    <td><span class="rank ${r.rank === 1 ? "top" : ""}">${r.rank}</span></td>
                    <td class="name">${esc(r.name)}</td>
                    <td class="num">${num(r.passersby)}</td>
                    <td class="num">${num(r.entries)}</td>
                    <td class="num">${num(r.receipts)}</td>
                    <td class="num">${money(r.revenue)}</td>
                    <td class="num">${money(r.avg_check)}</td>
                  </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>`;
      root.querySelector("#dl-daily").onclick = () => {
        const { from, to } = period(ctx.days);
        API.download(`/api/reports/daily?date_from=${from}&date_to=${to}`);
      };
      root.querySelector("#dl-ranking").onclick = () => {
        const { from, to } = period(ctx.days);
        API.download(`/api/reports/ranking?date_from=${from}&date_to=${to}`);
      };
    }

    /* ---------------- Интеграции ---------------- */
    async function integrations(root, ctx) {
      root.innerHTML = UI.skeleton(2);
      const [items, catalog] = await Promise.all([API.get("/api/integrations"), API.get("/api/integrations/catalog")]);
      root.innerHTML = `
        <div class="card reveal" style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
          <div>
            <div class="kpi-label">Integration Hub</div>
            <div style="font-family:var(--font-display);font-size:22px;margin-top:4px">${items.length} источников · ${items.filter((i) => i.status === "connected").length} активны</div>
          </div>
          <button class="btn" id="add-int">+ Подключить источник</button>
        </div>
        <div class="grid three">
          ${items
            .map(
              (item) => `
            <div class="card int-card reveal">
              <div class="int-head">
                <div class="int-logo">${esc(item.provider.slice(0, 2).toUpperCase())}</div>
                <div style="flex:1">
                  <strong>${esc(item.name)}</strong>
                  <small>${esc(item.kind)} · ${esc(item.provider)}</small>
                </div>
                ${statusDot(item.status === "connected" ? "active" : item.status === "error" ? "offline" : "attention")}
              </div>
              <div style="font-size:11.5px;color:var(--dim);display:flex;flex-direction:column;gap:3px">
                <span>Статус: <b style="color:var(--muted)">${STATUS_LABEL[item.status] || item.status}</b></span>
                <span>Синхронизация: <b style="color:var(--muted)">${item.last_sync_at ? item.last_sync_at.slice(0, 16).replace("T", " ") : "не выполнялась"}</b></span>
                <span>Интервал: <b style="color:var(--muted)">${item.sync_interval_min} мин</b></span>
                ${item.last_error ? `<span style="color:var(--magenta)">${esc(item.last_error)}</span>` : ""}
              </div>
              <div class="int-actions">
                <button class="btn small secondary" data-test="${item.id}">Проверить</button>
                <button class="btn small" data-sync="${item.id}">Синхронизировать</button>
                <button class="btn small secondary" data-logs="${item.id}">Журнал</button>
              </div>
            </div>`
            )
            .join("")}
        </div>
        <div class="card reveal">
          <div class="card-head"><h3>Доступные коннекторы</h3><span class="hint">модульная архитектура</span></div>
          <div class="grid three">
            ${catalog
              .map(
                (c) => `
              <div style="border:1px solid var(--line);border-radius:11px;padding:13px">
                <strong style="font-size:13px">${esc(c.name)}</strong>
                <p style="color:var(--muted);font-size:11.5px;line-height:1.55;margin:6px 0 0">${esc(c.description)}</p>
              </div>`
              )
              .join("")}
          </div>
        </div>`;

      root.querySelector("#add-int").onclick = () => integrationModal(ctx, catalog);
      root.querySelectorAll("[data-test]").forEach((btn) => {
        btn.onclick = async () => {
          btn.disabled = true;
          try {
            const res = await API.post(`/api/integrations/${btn.dataset.test}/test`);
            toast(res.message || (res.ok ? "Соединение установлено" : "Ошибка соединения"), res.ok ? "ok" : "error");
            ctx.reload();
          } catch (err) {
            toast(err.message, "error");
          } finally {
            btn.disabled = false;
          }
        };
      });
      root.querySelectorAll("[data-sync]").forEach((btn) => {
        btn.onclick = async () => {
          btn.disabled = true;
          btn.textContent = "Синхронизация…";
          try {
            const res = await API.post(`/api/integrations/${btn.dataset.sync}/sync`);
            toast(res.ok ? `Загружено записей: ${res.records}` : `Ошибка: ${res.error}`, res.ok ? "ok" : "error");
            ctx.reload();
          } catch (err) {
            toast(err.message, "error");
          } finally {
            btn.disabled = false;
            btn.textContent = "Синхронизировать";
          }
        };
      });
      root.querySelectorAll("[data-logs]").forEach((btn) => {
        btn.onclick = async () => {
          const logs = await API.get(`/api/integrations/${btn.dataset.logs}/logs`);
          modal({
            title: "Журнал интеграции",
            subtitle: "запросы, ошибки и результаты синхронизации",
            body: logs.length
              ? `<div class="log-list">${logs
                  .map(
                    (l) => `<div class="log-row ${l.level}">
                      <span class="t">${l.created_at.slice(5, 16).replace("T", " ")}</span>
                      <span>${esc(l.message)}</span>
                    </div>`
                  )
                  .join("")}</div>`
              : `<div class="empty">Журнал пуст</div>`,
            actions: [{ label: "Закрыть" }],
          });
        };
      });
    }

    function integrationModal(ctx, catalog) {
      modal({
        title: "Подключить источник данных",
        subtitle: "Ключи шифруются и не отдаются в интерфейс",
        body: `
          <div class="field"><label>Тип источника</label>
            <select class="select" id="int-provider">
              ${catalog.map((c) => `<option value="${c.provider}">${esc(c.name)}</option>`).join("")}
            </select>
          </div>
          <div class="field"><label>Название</label><input class="input" id="int-name" placeholder="Например, Ivideon · кассы" /></div>
          <div class="field"><label>API URL</label><input class="input" id="int-url" placeholder="https://api.example.com" /></div>
          <div class="form-row">
            <div class="field"><label>Авторизация</label>
              <select class="select" id="int-auth">
                <option value="api_key">API Key</option>
                <option value="bearer">Bearer token</option>
                <option value="oauth2">OAuth 2.0</option>
                <option value="none">Без авторизации</option>
              </select>
            </div>
            <div class="field"><label>Интервал, мин</label><input class="input" id="int-interval" type="number" value="60" /></div>
          </div>
          <div class="field"><label>Ключ / токен</label><input class="input" id="int-key" placeholder="Секрет не отображается после сохранения" /></div>
          <div class="field"><label>Точки (id через запятую)</label><input class="input" id="int-locs" placeholder="1,2,3" /></div>`,
        actions: [
          { label: "Отмена" },
          {
            label: "Подключить",
            kind: "",
            onClick: async (root) => {
              const provider = root.querySelector("#int-provider").value;
              const meta = catalog.find((c) => c.provider === provider);
              const name = root.querySelector("#int-name").value.trim() || meta.name;
              const locs = root
                .querySelector("#int-locs")
                .value.split(",")
                .map((x) => Number(x.trim()))
                .filter(Boolean);
              await API.post("/api/integrations", {
                kind: meta.kind,
                provider,
                name,
                base_url: root.querySelector("#int-url").value.trim(),
                auth_type: root.querySelector("#int-auth").value,
                credentials: { api_key: root.querySelector("#int-key").value.trim() },
                config: { location_ids: locs },
                sync_interval_min: Number(root.querySelector("#int-interval").value) || 60,
              });
              toast("Источник добавлен", "ok");
              ctx.reload();
            },
          },
        ],
      });
    }

    /* ---------------- Уведомления ---------------- */
    async function notifications(root, ctx) {
      root.innerHTML = UI.skeleton(2);
      const items = await API.get("/api/notifications");
      root.innerHTML = `
        <div class="card reveal" style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
          <div>
            <div class="kpi-label">Мониторинг</div>
            <div style="font-family:var(--font-display);font-size:22px;margin-top:4px">${items.filter((i) => !i.read).length} непрочитанных</div>
          </div>
          <button class="btn secondary" id="scan">Проверить аномалии</button>
        </div>
        <div class="card reveal">
          <div class="grid" style="gap:9px">
            ${
              items.length
                ? items
                    .map(
                      (n) => `
                <div class="insight ${n.severity}" style="opacity:${n.read ? 0.6 : 1}">
                  <div class="insight-head">
                    <span class="pill ${n.severity}">${SEVERITY_LABEL[n.severity] || n.severity}</span>
                    <strong>${esc(n.title)}</strong>
                    <span style="margin-left:auto;font-size:10.5px;color:var(--dim);font-family:var(--font-mono)">${n.created_at.slice(5, 16).replace("T", " ")}</span>
                  </div>
                  <p>${esc(n.body)}</p>
                  <div class="insight-meta">
                    ${n.location ? `<span>Точка: <b>${esc(n.location)}</b></span>` : ""}
                    ${!n.read ? `<button class="btn small secondary" data-read="${n.id}">Отметить прочитанным</button>` : `<span>Прочитано</span>`}
                  </div>
                </div>`
                    )
                    .join("")
                : `<div class="empty">Уведомлений нет</div>`
            }
          </div>
        </div>`;
      root.querySelector("#scan").onclick = async () => {
        const data = await API.post("/api/notifications/scan");
        toast(`Новых уведомлений: ${data.created}`, "ok");
        ctx.reload();
      };
      root.querySelectorAll("[data-read]").forEach((btn) => {
        btn.onclick = async () => {
          await API.post(`/api/notifications/${btn.dataset.read}/read`);
          ctx.reload();
        };
      });
    }

    /* ---------------- Настройки ---------------- */
    async function settings(root, ctx) {
      root.innerHTML = UI.skeleton(2);
      const [org, members, audit] = await Promise.all([
        API.get("/api/org"),
        API.get("/api/org/members"),
        API.get("/api/org/audit").catch(() => []),
      ]);
      root.innerHTML = `
        <div class="grid two">
          <div class="card reveal">
            <div class="card-head"><h3>Организация</h3><span class="hint">${esc(ROLE_LABEL[org.role] || org.role)}</span></div>
            <div style="font-family:var(--font-display);font-size:22px;margin-bottom:10px">${esc(org.name)}</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:12px;color:var(--muted)">
              <div>Тариф<b style="display:block;color:var(--text);margin-top:2px">${esc(org.subscription?.plan || "—")}</b></div>
              <div>Точек в лимите<b style="display:block;color:var(--text);margin-top:2px">${org.subscription?.locations_limit ?? "—"}</b></div>
              <div>Мест<b style="display:block;color:var(--text);margin-top:2px">${org.subscription?.seats ?? "—"}</b></div>
              <div>Стоимость<b style="display:block;color:var(--text);margin-top:2px">${org.subscription ? money(org.subscription.price_month) + " / мес" : "—"}</b></div>
            </div>
          </div>
          <div class="card reveal">
            <div class="card-head"><h3>Роли и доступ</h3><span class="hint">изоляция данных</span></div>
            <div style="font-size:12px;color:var(--muted);line-height:1.7">
              Каждый сотрудник видит только свою организацию и только разрешённые точки.
              Роли ограничивают действия: аналитик читает, управляющий фиксирует изменения,
              администратор управляет доступами.
            </div>
          </div>
        </div>
        <div class="card reveal">
          <div class="card-head"><h3>Сотрудники</h3><button class="btn small" id="add-member">+ Добавить</button></div>
          <table class="table">
            <thead><tr><th>Сотрудник</th><th>Роль</th><th>Статус</th><th>Последний вход</th></tr></thead>
            <tbody>
              ${members
                .map(
                  (m) => `<tr>
                    <td class="name">${esc(m.full_name)}<div style="color:var(--dim);font-size:10.5px">${esc(m.email)}</div></td>
                    <td>${ROLE_LABEL[m.role] || m.role}</td>
                    <td>${m.is_active ? "Активен" : "Отключён"}</td>
                    <td style="font-family:var(--font-mono);font-size:11px">${m.last_login_at ? m.last_login_at.slice(0, 16).replace("T", " ") : "—"}</td>
                  </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
        <div class="card reveal">
          <div class="card-head"><h3>Журнал действий</h3><span class="hint">аудит</span></div>
          ${
            audit.length
              ? `<div class="log-list">${audit
                  .map(
                    (a) => `<div class="log-row"><span class="t">${a.created_at.slice(5, 16).replace("T", " ")}</span><span>${esc(a.action)} · ${esc(a.entity)} #${esc(a.entity_id)}</span></div>`
                  )
                  .join("")}</div>`
              : `<div class="empty">Событий пока нет</div>`
          }
        </div>`;
      root.querySelector("#add-member").onclick = () => memberModal(ctx);
    }

    function memberModal(ctx) {
      modal({
        title: "Добавить сотрудника",
        subtitle: "Доступ ограничен вашей организацией",
        body: `
          <div class="field"><label>Email</label><input class="input" id="m-email" type="email" /></div>
          <div class="field"><label>Имя</label><input class="input" id="m-name" /></div>
          <div class="field"><label>Роль</label>
            <select class="select" id="m-role">
              <option value="ANALYST">Аналитик</option>
              <option value="LOCATION_MANAGER">Управляющий точкой</option>
              <option value="REGIONAL_MANAGER">Региональный менеджер</option>
              <option value="NETWORK_MANAGER">Руководитель сети</option>
              <option value="ORG_ADMIN">Администратор компании</option>
            </select>
          </div>
          <div class="field"><label>Пароль (если новый пользователь)</label><input class="input" id="m-pass" placeholder="Минимум 8 символов" /></div>`,
        actions: [
          { label: "Отмена" },
          {
            label: "Добавить",
            kind: "",
            onClick: async (root) => {
              await API.post("/api/org/members", {
                email: root.querySelector("#m-email").value.trim(),
                full_name: root.querySelector("#m-name").value.trim(),
                role: root.querySelector("#m-role").value,
                password: root.querySelector("#m-pass").value || null,
                scope: {},
              });
              toast("Сотрудник добавлен", "ok");
              ctx.reload();
            },
          },
        ],
      });
    }

    /* ---------------- Админ платформы ---------------- */
    async function admin(root, ctx) {
      root.innerHTML = UI.skeleton(2);
      const [stats, orgs, users, ints] = await Promise.all([
        API.get("/api/admin/stats"),
        API.get("/api/admin/organizations"),
        API.get("/api/admin/users"),
        API.get("/api/admin/integrations"),
      ]);
      root.innerHTML = `
        <div class="grid kpi">
          ${kpiCard("Организации", num(stats.organizations), null, "", "#35f0d0")}
          ${kpiCard("Пользователи", num(stats.users), null, "", "#8b7bff")}
          ${kpiCard("Точки", num(stats.locations), null, "", "#c8ff4d")}
          ${kpiCard("Интеграции", num(stats.integrations), null, "", "#ffb84d")}
          ${kpiCard("Ошибки интеграций", num(stats.integrations_error), null, "", "#ff4d8d")}
          ${kpiCard("Чеки в базе", num(stats.transactions), null, "", "#35f0d0")}
        </div>
        <div class="card reveal">
          <div class="card-head"><h3>Организации</h3><span class="hint">SaaS-клиенты</span></div>
          <table class="table">
            <thead><tr><th>Компания</th><th>Тариф</th><th class="num">Точек</th><th class="num">Пользователей</th><th>Статус</th></tr></thead>
            <tbody>
              ${orgs
                .map(
                  (o) => `<tr>
                    <td class="name">${esc(o.name)}<div style="color:var(--dim);font-size:10.5px">${esc(o.slug)}</div></td>
                    <td>${esc(o.subscription?.plan || o.plan)}</td>
                    <td class="num">${o.locations}</td>
                    <td class="num">${o.users}</td>
                    <td>${esc(o.status)}</td>
                  </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
        <div class="grid half">
          <div class="card reveal">
            <div class="card-head"><h3>Пользователи</h3><span class="hint">${users.length}</span></div>
            <div class="log-list">
              ${users
                .map(
                  (u) => `<div class="log-row">
                    <span class="t">${u.id}</span>
                    <span>${esc(u.full_name)} · ${esc(u.email)} ${u.is_superadmin ? "· суперадмин" : ""}</span>
                  </div>`
                )
                .join("")}
            </div>
          </div>
          <div class="card reveal">
            <div class="card-head"><h3>Интеграции платформы</h3><span class="hint">${ints.length}</span></div>
            <div class="log-list">
              ${ints
                .map(
                  (i) => `<div class="log-row ${i.status === "error" ? "error" : ""}">
                    <span class="t">${esc(i.status)}</span>
                    <span>${esc(i.organization)} · ${esc(i.name)}</span>
                  </div>`
                )
                .join("")}
            </div>
          </div>
        </div>`;
    }

    /* ---------------- Локальный контекст точки ---------------- */
    async function locationExtras(root, ctx, id) {
      const host = root.querySelector("#loc-extras");
      if (!host) return;
      host.innerHTML = `
        <div class="card reveal">
          <div class="card-head">
            <h3>Локальный контекст точки</h3>
            <span class="hint">ЦА, оценка, гипотезы, тесты, пилот</span>
          </div>
          <div class="tabs" id="ext-tabs">
            <button data-tab="audience" class="active">ЦА и трафик</button>
            <button data-tab="score">Оценка точки</button>
            <button data-tab="hypotheses">Гипотезы</button>
            <button data-tab="tests">План тестов</button>
            <button data-tab="trends">Тренды</button>
            <button data-tab="photos">Фото-аудит</button>
            <button data-tab="pilot">Пилот</button>
            <button data-tab="manual">Ручной ввод</button>
          </div>
          <div id="ext-body" style="margin-top:14px"><div class="empty">Загрузка…</div></div>
        </div>`;

      const body = host.querySelector("#ext-body");
      const tabs = host.querySelectorAll("#ext-tabs button");
      const render = async (tab) => {
        tabs.forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
        body.innerHTML = `<div class="empty">Загрузка…</div>`;
        try {
          if (tab === "audience") await renderAudience(body, ctx, id);
          else if (tab === "score") await renderScore(body, ctx, id);
          else if (tab === "hypotheses") await renderHypotheses(body, ctx, id);
          else if (tab === "tests") await renderTests(body, ctx, id);
          else if (tab === "trends") await renderTrends(body, ctx, id);
          else if (tab === "photos") await renderPhotos(body, ctx, id);
          else if (tab === "manual") await renderManual(body, ctx, id);
          else await renderPilot(body, ctx, id);
        } catch (err) {
          body.innerHTML = `<div class="empty">Не удалось загрузить: ${esc(err.message)}</div>`;
        }
      };
      tabs.forEach((btn) => (btn.onclick = () => render(btn.dataset.tab)));
      await render("audience");
    }

    async function renderAudience(body, ctx, id) {
      const rows = await API.get(`/api/locations/${id}/audience`);
      body.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">
          <div style="font-size:12px;color:var(--muted);max-width:640px">
            Кто проходит мимо точки, когда и с каким мотивом. AI учитывает этот профиль
            вместе с адресом точки, когда объясняет изменения и предлагает действия.
          </div>
          <button class="btn small" id="add-seg">+ Сегмент</button>
        </div>
        ${
          rows.length
            ? `<table class="table">
                <thead><tr><th>Когда</th><th>Сегмент</th><th>Возраст</th><th>Мотив</th><th>Что сработает</th><th></th></tr></thead>
                <tbody>
                  ${rows
                    .map(
                      (r) => `<tr>
                        <td style="white-space:nowrap">${esc(r.weekday)}<div style="color:var(--dim);font-size:10.5px">${esc(r.time_from)}–${esc(r.time_to)}</div></td>
                        <td class="name">${esc(r.segment)}<div style="color:var(--dim);font-size:10.5px">${esc(r.composition)}</div></td>
                        <td>${esc(r.age)}</td>
                        <td style="max-width:220px">${esc(r.motive)}</td>
                        <td style="max-width:220px">${esc(r.what_works)}</td>
                        <td><button class="btn small secondary" data-del-seg="${r.id}">Удалить</button></td>
                      </tr>`
                    )
                    .join("")}
                </tbody>
              </table>`
            : `<div class="empty">Профиль ЦА не заполнен. Добавьте сегменты — AI будет учитывать их в анализе.</div>`
        }`;
      body.querySelector("#add-seg").onclick = () =>
        modal({
          title: "Сегмент локальной ЦА",
          subtitle: "кто проходит мимо точки и что для него важно",
          body: `
            <div class="form-row">
              <div class="field"><label>Когда</label>
                <select class="select" id="seg-weekday">
                  <option>Будни</option><option>Выходные</option><option>Вечер</option><option>Ежедневно</option>
                </select>
              </div>
              <div class="field"><label>Возраст</label><input class="input" id="seg-age" placeholder="25–45" /></div>
            </div>
            <div class="form-row">
              <div class="field"><label>С</label><input class="input" id="seg-from" placeholder="12:00" /></div>
              <div class="field"><label>По</label><input class="input" id="seg-to" placeholder="15:00" /></div>
            </div>
            <div class="field"><label>Сегмент</label><input class="input" id="seg-name" placeholder="Офисные сотрудники" /></div>
            <div class="field"><label>Состав</label><input class="input" id="seg-comp" placeholder="1–2 человека" /></div>
            <div class="field"><label>Сценарий поведения</label><textarea class="textarea" id="seg-behavior"></textarea></div>
            <div class="field"><label>Потенциальный мотив</label><textarea class="textarea" id="seg-motive"></textarea></div>
            <div class="field"><label>Что может сработать</label><textarea class="textarea" id="seg-works"></textarea></div>`,
          actions: [
            { label: "Отмена" },
            {
              label: "Добавить",
              kind: "",
              onClick: async (r) => {
                const segment = r.querySelector("#seg-name").value.trim();
                if (!segment) {
                  toast("Укажите сегмент", "error");
                  return false;
                }
                await API.post(`/api/locations/${id}/audience`, {
                  weekday: r.querySelector("#seg-weekday").value,
                  time_from: r.querySelector("#seg-from").value.trim(),
                  time_to: r.querySelector("#seg-to").value.trim(),
                  segment,
                  age: r.querySelector("#seg-age").value.trim(),
                  composition: r.querySelector("#seg-comp").value.trim(),
                  behavior: r.querySelector("#seg-behavior").value.trim(),
                  motive: r.querySelector("#seg-motive").value.trim(),
                  what_works: r.querySelector("#seg-works").value.trim(),
                });
                toast("Сегмент добавлен", "ok");
                await renderAudience(body, ctx, id);
              },
            },
          ],
        });
      body.querySelectorAll("[data-del-seg]").forEach((btn) => {
        btn.onclick = async () => {
          await API.del(`/api/locations/${id}/audience/${btn.dataset.delSeg}`);
          await renderAudience(body, ctx, id);
        };
      });
    }

    async function renderScore(body, ctx, id) {
      const data = await API.get(`/api/locations/${id}/score`);
      body.innerHTML = `
        <div style="display:flex;gap:18px;flex-wrap:wrap;align-items:flex-start">
          <div style="flex:1;min-width:280px">
            ${data.parameters
              .map(
                (p) => `<div style="display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.04)">
                  <div style="flex:1;font-size:12.5px">${esc(p.label)}<span style="color:var(--dim);font-size:10.5px"> · вес ${p.weight}</span></div>
                  <input class="input" type="number" min="1" max="5" step="1" style="width:70px" data-score="${p.key}" value="${data.scores[p.key] ?? ""}" />
                </div>`
              )
              .join("")}
            <button class="btn" style="margin-top:12px" id="save-score">Сохранить оценку</button>
          </div>
          <div style="width:220px;text-align:center;border:1px solid var(--line);border-radius:12px;padding:16px">
            <div class="kpi-label">Индекс точки</div>
            <div style="font-family:var(--font-display);font-size:38px;margin:6px 0">${data.index ? data.index.toFixed(2).replace(".", ",") : "—"}</div>
            <div style="font-size:11.5px;color:var(--muted);line-height:1.5">${esc(data.interpretation)}</div>
          </div>
        </div>`;
      body.querySelector("#save-score").onclick = async () => {
        const scores = {};
        body.querySelectorAll("[data-score]").forEach((input) => {
          const value = Number(input.value);
          if (value >= 1 && value <= 5) scores[input.dataset.score] = value;
        });
        const res = await API.patch(`/api/locations/${id}/score`, { scores }).catch(() => null);
        if (!res) {
          await API.post(`/api/locations/${id}/score`, { scores }).catch(() => null);
        }
        toast("Оценка сохранена", "ok");
        await renderScore(body, ctx, id);
      };
    }

    async function renderHypotheses(body, ctx, id) {
      const rows = await API.get(`/api/locations/${id}/hypotheses`);
      body.innerHTML = `
        <div style="display:flex;justify-content:flex-end;margin-bottom:10px">
          <button class="btn small" id="add-hyp">+ Гипотеза</button>
        </div>
        ${
          rows.length
            ? `<table class="table">
                <thead><tr><th>Гипотеза</th><th>Метрика</th><th>Рост</th><th>Срок</th><th>Результат</th><th></th></tr></thead>
                <tbody>
                  ${rows
                    .map(
                      (r) => `<tr>
                        <td class="name">${esc(r.hypothesis)}<div style="color:var(--dim);font-size:10.5px">${esc(r.change)}</div></td>
                        <td>${esc(r.metric)}</td>
                        <td>${esc(r.growth)}</td>
                        <td>${esc(r.test_days)}</td>
                        <td>${esc(r.result)}</td>
                        <td><button class="btn small secondary" data-hyp="${r.id}">Итог</button></td>
                      </tr>`
                    )
                    .join("")}
                </tbody>
              </table>`
            : `<div class="empty">Гипотез нет. Добавьте первую — платформа свяжет её с замером «до/после».</div>`
        }`;
      body.querySelector("#add-hyp").onclick = () =>
        modal({
          title: "Новая гипотеза",
          subtitle: "что меняем, какую метрику ждём и за какой срок",
          body: `
            <div class="field"><label>Гипотеза</label><input class="input" id="h-text" placeholder="Неоновый контур окон увеличит количество взглядов" /></div>
            <div class="field"><label>Что меняем</label><textarea class="textarea" id="h-change"></textarea></div>
            <div class="form-row">
              <div class="field"><label>Метрика</label><input class="input" id="h-metric" placeholder="Взгляды" /></div>
              <div class="field"><label>Ожидаемый рост</label><input class="input" id="h-growth" placeholder="10–15%" /></div>
            </div>
            <div class="field"><label>Срок теста</label><input class="input" id="h-days" placeholder="14–30 дней" /></div>`,
          actions: [
            { label: "Отмена" },
            {
              label: "Добавить",
              kind: "",
              onClick: async (r) => {
                const hypothesis = r.querySelector("#h-text").value.trim();
                if (!hypothesis) {
                  toast("Опишите гипотезу", "error");
                  return false;
                }
                await API.post(`/api/locations/${id}/hypotheses`, {
                  hypothesis,
                  change: r.querySelector("#h-change").value.trim(),
                  metric: r.querySelector("#h-metric").value.trim(),
                  growth: r.querySelector("#h-growth").value.trim(),
                  test_days: r.querySelector("#h-days").value.trim(),
                });
                toast("Гипотеза добавлена", "ok");
                await renderHypotheses(body, ctx, id);
              },
            },
          ],
        });
      body.querySelectorAll("[data-hyp]").forEach((btn) => {
        btn.onclick = () =>
          modal({
            title: "Итог гипотезы",
            body: `
              <div class="field"><label>Результат</label>
                <select class="select" id="h-res">
                  <option>Не начато</option><option>Идёт</option><option>Подтвердилась</option><option>Не подтвердилась</option>
                </select>
              </div>
              <div class="field"><label>Вывод</label><textarea class="textarea" id="h-concl"></textarea></div>
              <div class="field"><label>Следующее действие</label><input class="input" id="h-next" /></div>`,
            actions: [
              { label: "Отмена" },
              {
                label: "Сохранить",
                kind: "",
                onClick: async (r) => {
                  await API.patch(`/api/locations/${id}/hypotheses/${btn.dataset.hyp}`, {
                    result: r.querySelector("#h-res").value,
                    conclusion: r.querySelector("#h-concl").value.trim(),
                    next_action: r.querySelector("#h-next").value.trim(),
                  });
                  await renderHypotheses(body, ctx, id);
                },
              },
            ],
          });
      });
    }

    async function renderTests(body, ctx, id) {
      const rows = await API.get(`/api/locations/${id}/tests`);
      body.innerHTML = `
        <div style="display:flex;justify-content:flex-end;margin-bottom:10px">
          <button class="btn small" id="add-test">+ Тест</button>
        </div>
        ${
          rows.length
            ? `<table class="table">
                <thead><tr><th>Тест</th><th>Что делаем</th><th>Метрика</th><th>Цель</th><th>Результат</th></tr></thead>
                <tbody>
                  ${rows
                    .map(
                      (r) => `<tr>
                        <td class="name">${esc(r.name)}</td>
                        <td style="max-width:260px">${esc(r.what)}</td>
                        <td>${esc(r.metric)}</td>
                        <td>${esc(r.goal)}</td>
                        <td>${esc(r.result)}</td>
                      </tr>`
                    )
                    .join("")}
                </tbody>
              </table>`
            : `<div class="empty">План тестов пуст.</div>`
        }`;
      body.querySelector("#add-test").onclick = () =>
        modal({
          title: "Новый тест",
          body: `
            <div class="field"><label>Название</label><input class="input" id="t-name" placeholder="Динамика вывески" /></div>
            <div class="field"><label>Что делаем</label><textarea class="textarea" id="t-what"></textarea></div>
            <div class="form-row">
              <div class="field"><label>Метрика</label><input class="input" id="t-metric" placeholder="Взгляды" /></div>
              <div class="field"><label>Цель</label><input class="input" id="t-goal" placeholder="+10%" /></div>
            </div>`,
          actions: [
            { label: "Отмена" },
            {
              label: "Добавить",
              kind: "",
              onClick: async (r) => {
                const name = r.querySelector("#t-name").value.trim();
                if (!name) {
                  toast("Укажите название теста", "error");
                  return false;
                }
                await API.post(`/api/locations/${id}/tests`, {
                  name,
                  what: r.querySelector("#t-what").value.trim(),
                  metric: r.querySelector("#t-metric").value.trim(),
                  goal: r.querySelector("#t-goal").value.trim(),
                });
                await renderTests(body, ctx, id);
              },
            },
          ],
        });
    }

    async function renderTrends(body, ctx, id) {
      const rows = await API.get(`/api/locations/${id}/trends`);
      body.innerHTML = `
        <div style="display:flex;justify-content:flex-end;margin-bottom:10px">
          <button class="btn small" id="add-trend">+ Тренд</button>
        </div>
        ${
          rows.length
            ? `<div class="grid" style="gap:9px">${rows
                .map(
                  (r) => `<div class="insight info">
                    <div class="insight-head"><span class="pill info">${esc(r.kind)}</span><strong>${esc(r.title)}</strong><span class="pill" style="margin-left:auto">${esc(r.status)}</span></div>
                    <p>${esc(r.why)}</p>
                    <div class="insight-meta"><span>Идея: <b>${esc(r.idea)}</b></span><span>Срочность: <b>${esc(r.urgency)}</b></span></div>
                  </div>`
                )
                .join("")}</div>`
            : `<div class="empty">Трендов нет.</div>`
        }`;
      body.querySelector("#add-trend").onclick = () =>
        modal({
          title: "Тренд или инфоповод",
          body: `
            <div class="form-row">
              <div class="field"><label>Тип</label><input class="input" id="tr-kind" placeholder="Погода / Сезон / Событие" /></div>
              <div class="field"><label>Срочность</label><input class="input" id="tr-urg" placeholder="Средняя" /></div>
            </div>
            <div class="field"><label>Тренд</label><input class="input" id="tr-title" placeholder="Холодная неделя" /></div>
            <div class="field"><label>Почему важно</label><textarea class="textarea" id="tr-why"></textarea></div>
            <div class="field"><label>Идея для вывески</label><textarea class="textarea" id="tr-idea"></textarea></div>`,
          actions: [
            { label: "Отмена" },
            {
              label: "Добавить",
              kind: "",
              onClick: async (r) => {
                const title = r.querySelector("#tr-title").value.trim();
                if (!title) {
                  toast("Укажите тренд", "error");
                  return false;
                }
                await API.post(`/api/locations/${id}/trends`, {
                  kind: r.querySelector("#tr-kind").value.trim(),
                  title,
                  why: r.querySelector("#tr-why").value.trim(),
                  idea: r.querySelector("#tr-idea").value.trim(),
                  urgency: r.querySelector("#tr-urg").value.trim(),
                });
                await renderTrends(body, ctx, id);
              },
            },
          ],
        });
    }

    async function renderPhotos(body, ctx, id) {
      const rows = await API.get(`/api/locations/${id}/photos`);
      body.innerHTML = `
        <div style="display:flex;justify-content:flex-end;margin-bottom:10px">
          <button class="btn small" id="add-photo">+ Ракурс</button>
        </div>
        ${
          rows.length
            ? `<table class="table">
                <thead><tr><th>Ракурс</th><th>Проблема</th><th>Рекомендация</th><th>Приоритет</th></tr></thead>
                <tbody>${rows
                  .map(
                    (r) => `<tr>
                      <td class="name">${esc(r.angle)}</td>
                      <td style="max-width:240px">${esc(r.problem)}</td>
                      <td style="max-width:280px">${esc(r.recommendation)}</td>
                      <td>${esc(r.priority)}</td>
                    </tr>`
                  )
                  .join("")}</tbody>
              </table>`
            : `<div class="empty">Фото-аудит не заполнен.</div>`
        }`;
      body.querySelector("#add-photo").onclick = () =>
        modal({
          title: "Ракурс фото-аудита",
          body: `
            <div class="field"><label>Ракурс</label><input class="input" id="p-angle" placeholder="20–30 метров прямо" /></div>
            <div class="field"><label>Что видно хорошо</label><textarea class="textarea" id="p-good"></textarea></div>
            <div class="field"><label>Что видно плохо</label><textarea class="textarea" id="p-bad"></textarea></div>
            <div class="field"><label>Проблема</label><input class="input" id="p-problem" /></div>
            <div class="field"><label>Рекомендация</label><textarea class="textarea" id="p-rec"></textarea></div>
            <div class="field"><label>Приоритет</label>
              <select class="select" id="p-prio"><option>Высокий</option><option selected>Средний</option><option>Низкий</option></select>
            </div>`,
          actions: [
            { label: "Отмена" },
            {
              label: "Добавить",
              kind: "",
              onClick: async (r) => {
                await API.post(`/api/locations/${id}/photos`, {
                  angle: r.querySelector("#p-angle").value.trim(),
                  good: r.querySelector("#p-good").value.trim(),
                  bad: r.querySelector("#p-bad").value.trim(),
                  problem: r.querySelector("#p-problem").value.trim(),
                  recommendation: r.querySelector("#p-rec").value.trim(),
                  priority: r.querySelector("#p-prio").value,
                });
                await renderPhotos(body, ctx, id);
              },
            },
          ],
        });
    }

    async function renderPilot(body, ctx, id) {
      const pilot = await API.get(`/api/locations/${id}/pilot`);
      body.innerHTML = `
        <div class="grid half">
          <div>
            <div class="form-row">
              <div class="field"><label>Дата установки вывески</label><input class="input" type="date" id="pl-sign" value="${pilot.signage_date ? pilot.signage_date.slice(0, 10) : ""}" /></div>
              <div class="field"><label>Дата запуска ИИ-камеры</label><input class="input" type="date" id="pl-cam" value="${pilot.camera_date ? pilot.camera_date.slice(0, 10) : ""}" /></div>
            </div>
            <div class="form-row">
              <div class="field"><label>Средний чек, ₽</label><input class="input" type="number" id="pl-check" value="${pilot.avg_check || ""}" /></div>
              <div class="field"><label>Цель роста чеков, %</label><input class="input" type="number" step="0.01" id="pl-target" value="${pilot.target_growth}" /></div>
            </div>
            <div class="form-row">
              <div class="field"><label>Мин. дней ДО</label><input class="input" type="number" id="pl-before" value="${pilot.min_days_before}" /></div>
              <div class="field"><label>Мин. дней ПОСЛЕ</label><input class="input" type="number" id="pl-after" value="${pilot.min_days_after}" /></div>
            </div>
            <div class="field"><label>Комментарий</label><textarea class="textarea" id="pl-comment">${esc(pilot.comment)}</textarea></div>
            <button class="btn" id="save-pilot">Сохранить настройки пилота</button>
          </div>
          <div>
            <div class="card-head"><h3>Эффект «до / после»</h3><span class="hint">по дате вывески</span></div>
            <div id="pilot-result"><div class="empty">Укажите дату установки вывески и нажмите «Рассчитать»</div></div>
            <button class="btn secondary" style="margin-top:10px" id="calc-pilot">Рассчитать</button>
          </div>
        </div>`;
      body.querySelector("#save-pilot").onclick = async () => {
        const sign = body.querySelector("#pl-sign").value;
        const cam = body.querySelector("#pl-cam").value;
        await API.put(`/api/locations/${id}/pilot`, {
          signage_date: sign ? sign + "T00:00:00" : null,
          camera_date: cam ? cam + "T00:00:00" : null,
          compare_days: 60,
          avg_check: Number(body.querySelector("#pl-check").value) || 0,
          target_growth: Number(body.querySelector("#pl-target").value) || 0.3,
          min_days_before: Number(body.querySelector("#pl-before").value) || 30,
          min_days_after: Number(body.querySelector("#pl-after").value) || 30,
          point_name: pilot.point_name,
          address: pilot.address,
          comment: body.querySelector("#pl-comment").value.trim(),
        });
        toast("Настройки пилота сохранены", "ok");
      };
      body.querySelector("#calc-pilot").onclick = async () => {
        const sign = body.querySelector("#pl-sign").value;
        if (!sign) {
          toast("Укажите дату установки вывески", "error");
          return;
        }
        const data = await API.get(
          `/api/analytics/before-after?location_id=${id}&change_at=${sign}T00:00:00&baseline_days=${pilot.min_days_before}&result_days=${pilot.min_days_after}`
        );
        Views.renderBeforeAfter(body.querySelector("#pilot-result"), data);
      };
    }

    /* ---------------- Ручной ввод показателей ---------------- */
    async function renderManual(body, ctx, id) {
      const rows = await API.get(`/api/locations/${id}/manual`);
      const today = new Date().toISOString().slice(0, 10);
      body.innerHTML = `
        <div class="grid half">
          <div>
            <div style="font-size:12px;color:var(--muted);line-height:1.6;margin-bottom:12px">
              Если точка не подключена к кассе или API, показатели можно вносить вручную.
              Ручные данные за день заменяют данные интеграций за этот же день и сразу
              попадают в дашборд, отчёты и AI-анализ.
            </div>
            <div class="form-row">
              <div class="field"><label>Дата</label><input class="input" type="date" id="mn-day" value="${today}" /></div>
              <div class="field"><label>Выручка, ₽</label><input class="input" type="number" step="0.01" id="mn-revenue" placeholder="15400" /></div>
            </div>
            <div class="form-row">
              <div class="field"><label>Чеков</label><input class="input" type="number" id="mn-receipts" placeholder="12" /></div>
              <div class="field"><label>Средний чек, ₽</label><input class="input" type="number" step="0.01" id="mn-avg" placeholder="рассчитается" /></div>
            </div>
            <div class="form-row">
              <div class="field"><label>Вошедшие</label><input class="input" type="number" id="mn-entries" placeholder="необязательно" /></div>
              <div class="field"><label>Посмотревшие</label><input class="input" type="number" id="mn-looked" placeholder="необязательно" /></div>
            </div>
            <div class="field"><label>Трафик</label><input class="input" type="number" id="mn-pass" placeholder="необязательно" /></div>
            <div class="field"><label>Комментарий</label><input class="input" id="mn-note" placeholder="например, данные из кассовой книги" /></div>
            <button class="btn" id="mn-save">Сохранить за день</button>
          </div>
          <div>
            <div class="card-head"><h3>Внесённые дни</h3><span class="hint">${rows.length}</span></div>
            ${
              rows.length
                ? `<table class="table">
                    <thead><tr><th>Дата</th><th class="num">Выручка</th><th class="num">Чеки</th><th class="num">Ср. чек</th><th></th></tr></thead>
                    <tbody>
                      ${rows
                        .map(
                          (r) => `<tr>
                            <td style="font-family:var(--font-mono);font-size:11.5px">${r.day}</td>
                            <td class="num">${r.revenue != null ? money(r.revenue) : "—"}</td>
                            <td class="num">${r.receipts ?? "—"}</td>
                            <td class="num">${r.avg_check != null ? money(r.avg_check) : "—"}</td>
                            <td><button class="btn small secondary" data-del-manual="${r.day}">Удалить</button></td>
                          </tr>`
                        )
                        .join("")}
                    </tbody>
                  </table>`
                : `<div class="empty">Ручных данных пока нет.</div>`
            }
          </div>
        </div>`;
      body.querySelector("#mn-save").onclick = async () => {
        const revenue = body.querySelector("#mn-revenue").value;
        const receipts = body.querySelector("#mn-receipts").value;
        const avg = body.querySelector("#mn-avg").value;
        let revenueValue = revenue === "" ? null : Number(revenue);
        let receiptsValue = receipts === "" ? null : Number(receipts);
        if (revenueValue === null && avg !== "" && receiptsValue) {
          revenueValue = Number(avg) * receiptsValue;
        }
        if (revenueValue === null && receiptsValue === null) {
          toast("Укажите выручку или количество чеков", "error");
          return;
        }
        await API.post(`/api/locations/${id}/manual`, {
          day: body.querySelector("#mn-day").value,
          revenue: revenueValue,
          receipts: receiptsValue,
          entries: body.querySelector("#mn-entries").value === "" ? null : Number(body.querySelector("#mn-entries").value),
          looked: body.querySelector("#mn-looked").value === "" ? null : Number(body.querySelector("#mn-looked").value),
          passersby: body.querySelector("#mn-pass").value === "" ? null : Number(body.querySelector("#mn-pass").value),
          note: body.querySelector("#mn-note").value.trim(),
        });
        toast("Данные сохранены", "ok");
        await renderManual(body, ctx, id);
      };
      body.querySelectorAll("[data-del-manual]").forEach((btn) => {
        btn.onclick = async () => {
          await API.del(`/api/locations/${id}/manual/${btn.dataset.delManual}`);
          await renderManual(body, ctx, id);
        };
      });
    }

    function manualModal(ctx) {
      const options = (ctx.locations || [])
        .map((loc) => `<option value="${loc.id}">${esc(loc.name)}</option>`)
        .join("");
      modal({
        title: "Внести показатели вручную",
        subtitle: "для точек без кассы и API",
        body: `
          <div class="field"><label>Точка</label><select class="select" id="mm-loc">${options}</select></div>
          <div class="form-row">
            <div class="field"><label>Дата</label><input class="input" type="date" id="mm-day" value="${new Date().toISOString().slice(0, 10)}" /></div>
            <div class="field"><label>Выручка, ₽</label><input class="input" type="number" step="0.01" id="mm-revenue" /></div>
          </div>
          <div class="form-row">
            <div class="field"><label>Чеков</label><input class="input" type="number" id="mm-receipts" /></div>
            <div class="field"><label>Средний чек, ₽</label><input class="input" type="number" step="0.01" id="mm-avg" /></div>
          </div>
          <div class="form-row">
            <div class="field"><label>Вошедшие</label><input class="input" type="number" id="mm-entries" /></div>
            <div class="field"><label>Посмотревшие</label><input class="input" type="number" id="mm-looked" /></div>
          </div>
          <div class="field"><label>Комментарий</label><input class="input" id="mm-note" /></div>`,
        actions: [
          { label: "Отмена" },
          {
            label: "Сохранить",
            kind: "",
            onClick: async (root) => {
              const revenue = root.querySelector("#mm-revenue").value;
              const receipts = root.querySelector("#mm-receipts").value;
              const avg = root.querySelector("#mm-avg").value;
              let revenueValue = revenue === "" ? null : Number(revenue);
              const receiptsValue = receipts === "" ? null : Number(receipts);
              if (revenueValue === null && avg !== "" && receiptsValue) {
                revenueValue = Number(avg) * receiptsValue;
              }
              if (revenueValue === null && receiptsValue === null) {
                toast("Укажите выручку или количество чеков", "error");
                return false;
              }
              await API.post(`/api/locations/${root.querySelector("#mm-loc").value}/manual`, {
                day: root.querySelector("#mm-day").value,
                revenue: revenueValue,
                receipts: receiptsValue,
                entries: root.querySelector("#mm-entries").value === "" ? null : Number(root.querySelector("#mm-entries").value),
                looked: root.querySelector("#mm-looked").value === "" ? null : Number(root.querySelector("#mm-looked").value),
                note: root.querySelector("#mm-note").value.trim(),
              });
              toast("Данные сохранены", "ok");
              ctx.reload();
            },
          },
        ],
      });
    }

    return { compare, ai, reports, integrations, notifications, settings, admin, locationExtras, manualModal };
  })()
);
