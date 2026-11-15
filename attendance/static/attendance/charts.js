/* Dependency-free canvas charts for the dashboard (no CDN needed). */
(function () {
  "use strict";
  var el = document.getElementById("chart-data");
  if (!el) { return; }
  var data = JSON.parse(el.textContent);
  var COL = { ontime: "#19b3a6", late: "#ff9a3d", absent: "#f03e7e", leave: "#8b6cf0" };
  var INK = "#2b3550", MUTED = "#8a94a8", GRID = "#e6eaf2";
  var FONT = '12px "Segoe UI", system-ui, sans-serif';

  var tip = document.createElement("div");
  tip.id = "chart-tip";
  document.body.appendChild(tip);

  var registry = {};   // canvas id -> {draw: fn, hits: []}

  function setup(canvas) {
    var box = canvas.parentNode.getBoundingClientRect();
    var dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.round(box.width * dpr));
    canvas.height = Math.max(1, Math.round(box.height * dpr));
    var ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, box.width, box.height);
    ctx.font = FONT;
    return { ctx: ctx, w: box.width, h: box.height };
  }

  function rrect(ctx, x, y, w, h, r) {
    r = Math.min(r, w / 2, Math.abs(h));
    ctx.beginPath();
    ctx.moveTo(x, y + h);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h);
    ctx.closePath();
  }

  function empty(s, msg) {
    s.ctx.fillStyle = MUTED;
    s.ctx.textAlign = "center";
    s.ctx.fillText(msg, s.w / 2, s.h / 2);
  }

  function niceTop(max) {
    var step = Math.max(1, Math.ceil(max / 4));
    return { step: step, top: step * 4 };
  }

  function axes(s, pad, top, step, fmt) {
    var ctx = s.ctx;
    ctx.strokeStyle = GRID;
    ctx.fillStyle = MUTED;
    ctx.textAlign = "right";
    ctx.lineWidth = 1;
    for (var i = 0; i <= 4; i++) {
      var y = pad.t + (s.h - pad.t - pad.b) * (1 - i / 4);
      ctx.beginPath();
      ctx.moveTo(pad.l, y + 0.5);
      ctx.lineTo(s.w - pad.r, y + 0.5);
      ctx.stroke();
      ctx.fillText(fmt ? fmt(step * i) : String(step * i), pad.l - 8, y + 4);
    }
  }

  /* ---------- grouped bars ---------- */
  function drawBars(canvas, items) {
    var s = setup(canvas), ctx = s.ctx, hits = [];
    if (!items.length) { empty(s, "No data yet"); return hits; }
    var pad = { l: 32, r: 8, t: 10, b: 26 };
    var max = 0;
    items.forEach(function (d) { max = Math.max(max, d.on_time, d.late, d.absent, d.leave); });
    var n = niceTop(max);
    axes(s, pad, n.top, n.step);
    var plotW = s.w - pad.l - pad.r, plotH = s.h - pad.t - pad.b;
    var groupW = plotW / items.length;
    var barW = Math.max(2, Math.min(14, (groupW * 0.8) / 4));
    var keys = [["on_time", COL.ontime], ["late", COL.late], ["absent", COL.absent], ["leave", COL.leave]];
    var every = Math.ceil(items.length / Math.max(1, Math.floor(plotW / 54)));
    items.forEach(function (d, i) {
      var gx = pad.l + groupW * i + (groupW - barW * 4) / 2;
      keys.forEach(function (k, j) {
        var h = (d[k[0]] / n.top) * plotH;
        if (h > 0) {
          ctx.fillStyle = k[1];
          rrect(ctx, gx + j * barW, pad.t + plotH - h, barW - 1, h, 3);
          ctx.fill();
        }
      });
      if (i % every === 0) {
        ctx.fillStyle = MUTED;
        ctx.textAlign = "center";
        ctx.fillText(d.label, pad.l + groupW * i + groupW / 2, s.h - 8);
      }
      hits.push({ x0: pad.l + groupW * i, x1: pad.l + groupW * (i + 1), y0: 0, y1: s.h,
        text: d.label + "\nOn time: " + d.on_time + "\nLate: " + d.late + "\nAbsent: " + d.absent + "\nOn leave: " + d.leave });
    });
    return hits;
  }

  /* ---------- line (present %) ---------- */
  function drawLine(canvas, items) {
    var s = setup(canvas), ctx = s.ctx, hits = [];
    var pts = [];
    items.forEach(function (d, i) {
      var den = d.on_time + d.late + d.absent;
      pts.push({ i: i, label: d.label, v: den ? Math.round(100 * (d.on_time + d.late) / den) : null });
    });
    if (!pts.some(function (p) { return p.v !== null; })) { empty(s, "No data yet"); return hits; }
    var pad = { l: 38, r: 12, t: 12, b: 26 };
    axes(s, pad, 100, 25, function (v) { return v + "%"; });
    var plotW = s.w - pad.l - pad.r, plotH = s.h - pad.t - pad.b;
    var stepX = items.length > 1 ? plotW / (items.length - 1) : 0;
    function X(i) { return pad.l + (items.length > 1 ? stepX * i : plotW / 2); }
    function Y(v) { return pad.t + plotH * (1 - v / 100); }
    var real = pts.filter(function (p) { return p.v !== null; });
    var grad = ctx.createLinearGradient(0, pad.t, 0, pad.t + plotH);
    grad.addColorStop(0, "rgba(25,179,166,.35)");
    grad.addColorStop(1, "rgba(25,179,166,0)");
    ctx.beginPath();
    real.forEach(function (p, k) { if (k === 0) { ctx.moveTo(X(p.i), Y(p.v)); } else { ctx.lineTo(X(p.i), Y(p.v)); } });
    ctx.strokeStyle = COL.ontime; ctx.lineWidth = 2.5; ctx.lineJoin = "round"; ctx.stroke();
    ctx.lineTo(X(real[real.length - 1].i), pad.t + plotH);
    ctx.lineTo(X(real[0].i), pad.t + plotH);
    ctx.closePath(); ctx.fillStyle = grad; ctx.fill();
    var every = Math.ceil(items.length / Math.max(1, Math.floor(plotW / 54)));
    pts.forEach(function (p) {
      if (p.v !== null) {
        ctx.beginPath(); ctx.arc(X(p.i), Y(p.v), 3.5, 0, Math.PI * 2);
        ctx.fillStyle = "#fff"; ctx.fill(); ctx.strokeStyle = COL.ontime; ctx.lineWidth = 2; ctx.stroke();
      }
      if (p.i % every === 0) {
        ctx.fillStyle = MUTED; ctx.textAlign = "center"; ctx.fillText(p.label, X(p.i), s.h - 8);
      }
      var half = stepX ? stepX / 2 : plotW / 2;
      hits.push({ x0: X(p.i) - half, x1: X(p.i) + half, y0: 0, y1: s.h,
        text: p.label + "\nPresent: " + (p.v === null ? "no data" : p.v + "%") });
    });
    return hits;
  }

  /* ---------- donut ---------- */
  function drawDonut(canvas, parts) {
    var s = setup(canvas), ctx = s.ctx, hits = [];
    var total = parts.reduce(function (a, p) { return a + p.value; }, 0);
    var cx = s.w / 2, cy = s.h / 2, R = Math.min(s.w, s.h) / 2 - 8, r = R * 0.62;
    if (!total) {
      ctx.beginPath(); ctx.arc(cx, cy, (R + r) / 2, 0, Math.PI * 2);
      ctx.lineWidth = R - r; ctx.strokeStyle = GRID; ctx.stroke();
      ctx.fillStyle = MUTED; ctx.textAlign = "center"; ctx.fillText("No employees", cx, cy + 4);
      return hits;
    }
    var a = -Math.PI / 2;
    parts.forEach(function (p) {
      if (!p.value) { return; }
      var da = (p.value / total) * Math.PI * 2;
      ctx.beginPath();
      ctx.arc(cx, cy, R, a, a + da);
      ctx.arc(cx, cy, r, a + da, a, true);
      ctx.closePath();
      ctx.fillStyle = COL[p.key]; ctx.fill();
      ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.stroke();
      a += da;
    });
    var here = parts[0].value + parts[1].value;
    ctx.fillStyle = INK; ctx.textAlign = "center";
    ctx.font = 'bold 26px "Segoe UI", system-ui, sans-serif';
    ctx.fillText(Math.round(100 * here / total) + "%", cx, cy + 6);
    ctx.font = FONT; ctx.fillStyle = MUTED; ctx.fillText("present", cx, cy + 24);
    hits.push({ x0: cx - R, x1: cx + R, y0: cy - R, y1: cy + R,
      text: parts.map(function (p) { return p.label + ": " + p.value; }).join("\n") });
    return hits;
  }

  /* ---------- horizontal bars (departments) ---------- */
  function drawHBars(canvas, items) {
    var s = setup(canvas), ctx = s.ctx, hits = [];
    if (!items.length) { empty(s, "No data yet"); return hits; }
    items = items.slice().sort(function (a, b) { return b.rate - a.rate; }).slice(0, 7);
    var rowH = Math.min(30, (s.h - 8) / items.length), labelW = 92;
    var max = Math.max(10, Math.ceil(Math.max.apply(null, items.map(function (d) { return d.rate; })) / 5) * 5);
    items.forEach(function (d, i) {
      var y = 4 + i * rowH, bw = (s.w - labelW - 46) * (d.rate / max);
      var name = d.department.length > 13 ? d.department.slice(0, 12) + "…" : d.department;
      ctx.fillStyle = INK; ctx.textAlign = "left"; ctx.fillText(name, 0, y + rowH / 2 + 4);
      ctx.fillStyle = "#f1f4fa"; rrect(ctx, labelW, y + 5, s.w - labelW - 46, rowH - 10, 4); ctx.fill();
      if (bw > 0) { ctx.fillStyle = COL.absent; rrect(ctx, labelW, y + 5, Math.max(bw, 4), rowH - 10, 4); ctx.fill(); }
      ctx.fillStyle = MUTED; ctx.textAlign = "right"; ctx.fillText(d.rate + "%", s.w, y + rowH / 2 + 4);
      hits.push({ x0: 0, x1: s.w, y0: y, y1: y + rowH,
        text: d.department + "\nAbsent " + d.absent + " of " + d.expected + " days (" + d.rate + "%)" });
    });
    return hits;
  }

  /* ---------- simple vertical bars (tardiness by weekday) ---------- */
  function drawSimple(canvas, items) {
    var s = setup(canvas), ctx = s.ctx, hits = [];
    if (!items.length) { empty(s, "No data yet"); return hits; }
    var pad = { l: 28, r: 6, t: 14, b: 24 };
    var max = 0; items.forEach(function (d) { max = Math.max(max, d.late); });
    var n = niceTop(max);
    axes(s, pad, n.top, n.step);
    var plotW = s.w - pad.l - pad.r, plotH = s.h - pad.t - pad.b, gw = plotW / items.length;
    var bw = Math.min(26, gw * 0.55);
    items.forEach(function (d, i) {
      var h = (d.late / n.top) * plotH, x = pad.l + gw * i + (gw - bw) / 2;
      if (h > 0) { ctx.fillStyle = COL.late; rrect(ctx, x, pad.t + plotH - h, bw, h, 4); ctx.fill(); }
      ctx.fillStyle = MUTED; ctx.textAlign = "center"; ctx.fillText(d.label, x + bw / 2, s.h - 7);
      if (d.late) { ctx.fillStyle = INK; ctx.fillText(String(d.late), x + bw / 2, pad.t + plotH - h - 4); }
      hits.push({ x0: pad.l + gw * i, x1: pad.l + gw * (i + 1), y0: 0, y1: s.h, text: d.label + ": " + d.late + " late" });
    });
    return hits;
  }

  /* ---------- wiring ---------- */
  function register(id, fn) {
    var canvas = document.getElementById(id);
    if (!canvas) { return null; }
    var entry = { canvas: canvas, fn: fn, hits: [] };
    registry[id] = entry;
    canvas.addEventListener("mousemove", function (ev) {
      var r = canvas.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top, hit = null;
      for (var i = 0; i < entry.hits.length; i++) {
        var h = entry.hits[i];
        if (x >= h.x0 && x <= h.x1 && y >= h.y0 && y <= h.y1) { hit = h; break; }
      }
      if (!hit) { tip.style.display = "none"; return; }
      tip.textContent = hit.text;
      tip.style.display = "block";
      tip.style.left = Math.min(ev.clientX + 14, window.innerWidth - 170) + "px";
      tip.style.top = (ev.clientY + 14) + "px";
    });
    canvas.addEventListener("mouseleave", function () { tip.style.display = "none"; });
    return entry;
  }

  var mode = "bars";   // "bars" | "line"
  var rangeSel = document.getElementById("trend-range");
  var modeBtn = document.getElementById("trend-mode");
  var legend = document.getElementById("trend-legend");
  var title = document.getElementById("trend-title");
  var hint = document.getElementById("trend-hint");

  function trendItems() {
    var all = data.trend || [];
    if (mode === "line") { return all; }
    var n = parseInt(rangeSel.value, 10) || 14;
    return all.slice(Math.max(0, all.length - n));
  }

  register("trendChart", function (c) {
    return mode === "line" ? drawLine(c, trendItems()) : drawBars(c, trendItems());
  });
  register("donutChart", function (c) { return drawDonut(c, data.donut || []); });
  register("deptChart", function (c) { return drawHBars(c, data.dept || []); });
  register("tardyChart", function (c) { return drawSimple(c, data.tardy || []); });

  function redraw() {
    Object.keys(registry).forEach(function (id) {
      var e = registry[id];
      e.hits = e.fn(e.canvas) || [];
    });
  }

  if (rangeSel) { rangeSel.addEventListener("change", redraw); }
  if (modeBtn) {
    modeBtn.addEventListener("click", function () {
      mode = mode === "bars" ? "line" : "bars";
      modeBtn.textContent = mode === "bars" ? "view monthly" : "view daily";
      rangeSel.disabled = mode === "line";
      legend.style.display = mode === "line" ? "none" : "";
      title.textContent = mode === "line" ? "Monthly attendance" : "Attendance trend";
      hint.textContent = mode === "line" ? "Present % of expected staff · last 30 days" : "Employees per day by status";
      redraw();
    });
  }
  var timer = null;
  window.addEventListener("resize", function () { clearTimeout(timer); timer = setTimeout(redraw, 120); });
  redraw();

  /* ---------- live feed ---------- */
  var feed = document.getElementById("feed");
  if (feed && window.fetch) {
    setInterval(function () {
      if (document.hidden) { return; }
      fetch(feed.getAttribute("data-url"), { credentials: "same-origin", headers: { "X-Requested-With": "fetch" } })
        .then(function (r) { return r.ok && !r.redirected ? r.text() : null; })
        .then(function (html) { if (html) { feed.innerHTML = html; } })
        .catch(function () { /* offline: keep the old rows */ });
    }, 10000);
  }
})();
