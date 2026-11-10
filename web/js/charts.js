/* Лёгкие SVG-графики без внешних зависимостей. */
const Charts = (() => {
  const NS = "http://www.w3.org/2000/svg";

  function fmt(v) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    const abs = Math.abs(v);
    if (abs >= 1e9) return (v / 1e9).toFixed(1).replace(".", ",") + " млрд";
    if (abs >= 1e6) return (v / 1e6).toFixed(1).replace(".", ",") + " млн";
    if (abs >= 1e4) return Math.round(v / 1e3) + " тыс";
    if (abs >= 1000) return Math.round(v).toLocaleString("ru-RU");
    if (abs >= 10) return Math.round(v).toString();
    return (Math.round(v * 100) / 100).toString().replace(".", ",");
  }

  function niceMax(v) {
    if (v <= 0) return 1;
    const exp = Math.pow(10, Math.floor(Math.log10(v)));
    const f = v / exp;
    const step = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
    return step * exp;
  }

  function tooltip(container) {
    let tip = container.querySelector(".chart-tip");
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "chart-tip";
      container.appendChild(tip);
    }
    return tip;
  }

  function line(container, opts) {
    const { labels, series, height = 220, yFormat = fmt, area = true, minZero = true } = opts;
    container.innerHTML = "";
    container.classList.add("chart-wrap");
    const width = Math.max(container.clientWidth || 640, 320);
    const pad = { l: 46, r: 12, t: 12, b: 26 };
    const w = width - pad.l - pad.r;
    const h = height - pad.t - pad.b;
    const all = series.flatMap((s) => s.values.filter((v) => v !== null && v !== undefined));
    let max = Math.max(...all, 1);
    let min = minZero ? 0 : Math.min(...all, 0);
    max = niceMax(max);
    const x = (i) => pad.l + (labels.length <= 1 ? w / 2 : (i / (labels.length - 1)) * w);
    const y = (v) => pad.t + h - ((v - min) / (max - min || 1)) * h;

    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", height);
    svg.style.display = "block";

    for (let i = 0; i <= 4; i++) {
      const value = min + ((max - min) / 4) * i;
      const gy = y(value);
      const grid = document.createElementNS(NS, "line");
      grid.setAttribute("x1", pad.l);
      grid.setAttribute("x2", width - pad.r);
      grid.setAttribute("y1", gy);
      grid.setAttribute("y2", gy);
      grid.setAttribute("stroke", "rgba(255,255,255,0.06)");
      svg.appendChild(grid);
      const text = document.createElementNS(NS, "text");
      text.setAttribute("x", pad.l - 8);
      text.setAttribute("y", gy + 3.5);
      text.setAttribute("text-anchor", "end");
      text.setAttribute("fill", "#4d5666");
      text.setAttribute("font-size", "9.5");
      text.setAttribute("font-family", "Cascadia Mono, Consolas, monospace");
      text.textContent = yFormat(value);
      svg.appendChild(text);
    }

    const step = Math.max(1, Math.ceil(labels.length / 8));
    labels.forEach((label, i) => {
      if (i % step !== 0 && i !== labels.length - 1) return;
      const text = document.createElementNS(NS, "text");
      text.setAttribute("x", x(i));
      text.setAttribute("y", height - 8);
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("fill", "#4d5666");
      text.setAttribute("font-size", "9.5");
      text.textContent = label;
      svg.appendChild(text);
    });

    series.forEach((s, si) => {
      const color = s.color || ["#35f0d0", "#8b7bff", "#c8ff4d", "#ff4d8d"][si % 4];
      const points = s.values.map((v, i) => [x(i), y(v ?? 0)]);
      const d = points.map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
      if (area) {
        const gradId = `g${Math.random().toString(36).slice(2, 8)}`;
        const defs = document.createElementNS(NS, "defs");
        const grad = document.createElementNS(NS, "linearGradient");
        grad.setAttribute("id", gradId);
        grad.setAttribute("x1", "0");
        grad.setAttribute("y1", "0");
        grad.setAttribute("x2", "0");
        grad.setAttribute("y2", "1");
        const stop1 = document.createElementNS(NS, "stop");
        stop1.setAttribute("offset", "0%");
        stop1.setAttribute("stop-color", color);
        stop1.setAttribute("stop-opacity", "0.22");
        const stop2 = document.createElementNS(NS, "stop");
        stop2.setAttribute("offset", "100%");
        stop2.setAttribute("stop-color", color);
        stop2.setAttribute("stop-opacity", "0");
        grad.append(stop1, stop2);
        defs.appendChild(grad);
        svg.appendChild(defs);
        const areaPath = document.createElementNS(NS, "path");
        areaPath.setAttribute(
          "d",
          `${d} L${x(labels.length - 1).toFixed(1)},${pad.t + h} L${x(0).toFixed(1)},${pad.t + h} Z`
        );
        areaPath.setAttribute("fill", `url(#${gradId})`);
        svg.appendChild(areaPath);
      }
      const path = document.createElementNS(NS, "path");
      path.setAttribute("d", d);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", color);
      path.setAttribute("stroke-width", "2");
      path.setAttribute("stroke-linejoin", "round");
      path.setAttribute("stroke-linecap", "round");
      svg.appendChild(path);
    });

    const tip = tooltip(container);
    const hoverLine = document.createElementNS(NS, "line");
    hoverLine.setAttribute("stroke", "rgba(255,255,255,0.2)");
    hoverLine.setAttribute("y1", pad.t);
    hoverLine.setAttribute("y2", pad.t + h);
    hoverLine.style.opacity = "0";
    svg.appendChild(hoverLine);

    svg.addEventListener("mousemove", (event) => {
      const rect = svg.getBoundingClientRect();
      const px = ((event.clientX - rect.left) / rect.width) * width;
      const idx = Math.round(((px - pad.l) / w) * (labels.length - 1));
      if (idx < 0 || idx >= labels.length) return;
      hoverLine.setAttribute("x1", x(idx));
      hoverLine.setAttribute("x2", x(idx));
      hoverLine.style.opacity = "1";
      tip.innerHTML =
        `<b>${labels[idx]}</b><br>` +
        series
          .map(
            (s, si) =>
              `<span style="color:${s.color || ["#35f0d0", "#8b7bff", "#c8ff4d", "#ff4d8d"][si % 4]}">●</span> ${s.name}: <b>${yFormat(s.values[idx] ?? 0)}</b>`
          )
          .join("<br>");
      tip.style.left = `${(x(idx) / width) * 100}%`;
      tip.style.top = `${(y(Math.max(...series.map((s) => s.values[idx] ?? 0))) / height) * 100}%`;
      tip.classList.add("show");
    });
    svg.addEventListener("mouseleave", () => {
      tip.classList.remove("show");
      hoverLine.style.opacity = "0";
    });

    container.appendChild(svg);
  }

  function bars(container, opts) {
    const { labels, values, height = 200, color = "#35f0d0", yFormat = fmt, highlightMax = true } = opts;
    container.innerHTML = "";
    container.classList.add("chart-wrap");
    const width = Math.max(container.clientWidth || 640, 320);
    const pad = { l: 44, r: 10, t: 12, b: 26 };
    const w = width - pad.l - pad.r;
    const h = height - pad.t - pad.b;
    const max = niceMax(Math.max(...values, 1));
    const bw = Math.max(3, (w / values.length) * 0.62);
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", height);

    for (let i = 0; i <= 3; i++) {
      const gy = pad.t + h - (h / 3) * i;
      const grid = document.createElementNS(NS, "line");
      grid.setAttribute("x1", pad.l);
      grid.setAttribute("x2", width - pad.r);
      grid.setAttribute("y1", gy);
      grid.setAttribute("y2", gy);
      grid.setAttribute("stroke", "rgba(255,255,255,0.06)");
      svg.appendChild(grid);
      const text = document.createElementNS(NS, "text");
      text.setAttribute("x", pad.l - 8);
      text.setAttribute("y", gy + 3.5);
      text.setAttribute("text-anchor", "end");
      text.setAttribute("fill", "#4d5666");
      text.setAttribute("font-size", "9.5");
      text.textContent = yFormat((max / 3) * i);
      svg.appendChild(text);
    }

    const maxIdx = values.indexOf(Math.max(...values));
    values.forEach((v, i) => {
      const bh = (v / max) * h;
      const bx = pad.l + (i + 0.5) * (w / values.length) - bw / 2;
      const rect = document.createElementNS(NS, "rect");
      rect.setAttribute("x", bx);
      rect.setAttribute("y", pad.t + h - bh);
      rect.setAttribute("width", bw);
      rect.setAttribute("height", Math.max(bh, 1));
      rect.setAttribute("rx", "3");
      rect.setAttribute("fill", highlightMax && i === maxIdx ? "#c8ff4d" : color);
      rect.setAttribute("opacity", highlightMax && i === maxIdx ? "1" : "0.55");
      svg.appendChild(rect);
      if (labels.length <= 16 || i % 2 === 0) {
        const text = document.createElementNS(NS, "text");
        text.setAttribute("x", bx + bw / 2);
        text.setAttribute("y", height - 8);
        text.setAttribute("text-anchor", "middle");
        text.setAttribute("fill", "#4d5666");
        text.setAttribute("font-size", "9.5");
        text.textContent = labels[i];
        svg.appendChild(text);
      }
    });
    container.appendChild(svg);
  }

  function sparkline(container, values, color = "#35f0d0") {
    container.innerHTML = "";
    const width = Math.max(container.clientWidth || 160, 80);
    const height = 34;
    const max = Math.max(...values, 1);
    const min = Math.min(...values, 0);
    const x = (i) => (i / Math.max(values.length - 1, 1)) * width;
    const y = (v) => height - 3 - ((v - min) / (max - min || 1)) * (height - 6);
    const d = values.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", height);
    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", color);
    path.setAttribute("stroke-width", "1.6");
    path.setAttribute("stroke-linecap", "round");
    svg.appendChild(path);
    container.appendChild(svg);
  }

  function donut(container, segments, opts = {}) {
    container.innerHTML = "";
    const size = opts.size || 150;
    const stroke = opts.stroke || 14;
    const r = (size - stroke) / 2;
    const c = 2 * Math.PI * r;
    const total = segments.reduce((sum, s) => sum + s.value, 0) || 1;
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
    svg.setAttribute("width", size);
    svg.setAttribute("height", size);
    let offset = 0;
    segments.forEach((s) => {
      const circle = document.createElementNS(NS, "circle");
      circle.setAttribute("cx", size / 2);
      circle.setAttribute("cy", size / 2);
      circle.setAttribute("r", r);
      circle.setAttribute("fill", "none");
      circle.setAttribute("stroke", s.color);
      circle.setAttribute("stroke-width", stroke);
      circle.setAttribute("stroke-dasharray", `${(s.value / total) * c} ${c}`);
      circle.setAttribute("stroke-dashoffset", -offset);
      circle.setAttribute("transform", `rotate(-90 ${size / 2} ${size / 2})`);
      circle.setAttribute("stroke-linecap", "butt");
      svg.appendChild(circle);
      offset += (s.value / total) * c;
    });
    container.appendChild(svg);
  }

  return { line, bars, sparkline, donut, fmt };
})();
