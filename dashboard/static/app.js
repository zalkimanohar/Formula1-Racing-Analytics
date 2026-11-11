/* Formula 1 in numbers - interactions. Data: window.F1 (built by build_web_data.py). */
(() => {
  "use strict";

  const D = window.F1;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const fmt = (n) => Math.round(n).toLocaleString("en-GB");
  const dash = (a, b) => (a === b ? `${a}` : `${a}–${b}`);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const INK = "#ecebe6", INK2 = "#b4b7bf", INK3 = "#7d828d", LINE = "#2a2e36", SOFT = "#22252b", PURPLE = "#b26bff";
  const UI_FONT = "Titillium Web, Segoe UI, sans-serif";
  const TEAM_COLORS = {
    Ferrari: "#d9002a", Williams: "#3d93d6", McLaren: "#d96a00", Lotus: "#2f9e57",
    "Red Bull": "#3a5fc4", Renault: "#b88a00", Mercedes: "#00a896", Other: "#4a4e57",
  };
  const teamColor = (t) => TEAM_COLORS[t] || "#666b76";
  const driverName = (id) => (D.drivers[id] ? D.drivers[id].n : id);

  const state = { from: D.kpi.first, to: D.kpi.last, metric: "wins" };
  const rangeListeners = [];
  const onRange = (fn) => rangeListeners.push(fn);

  // ------------------------------------------------------------------------------------------
  // Hero: start lights, then lights out
  // ------------------------------------------------------------------------------------------
  $$("[data-k]").forEach((el) => { el.textContent = fmt(D.kpi[el.dataset.k]); });

  function runCounters() {
    $$("[data-count]").forEach((el) => {
      const target = D.kpi[el.dataset.count];
      if (reduceMotion) { el.textContent = fmt(target); return; }
      const t0 = performance.now(), dur = 1500;
      const step = (now) => {
        const p = Math.min(1, (now - t0) / dur);
        el.textContent = fmt(target * (1 - Math.pow(1 - p, 4)));
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  }

  let startTimers = [];
  function startSequence() {
    startTimers.forEach(clearTimeout);
    startTimers = [];
    const pods = $$(".pod");
    document.body.classList.remove("lights-out");
    pods.forEach((p) => p.classList.remove("on"));
    if (reduceMotion) { document.body.classList.add("lights-out"); runCounters(); return; }
    pods.forEach((p, i) => startTimers.push(setTimeout(() => p.classList.add("on"), 500 + i * 750)));
    const lightsOut = 500 + 4 * 750 + 900 + Math.random() * 1100;
    startTimers.push(setTimeout(() => {
      pods.forEach((p) => p.classList.remove("on"));
      document.body.classList.add("lights-out");
      runCounters();
    }, lightsOut));
  }
  $("#replay").addEventListener("click", startSequence);
  startSequence();

  // In-page links scroll instead of navigating (the page may run inside an embedding frame).
  document.addEventListener("click", (e) => {
    const a = e.target.closest('a[href^="#"]');
    if (!a) return;
    const target = document.querySelector(a.getAttribute("href"));
    if (!target) return;
    e.preventDefault();
    target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  });

  // ------------------------------------------------------------------------------------------
  // Season range (pit wall bar)
  // ------------------------------------------------------------------------------------------
  function initRange() {
    const from = $("#from"), to = $("#to"), sel = $("#range-sel");
    [from, to].forEach((i) => { i.min = D.kpi.first; i.max = D.kpi.last; });
    from.value = state.from;
    to.value = state.to;
    const span = D.kpi.last - D.kpi.first;
    const paint = () => {
      const a = +from.value, b = +to.value;
      sel.style.left = `${((a - D.kpi.first) / span) * 100}%`;
      sel.style.right = `${((D.kpi.last - b) / span) * 100}%`;
      $("#from-out").textContent = a;
      $("#to-out").textContent = b;
      $$("[data-scope]").forEach((el) => { el.textContent = dash(a, b); });
    };
    let pending;
    const update = (e) => {
      if (+from.value > +to.value) {
        if (e.target === from) from.value = to.value; else to.value = from.value;
      }
      paint();
      clearTimeout(pending);
      pending = setTimeout(() => {
        state.from = +from.value;
        state.to = +to.value;
        rangeListeners.forEach((fn) => fn());
      }, 140);
    };
    from.addEventListener("input", update);
    to.addEventListener("input", update);
    paint();
  }
  initRange();

  // nav highlight
  const navLinks = $$(".pitwall nav a");
  const navIO = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) navLinks.forEach((a) => a.classList.toggle("active", a.hash === `#${e.target.id}`));
    });
  }, { rootMargin: "-45% 0px -50% 0px" });
  $$(".chapter").forEach((s) => navIO.observe(s));

  // ------------------------------------------------------------------------------------------
  // Shared chart helpers
  // ------------------------------------------------------------------------------------------
  const charts = [];
  function makeChart(el) {
    const c = echarts.init(el, null, { renderer: "canvas" });
    charts.push(c);
    return c;
  }
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => charts.forEach((c) => c.resize()), 120);
  });

  const tooltipBase = {
    backgroundColor: "rgba(14,15,18,0.96)", borderColor: "#343944", borderWidth: 1, padding: [10, 12],
    textStyle: { color: INK, fontFamily: UI_FONT, fontSize: 13 },
    extraCssText: "border-radius:10px;box-shadow:0 14px 34px rgba(0,0,0,.5);",
  };
  const axisLabel = { color: INK3, fontFamily: UI_FONT, fontSize: 12 };
  const swatch = (c) => `<span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:${c};margin-right:7px"></span>`;

  function lazy(id, init) {
    const el = document.getElementById(id);
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { io.disconnect(); init(el); }
    }, { rootMargin: "400px 0px" });
    io.observe(el);
  }

  function rolling(arr, w) {
    const h = Math.floor(w / 2);
    return arr.map((_, i) => {
      let s = 0, n = 0;
      for (let j = i - h; j <= i + h; j++) if (j >= 0 && j < arr.length) { s += arr[j]; n++; }
      return s / n;
    });
  }

  const seasonLabels = D.seasons.map(String);
  function shadeOutside() {
    const out = [];
    if (state.from > D.kpi.first) out.push([{ xAxis: String(D.kpi.first) }, { xAxis: String(state.from) }]);
    if (state.to < D.kpi.last) out.push([{ xAxis: String(state.to) }, { xAxis: String(D.kpi.last) }]);
    return out;
  }

  /** Stacked 100% area with labels placed inside each band at its widest season. */
  function stackedShare(el, { groups, colors, rows, smooth, tooltip, labelMin = 9, emphasise = null, marker = null }) {
    const c = makeChart(el);
    const totals = rows.map((r) => r.reduce((a, b) => a + b, 0));
    const raw = groups.map((_, j) => rows.map((r, i) => (totals[i] ? (r[j] / totals[i]) * 100 : 0)));
    const sm = raw.map((s) => rolling(s, smooth));
    const sums = D.seasons.map((_, i) => sm.reduce((a, s) => a + s[i], 0));
    const share = sm.map((s) => s.map((v, i) => (sums[i] ? +((v / sums[i]) * 100).toFixed(2) : 0)));
    const series = groups.map((g, j) => ({
      name: g, type: "line", stack: "share", smooth: 0.35, symbol: "none", color: colors[j], lineStyle: { width: 0 },
      areaStyle: { color: colors[j], opacity: emphasise && !emphasise.includes(g) ? 0.85 : 0.97 },
      emphasis: { focus: "series" }, data: share[j],
    }));
    series[series.length - 1].markArea = { silent: true, itemStyle: { color: "rgba(17,19,22,0.74)" }, data: shadeOutside() };
    if (marker) {
      series[0].markLine = {
        silent: true, symbol: "none", lineStyle: { color: INK, width: 1, type: "solid", opacity: 0.8 },
        label: { formatter: marker.text, position: "end", align: "right", distance: 8, color: INK, fontFamily: UI_FONT,
          fontSize: 12, fontWeight: 600, backgroundColor: "rgba(17,19,22,0.9)", padding: [4, 8], borderRadius: 6 },
        data: [{ xAxis: String(marker.season) }],
      };
    }
    c.setOption({
      animation: !reduceMotion, animationDuration: 1800, animationEasing: "cubicOut",
      grid: { left: 48, right: 18, top: 52, bottom: 34 },
      legend: { top: 0, left: 0, icon: "roundRect", itemWidth: 12, itemHeight: 12, itemGap: 18,
        textStyle: { color: INK2, fontFamily: UI_FONT, fontSize: 13 } },
      tooltip: { ...tooltipBase, trigger: "axis", axisPointer: { type: "line", lineStyle: { color: "#6b7080" } },
        formatter: (ps) => tooltip(ps[0].dataIndex, totals) },
      xAxis: { type: "category", boundaryGap: false, data: seasonLabels, axisTick: { show: false },
        axisLine: { lineStyle: { color: LINE } },
        axisLabel: { ...axisLabel, interval: (i) => D.seasons[i] % 10 === 0 } },
      yAxis: { type: "value", max: 100, splitNumber: 4, axisLabel: { ...axisLabel, formatter: "{value}%" },
        splitLine: { lineStyle: { color: SOFT } } },
      series,
    });
    const place = () => {
      const g = [];
      const margin = Math.ceil(D.seasons.length * 0.06);
      groups.forEach((name, j) => {
        let best = margin;
        share[j].forEach((v, i) => {
          if (i >= margin && i < share[j].length - margin && v > share[j][best]) best = i;
        });
        if (share[j][best] < labelMin) return;
        const below = share.slice(0, j).reduce((a, s) => a + s[best], 0);
        const [x, y] = c.convertToPixel({ gridIndex: 0 }, [best, below + share[j][best] / 2]);
        g.push({ type: "text", x, y, silent: true, z: 10,
          style: { text: name, fill: "#ffffff", font: `700 13px ${UI_FONT}`, align: "center", verticalAlign: "middle",
            textShadowColor: "rgba(0,0,0,0.55)", textShadowBlur: 6 } });
      });
      c.setOption({ graphic: g }, { replaceMerge: ["graphic"] });
    };
    setTimeout(place, reduceMotion ? 0 : 1900);
    charts.push({ resize: () => setTimeout(place, 60) });
    onRange(() => {
      const last = series.length - 1;
      const patch = groups.map((_, j) => (j === last ? { markArea: { data: shadeOutside() } } : {}));
      c.setOption({ series: patch });
    });
    return { chart: c, share, totals };
  }

  // ------------------------------------------------------------------------------------------
  // Eras
  // ------------------------------------------------------------------------------------------
  lazy("chart-eras", (el) => {
    const teams = D.eras.teams, rows = D.eras.rows;
    stackedShare(el, {
      groups: teams, colors: teams.map(teamColor), rows, smooth: 3,
      tooltip: (i, totals) => {
        const won = teams.map((t, j) => [t, rows[i][j]]).filter((x) => x[1] > 0).sort((a, b) => b[1] - a[1]);
        return `<b style="font-size:15px">${D.seasons[i]}</b> <span style="color:${INK3}">${totals[i]} races</span><br>` +
          won.map(([t, n]) => `${swatch(teamColor(t))}${t}<b style="float:right;margin-left:22px">${n}</b>`).join("<br>");
      },
    });
    let best = { share: 0 };
    rows.forEach((r, i) => {
      const total = r.reduce((a, b) => a + b, 0);
      teams.forEach((t, j) => {
        if (t === "Other" || !total) return;
        const s = r[j] / total;
        if (s > best.share || (s === best.share && r[j] > best.wins)) best = { share: s, wins: r[j], total, team: t, season: D.seasons[i] };
      });
    });
    const decades = [...new Set(D.seasons.map((s) => Math.floor(s / 10) * 10))];
    const everyDecade = teams.filter((t, j) => t !== "Other" &&
      decades.every((dec) => rows.some((r, i) => Math.floor(D.seasons[i] / 10) * 10 === dec && r[j] > 0)));
    $("#eras-finding").textContent =
      `${best.team} won ${best.wins} of ${best.total} races in ${best.season}, the most dominant season on record.` +
      (everyDecade.length === 1 ? ` ${everyDecade[0]} is the only constructor with a win in every decade since the 1950s.` : "");
  });

  // ------------------------------------------------------------------------------------------
  // Drivers: timing tower
  // ------------------------------------------------------------------------------------------
  const METRICS = {
    wins: { label: "Wins", idx: 3, fmt: (v) => fmt(v) },
    podiums: { label: "Podiums", idx: 4, fmt: (v) => fmt(v) },
    poles: { label: "Pole starts", idx: 5, fmt: (v) => fmt(v) },
    score: { label: "Era-adjusted", idx: 7, fmt: (v) => v.toFixed(1) },
    points: { label: "Points", idx: 6, fmt: (v) => fmt(v) },
  };

  function aggregate(from, to, metric, limit = 15) {
    const idx = METRICS[metric].idx;
    const total = new Map(), wins = new Map();
    for (const r of D.driverSeasons) {
      if (r[1] < from || r[1] > to) continue;
      total.set(r[0], (total.get(r[0]) || 0) + r[idx]);
      wins.set(r[0], (wins.get(r[0]) || 0) + r[3]);
    }
    return [...total].filter(([, v]) => v > 0)
      .sort((a, b) => b[1] - a[1] || wins.get(b[0]) - wins.get(a[0]))
      .slice(0, limit).map(([id, v]) => ({ id, v }));
  }

  const tower = $("#tower");
  const ROW = 46;
  const rows = new Map();
  function towerRow(id) {
    const d = D.drivers[id];
    const li = document.createElement("li");
    li.title = d.n;
    li.innerHTML = `<span class="pos"></span><span class="team" style="background:${teamColor(d.t)}"></span>` +
      `<span class="code">${esc(d.c)}</span><span class="name">${esc(d.n)}</span>` +
      `<span class="track"><span class="fill" style="background:${teamColor(d.t)}"></span></span><span class="val"></span>`;
    return li;
  }

  function renderTower(from, to) {
    const m = METRICS[state.metric];
    const list = aggregate(from, to, state.metric);
    const keep = new Set(list.map((d) => d.id));
    rows.forEach((li, id) => {
      if (keep.has(id)) return;
      li.classList.add("leaving");
      rows.delete(id);
      setTimeout(() => li.remove(), 360);
    });
    const max = list.length ? list[0].v : 1;
    list.forEach((d, i) => {
      let li = rows.get(d.id);
      if (!li) {
        li = towerRow(d.id);
        li.classList.add("entering");
        li.style.transform = `translateY(${(i + 1) * ROW}px)`;
        tower.appendChild(li);
        rows.set(d.id, li);
        requestAnimationFrame(() => requestAnimationFrame(() => li.classList.remove("entering")));
      }
      li.style.transform = `translateY(${i * ROW}px)`;
      li.querySelector(".pos").textContent = i + 1;
      li.querySelector(".fill").style.width = `${(d.v / max) * 100}%`;
      li.querySelector(".val").textContent = m.fmt(d.v);
      li.classList.toggle("leader", i === 0);
    });
    tower.style.height = `${Math.max(list.length, 1) * ROW}px`;
    $("#metric-head").textContent = m.label;
    $("#season-badge").textContent = to;
    $("#season-caption").textContent = `Totals for ${dash(from, to)}`;
    const note = $("#tower-note");
    if (!list.length) { note.textContent = "No results in this range."; return; }
    const leader = list[0];
    let text = `<b>${esc(driverName(leader.id))}</b> leads with ${m.fmt(leader.v)} ${m.label.toLowerCase()}` +
      `${state.metric === "score" ? " race-win equivalents" : ""} in ${dash(from, to)}.`;
    if (state.metric === "score" || state.metric === "points") {
      const byScore = aggregate(from, to, "score", 999).map((d) => d.id);
      const byPoints = aggregate(from, to, "points", 999).map((d) => d.id);
      const mover = byScore.slice(0, 15).map((id) => [id, byPoints.indexOf(id) - byScore.indexOf(id)])
        .sort((a, b) => b[1] - a[1])[0];
      if (mover && mover[1] > 3) {
        text += ` Adjusting for era lifts <b>${esc(driverName(mover[0]))}</b> from ${byPoints.indexOf(mover[0]) + 1}th on raw points ` +
          `to ${byScore.indexOf(mover[0]) + 1}th.`;
      }
    }
    note.innerHTML = text;
  }

  let playTimer = null;
  function stopPlay() {
    clearTimeout(playTimer);
    playTimer = null;
    const b = $("#play");
    b.setAttribute("aria-pressed", "false");
    b.textContent = "Replay history";
    renderTower(state.from, state.to);
  }
  $("#play").addEventListener("click", () => {
    if (playTimer) { stopPlay(); return; }
    const b = $("#play");
    b.setAttribute("aria-pressed", "true");
    b.textContent = "Pause";
    let s = state.from;
    const tick = () => {
      renderTower(state.from, s);
      s += 1;
      if (s > state.to) { playTimer = null; b.setAttribute("aria-pressed", "false"); b.textContent = "Replay history"; return; }
      playTimer = setTimeout(tick, reduceMotion ? 150 : 430);
    };
    tick();
  });
  $$("#metric button").forEach((btn) => btn.addEventListener("click", () => {
    $$("#metric button").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
    state.metric = btn.dataset.m;
    if (playTimer) stopPlay(); else renderTower(state.from, state.to);
  }));
  renderTower(state.from, state.to);
  onRange(() => { if (playTimer) stopPlay(); else renderTower(state.from, state.to); });

  // ------------------------------------------------------------------------------------------
  // The grid: start vs finish
  // ------------------------------------------------------------------------------------------
  const FIN_ROWS = ["Not classified", "21st or lower"].concat(Array.from({ length: 20 }, (_, i) => String(20 - i)));
  const finRow = (f) => (f === 0 ? 0 : f === 21 ? 1 : 22 - f);
  const ordinal = (n) => n + (["th", "st", "nd", "rd"][((n % 100) - 20) % 10] || ["th", "st", "nd", "rd"][n % 100] || "th");

  function gridCounts(from, to) {
    const counts = Array.from({ length: 20 }, () => new Array(22).fill(0));
    for (const [s, g, f, n] of D.gridFinish) if (s >= from && s <= to) counts[g - 1][f] += n;
    return counts;
  }

  lazy("chart-heat", (el) => {
    const c = makeChart(el);
    const ramp = ["#1d2026", "#2c2449", "#40307a", "#5a3faf", "#7b55df", "#a07cf7", "#c9b2ff", "#efe6ff"];
    const draw = () => {
      const counts = gridCounts(state.from, state.to);
      const data = [];
      counts.forEach((row, g) => {
        const starters = row.reduce((a, b) => a + b, 0);
        row.forEach((n, f) => {
          if (!starters) return;
          data.push([g, finRow(f), +((n / starters) * 100).toFixed(2), n, starters]);
        });
      });
      c.setOption({
        animation: !reduceMotion,
        grid: { left: 108, right: 16, top: 16, bottom: 58 },
        tooltip: { ...tooltipBase, formatter: (p) => {
          const [g, r, v, n, st] = p.value;
          const label = r === 0 ? "were not classified" : r === 1 ? "finished 21st or lower" : `finished ${ordinal(22 - r)}`;
          return `<b>From ${ordinal(g + 1)} on the grid</b><br>${v.toFixed(1)}% ${label}<br><span style="color:${INK3}">${fmt(n)} of ${fmt(st)} starts</span>`;
        } },
        xAxis: { type: "category", data: Array.from({ length: 20 }, (_, i) => String(i + 1)), name: "Starting position",
          nameLocation: "middle", nameGap: 36, nameTextStyle: { color: INK3, fontFamily: UI_FONT },
          axisLine: { show: false }, axisTick: { show: false }, axisLabel, splitArea: { show: false } },
        yAxis: { type: "category", data: FIN_ROWS, axisLine: { show: false }, axisTick: { show: false },
          axisLabel: { ...axisLabel, formatter: (v) => (/^\d+$/.test(v) ? `P${v}` : v) } },
        visualMap: { min: 0, max: 40, dimension: 2, calculable: false, show: false, inRange: { color: ramp } },
        series: [{ type: "heatmap", data, itemStyle: { borderColor: "#16181c", borderWidth: 1.5, borderRadius: 2 },
          emphasis: { itemStyle: { borderColor: INK, borderWidth: 1.5 } } }],
      });
      const poleStarts = counts[0].reduce((a, b) => a + b, 0);
      const wins = counts.reduce((a, row) => a + row[1], 0);
      $("#pole-win").textContent = poleStarts ? `${Math.round((counts[0][1] / poleStarts) * 100)}%` : "n/a";
      $("#front-row").textContent = wins ? `${Math.round(((counts[0][1] + counts[1][1]) / wins) * 100)}%` : "n/a";
    };
    draw();
    onRange(draw);
  });

  lazy("chart-pole", (el) => {
    const c = makeChart(el);
    const dec = new Map();
    for (const [s, g, f, n] of D.gridFinish) {
      if (g !== 1) continue;
      const d = Math.floor(s / 10) * 10;
      const cur = dec.get(d) || [0, 0];
      cur[1] += n;
      if (f === 1) cur[0] += n;
      dec.set(d, cur);
    }
    const keys = [...dec.keys()].sort();
    const vals = keys.map((k) => +((dec.get(k)[0] / dec.get(k)[1]) * 100).toFixed(1));
    c.setOption({
      animation: !reduceMotion,
      grid: { left: 34, right: 12, top: 12, bottom: 22 },
      tooltip: { ...tooltipBase, trigger: "axis", formatter: (ps) => `<b>${ps[0].name}</b><br>${ps[0].value}% of poles converted` },
      xAxis: { type: "category", data: keys.map((k) => `${k}s`), axisTick: { show: false }, axisLine: { lineStyle: { color: LINE } },
        axisLabel: { ...axisLabel, fontSize: 11, formatter: (v) => `'${v.slice(2)}` } },
      yAxis: { type: "value", min: 0, max: 70, splitNumber: 2, axisLabel: { ...axisLabel, fontSize: 11, formatter: "{value}%" },
        splitLine: { lineStyle: { color: SOFT } } },
      series: [{ type: "line", data: vals, smooth: 0.3, symbol: "circle", symbolSize: 8, lineStyle: { color: PURPLE, width: 2 },
        itemStyle: { color: PURPLE, borderColor: "#1c1f24", borderWidth: 2 },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "rgba(178,107,255,0.28)" }, { offset: 1, color: "rgba(178,107,255,0)" }]) } }],
    });
  });

  $("#deep").innerHTML = D.deepWins.slice(0, 5).map(([who, race, season, grid]) =>
    `<li><span class="g">P${grid}</span><span><span class="who">${esc(who)}</span><span class="where">${esc(race)} ${season}</span></span></li>`).join("");

  // ------------------------------------------------------------------------------------------
  // Reliability
  // ------------------------------------------------------------------------------------------
  lazy("chart-rel", (el) => {
    const G = D.status.groups;
    const groups = ["Finished", "Mechanical failure", "Accident or collision", "Other"];
    const map = (r) => [r[0] + r[1], r[2], r[3], r[4] + r[5] + r[6] + r[7]];
    const rows = D.status.rows.map(map);
    stackedShare(el, {
      groups, colors: ["#3b4049", "#e2622d", "#9085e9", "#5a5f69"], rows, smooth: 5, labelMin: 6,
      marker: { season: 2023, text: "2023: retirement causes no longer recorded" },
      tooltip: (i, totals) => `<b style="font-size:15px">${D.seasons[i]}</b> <span style="color:${INK3}">${fmt(totals[i])} starts</span><br>` +
        groups.map((g, j) => `${swatch(["#3b4049", "#e2622d", "#9085e9", "#5a5f69"][j])}${g}<b style="float:right;margin-left:22px">${((rows[i][j] / totals[i]) * 100).toFixed(0)}%</b>`).join("<br>"),
    });
    const decShare = (d0, j) => {
      let a = 0, t = 0;
      D.seasons.forEach((s, i) => { if (s >= d0 && s < d0 + 10) { a += rows[i][j]; t += rows[i].reduce((x, y) => x + y, 0); } });
      return t ? (a / t) * 100 : 0;
    };
    const m50 = decShare(1950, 1), m10 = decShare(2010, 1), f50 = decShare(1950, 0), f20 = decShare(2020, 0);
    $("#rel-finding").textContent =
      `The share of cars reaching the flag rose from ${f50.toFixed(0)}% in the 1950s to ${f20.toFixed(0)}% in the 2020s. ` +
      `Mechanical failures fell from ${m50.toFixed(0)}% of starters to ${m10.toFixed(0)}% in the 2010s, the last decade in which ` +
      `the source still recorded the cause of every retirement.`;
    void G;
  });

  // ------------------------------------------------------------------------------------------
  // Circuits: globe + list
  // ------------------------------------------------------------------------------------------
  const tip = $("#tip");
  const showTip = (html, x, y) => {
    tip.innerHTML = html;
    tip.hidden = false;
    const r = tip.getBoundingClientRect();
    tip.style.left = `${Math.min(window.innerWidth - r.width - 12, x + 16)}px`;
    tip.style.top = `${Math.max(12, y - r.height - 12)}px`;
  };
  const hideTip = () => { tip.hidden = true; };

  const circuitCount = (c) => c.seasons.filter((s) => s >= state.from && s <= state.to).length;
  let selectedCircuit = null;
  let globeApi = null;

  function renderCircuitCard(c) {
    const inRange = c.seasons.filter((s) => s >= state.from && s <= state.to);
    $("#circuit-card").innerHTML = `<h3>${esc(c.n)}</h3><p class="meta">${esc(c.loc)}, ${esc(c.country)}</p>` +
      `<div class="facts"><div><b>${inRange.length}</b><span>Grands Prix in ${dash(state.from, state.to)}</span></div>` +
      (inRange.length ? `<div><b>${inRange[0]}</b><span>first in range</span></div><div><b>${inRange[inRange.length - 1]}</b><span>last in range</span></div>` : "") +
      `</div>` + (c.king ? `<p class="meta" style="margin:14px 0 0">Most wins here: <b style="color:${INK}">${esc(c.king[0])}</b>, ${c.king[1]}</p>` : "");
  }

  function renderCircuitList() {
    const list = D.circuits.map((c) => ({ c, n: circuitCount(c) })).filter((x) => x.n > 0).sort((a, b) => b.n - a.n);
    $("#circuit-list").innerHTML = list.map((x, i) =>
      `<li><button type="button" data-id="${x.c.id}" aria-current="${selectedCircuit === x.c.id}"><span class="rk">${i + 1}</span>` +
      `<span>${esc(x.c.n)}<span class="ct">${esc(x.c.country)}</span></span><span class="gp">${x.n}</span></button></li>`).join("");
    $$("#circuit-list button").forEach((b) => b.addEventListener("click", () => selectCircuit(b.dataset.id, true)));
    if (!selectedCircuit || !list.some((x) => x.c.id === selectedCircuit)) {
      if (list.length) selectCircuit(list[0].c.id, false);
    }
  }

  function selectCircuit(id, rotate) {
    selectedCircuit = id;
    const c = D.circuits.find((x) => x.id === id);
    renderCircuitCard(c);
    $$("#circuit-list button").forEach((b) => b.setAttribute("aria-current", String(b.dataset.id === id)));
    if (globeApi) globeApi.focus(c, rotate);
  }

  lazy("globe", (el) => {
    const size = 640;
    const svg = d3.select(el).append("svg").attr("viewBox", `0 0 ${size} ${size}`);
    const proj = d3.geoOrthographic().scale(size / 2 - 14).translate([size / 2, size / 2]).rotate([-12, -30]).clipAngle(90).precision(0.6);
    const path = d3.geoPath(proj);
    const defs = svg.append("defs");
    const ocean = defs.append("radialGradient").attr("id", "ocean").attr("cx", "38%").attr("cy", "32%");
    ocean.append("stop").attr("offset", "0%").attr("stop-color", "#252a33");
    ocean.append("stop").attr("offset", "100%").attr("stop-color", "#101215");
    const glow = defs.append("filter").attr("id", "glow").attr("x", "-80%").attr("y", "-80%").attr("width", "260%").attr("height", "260%");
    glow.append("feGaussianBlur").attr("stdDeviation", 3.2).attr("result", "b");
    const merge = glow.append("feMerge");
    merge.append("feMergeNode").attr("in", "b");
    merge.append("feMergeNode").attr("in", "SourceGraphic");

    svg.append("circle").attr("cx", size / 2).attr("cy", size / 2).attr("r", size / 2 - 6)
      .attr("fill", "none").attr("stroke", "rgba(178,107,255,0.10)").attr("stroke-width", 10);
    const sphere = svg.append("path").datum({ type: "Sphere" }).attr("fill", "url(#ocean)").attr("stroke", "#30353e");
    const grat = svg.append("path").datum(d3.geoGraticule10()).attr("fill", "none").attr("stroke", "rgba(255,255,255,0.045)");
    const land = svg.append("path").datum(topojson.feature(WORLD, WORLD.objects.countries)).attr("fill", "#272b33");
    const borders = svg.append("path").datum(topojson.mesh(WORLD, WORLD.objects.countries, (a, b) => a !== b))
      .attr("fill", "none").attr("stroke", "#383d46").attr("stroke-width", 0.5);
    const dotsG = svg.append("g");

    let dragging = false, hovering = false, holdUntil = 0;
    const visible = (c) => d3.geoDistance([c.lon, c.lat], [-proj.rotate()[0], -proj.rotate()[1]]) < Math.PI / 2 - 0.02;

    function redraw() {
      sphere.attr("d", path);
      grat.attr("d", path);
      land.attr("d", path);
      borders.attr("d", path);
      const data = D.circuits.map((c) => ({ c, n: circuitCount(c) })).filter((x) => x.n > 0 && visible(x.c));
      const sel = dotsG.selectAll("circle").data(data, (d) => d.c.id);
      sel.exit().remove();
      sel.enter().append("circle")
        .attr("filter", "url(#glow)")
        .style("cursor", "pointer")
        .on("pointerenter", (ev, d) => { hovering = true; showTip(`<b>${esc(d.c.n)}</b><span>${esc(d.c.country)}, ${d.n} Grands Prix</span>`, ev.clientX, ev.clientY); })
        .on("pointermove", (ev, d) => showTip(`<b>${esc(d.c.n)}</b><span>${esc(d.c.country)}, ${d.n} Grands Prix</span>`, ev.clientX, ev.clientY))
        .on("pointerleave", () => { hovering = false; hideTip(); })
        .on("click", (ev, d) => selectCircuit(d.c.id, true))
        .merge(sel)
        .attr("cx", (d) => proj([d.c.lon, d.c.lat])[0])
        .attr("cy", (d) => proj([d.c.lon, d.c.lat])[1])
        .attr("r", (d) => 2.4 + Math.sqrt(d.n) * 1.35 + (d.c.id === selectedCircuit ? 2 : 0))
        .attr("fill", (d) => (d.c.id === selectedCircuit ? PURPLE : "#f4efe2"))
        .attr("fill-opacity", (d) => (d.c.id === selectedCircuit ? 1 : 0.86))
        .attr("stroke", (d) => (d.c.id === selectedCircuit ? "#ffffff" : "none"))
        .attr("stroke-width", 1.5);
    }

    svg.call(d3.drag()
      .on("start", () => { dragging = true; hideTip(); })
      .on("drag", (ev) => {
        const [l, p] = proj.rotate();
        proj.rotate([l + ev.dx * 0.28, Math.max(-75, Math.min(75, p - ev.dy * 0.28))]);
        redraw();
      })
      .on("end", () => { dragging = false; holdUntil = performance.now() + 2500; }));

    if (!reduceMotion) {
      d3.timer(() => {
        if (dragging || hovering || performance.now() < holdUntil) return;
        const [l, p] = proj.rotate();
        proj.rotate([l + 0.07, p]);
        redraw();
      });
    }

    globeApi = {
      redraw,
      focus(c, rotate) {
        if (!rotate || reduceMotion) {
          if (rotate) proj.rotate([-c.lon, -c.lat * 0.8]);
          redraw();
          return;
        }
        holdUntil = performance.now() + 6000;
        const target = [-c.lon, -c.lat * 0.8];
        const interp = d3.interpolate(proj.rotate(), target);
        d3.select(el).transition().duration(1100).ease(d3.easeCubicInOut)
          .tween("rotate", () => (t) => { proj.rotate(interp(t)); redraw(); });
      },
    };
    redraw();
    renderCircuitList();
  });
  onRange(() => { renderCircuitList(); if (selectedCircuit) renderCircuitCard(D.circuits.find((c) => c.id === selectedCircuit)); if (globeApi) globeApi.redraw(); });

  // ------------------------------------------------------------------------------------------
  // Team-mate network
  // ------------------------------------------------------------------------------------------
  lazy("chart-net", (el) => {
    const c = makeChart(el);
    const N = D.network.nodes, E = D.network.edges;
    const ramp = d3.interpolateRgb.gamma(1.2)("#33415e", "#cfe9ff");
    const col = (first) => ramp((first - D.kpi.first) / (D.kpi.last - D.kpi.first));
    const top = new Set(N.map((n, i) => [i, n[4]]).sort((a, b) => b[1] - a[1]).slice(0, 10).map((x) => x[0]));
    const pathSet = new Set(D.network.path);
    const pathEdges = new Set();
    D.network.path.slice(1).forEach((b, k) => {
      const a = D.network.path[k];
      pathEdges.add(`${Math.min(a, b)}-${Math.max(a, b)}`);
    });
    let pathOn = false;

    const build = () => ({
      nodes: N.map((n, i) => {
        const onPath = pathOn && pathSet.has(i);
        return {
          id: String(i), name: driverName(n[0]), x: n[1] * 1000, y: -n[2] * 1000, value: n[4],
          symbolSize: (3.4 + Math.sqrt(n[4]) * 34) + (onPath ? 6 : 0),
          itemStyle: { color: onPath ? PURPLE : col(n[6]), borderColor: "#1c1f24", borderWidth: 0.6,
            shadowBlur: onPath ? 18 : 8, shadowColor: onPath ? PURPLE : col(n[6]),
            opacity: pathOn && !onPath ? 0.28 : 1 },
          label: { show: onPath || (!pathOn && top.has(i)) },
          meta: [n[6], n[7], n[5], n[8]],
        };
      }),
      links: E.map(([a, b, w]) => {
        const onPath = pathOn && pathEdges.has(`${Math.min(a, b)}-${Math.max(a, b)}`);
        return { source: a, target: b, value: w,
          lineStyle: onPath ? { color: PURPLE, width: 3, opacity: 1 }
            : { width: Math.min(2.6, 0.55 + Math.log1p(w) * 0.38), opacity: pathOn ? 0.06 : 0.3 } };
      }),
    });

    const draw = () => {
      const { nodes, links } = build();
      c.setOption({
        animation: !reduceMotion, animationDurationUpdate: 600,
        tooltip: { ...tooltipBase, formatter: (p) => {
          if (p.dataType === "edge") {
            return `<b>${esc(nodes[p.data.source].name)} and ${esc(nodes[p.data.target].name)}</b><br>${p.data.value} races as team-mates`;
          }
          const [f, l, deg, w] = p.data.meta;
          return `<b>${esc(p.data.name)}</b><br>${dash(f, l)}<br><span style="color:${INK3}">${deg} team-mates, ${w} wins</span>`;
        } },
        series: [{
          type: "graph", layout: "none", roam: true, scaleLimit: { min: 0.6, max: 8 }, data: nodes, links,
          left: 40, right: 40, top: 30, bottom: 30, labelLayout: { hideOverlap: true },
          lineStyle: { color: "#8a93a6", curveness: 0 },
          label: { position: "right", color: INK, fontFamily: UI_FONT, fontSize: 12, fontWeight: 600,
            textBorderColor: "#1c1f24", textBorderWidth: 3 },
          emphasis: { focus: "adjacency", lineStyle: { opacity: 0.9, width: 1.6, color: "#d4d8df" }, label: { show: true } },
          blur: { itemStyle: { opacity: 0.12 }, lineStyle: { opacity: 0.03 } },
        }],
      }, { replaceMerge: ["series"] });
    };
    draw();

    const names = N.map((n) => driverName(n[0]));
    $("#driver-names").innerHTML = [...names].sort().map((n) => `<option value="${esc(n)}"></option>`).join("");
    let lastIdx = null;
    $("#driver-search").addEventListener("change", (e) => {
      const idx = names.findIndex((n) => n.toLowerCase() === e.target.value.trim().toLowerCase());
      if (lastIdx !== null) c.dispatchAction({ type: "downplay", seriesIndex: 0, dataIndex: lastIdx });
      if (idx < 0) return;
      lastIdx = idx;
      c.dispatchAction({ type: "highlight", seriesIndex: 0, dataIndex: idx });
      c.dispatchAction({ type: "showTip", seriesIndex: 0, dataIndex: idx });
    });

    $("#path-btn").addEventListener("click", (e) => {
      pathOn = !pathOn;
      e.currentTarget.setAttribute("aria-pressed", String(pathOn));
      draw();
      const chain = $("#chain");
      chain.hidden = !pathOn;
      if (pathOn) {
        chain.innerHTML = D.network.path.map((i, k) => {
          const via = k > 0 ? `<span class="via">${esc(D.network.pathVia[k - 1].join(", "))}</span>` : "";
          return `<li>${via}<span class="chip">${esc(driverName(N[i][0]))}</span></li>`;
        }).join("");
      }
    });

    const m = D.network.metrics;
    $("#net-finding").textContent =
      `${fmt(m.giant_component_drivers)} drivers form one connected network in which any two are on average ${m.average_shortest_path_giant.toFixed(1)} team-mates apart, ` +
      `with clustering ${Math.round(m.average_clustering_giant / m.random_graph_clustering)} times higher than in a random network of the same size: a small world.`;
  });

  // ------------------------------------------------------------------------------------------
  // The data: three sectors
  // ------------------------------------------------------------------------------------------
  $$("[data-team]").forEach((el) => { el.textContent = D.team; });
  const Q = D.quality;
  const qFmt = { rda_before: (v) => Math.round(v), rda_after: (v) => Math.round(v), qid_drivers: (v) => v.toFixed(1) };
  $$("[data-q]").forEach((el) => {
    const k = el.dataset.q;
    el.textContent = qFmt[k] ? qFmt[k](Q[k]) : fmt(Q[k]);
  });
})();
