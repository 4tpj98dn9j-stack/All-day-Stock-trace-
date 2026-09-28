const CHART_RANGES = [
  { value: "1d", label: "1일" },
  { value: "1w", label: "1주" },
  { value: "1mo", label: "1개월" },
  { value: "3mo", label: "3개월" },
  { value: "6mo", label: "6개월" },
  { value: "ytd", label: "YTD" },
  { value: "1y", label: "1년" },
  { value: "2y", label: "2년" },
  { value: "5y", label: "5년" },
  { value: "10y", label: "10년" },
  { value: "max", label: "전체" },
];
const DEFAULT_CHART_RANGE = "3mo";

function formatLargeNumber(n) {
  if (n == null) return "-";
  const abs = Math.abs(n);
  if (abs >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  return n.toLocaleString("en-US");
}

function formatStat(n, decimals = 2) {
  return n == null ? "-" : n.toFixed(decimals);
}

function renderAfterHoursPrice(stats) {
  if (!stats) return "";

  const render = (price, pct, label) => {
    const isUp = pct != null && pct >= 0;
    const sign = isUp ? "+" : "";
    const pctText = pct != null ? ` (${sign}${pct.toFixed(2)}%)` : "";
    const cls = pct != null ? (isUp ? "up" : "down") : "";
    return `<p class="after-hours-price ${cls}">${label}: $${price.toFixed(2)}${pctText}</p>`;
  };

  if (stats.post_market_price != null) {
    return render(stats.post_market_price, stats.post_market_change_pct, "시간외");
  }
  if (stats.pre_market_price != null) {
    return render(stats.pre_market_price, stats.pre_market_change_pct, "프리마켓");
  }
  return "";
}

function renderStatsGrid(stats) {
  if (!stats) {
    return "";
  }
  return `
    <h3 class="stats-title">추가 정보</h3>
    <div class="detail-grid stats-grid">
      <div><div class="label">시가총액</div><div class="value">${stats.market_cap != null ? "$" + formatLargeNumber(stats.market_cap) : "-"}</div></div>
      <div><div class="label">PER</div><div class="value">${formatStat(stats.pe_ratio)}</div></div>
      <div><div class="label">EPS</div><div class="value">${stats.eps != null ? "$" + formatStat(stats.eps) : "-"}</div></div>
      <div><div class="label">베타</div><div class="value">${formatStat(stats.beta)}</div></div>
      <div><div class="label">52주 최고</div><div class="value">${stats.week52_high != null ? "$" + formatStat(stats.week52_high) : "-"}</div></div>
      <div><div class="label">52주 최저</div><div class="value">${stats.week52_low != null ? "$" + formatStat(stats.week52_low) : "-"}</div></div>
      <div><div class="label">평균 거래량</div><div class="value">${stats.avg_volume != null ? formatLargeNumber(stats.avg_volume) : "-"}</div></div>
    </div>
  `;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function isSafeHttpUrl(url) {
  try {
    const parsed = new URL(url, window.location.href);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

function linkifyInline(text) {
  // Renders "[label](url)" as a safe <a>; everything else is HTML-escaped.
  const pattern = /\[([^\]]+)\]\(([^)]+)\)/g;
  let result = "";
  let lastIndex = 0;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    result += escapeHtml(text.slice(lastIndex, match.index));
    const [, label, url] = match;
    result += isSafeHttpUrl(url)
      ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`
      : escapeHtml(label);
    lastIndex = pattern.lastIndex;
  }
  result += escapeHtml(text.slice(lastIndex));
  return result;
}

function renderReportMarkdown(text) {
  // Minimal renderer tailored to daily_report.py's fixed output shape
  // (#/##/### headers, "> " quote, "| a | b |" tables, "- " list items,
  // "[label](url)" links) -- not a general Markdown parser.
  const parts = [];
  let tableBuffer = [];
  let listBuffer = [];

  const flushTable = () => {
    if (tableBuffer.length === 0) return;
    const rows = tableBuffer.filter((row) => !/^\|[\s-:|]+\|$/.test(row));
    const cellsOf = (row) => row.slice(1, -1).split("|").map((c) => c.trim());
    const [headerRow, ...bodyRows] = rows;
    if (headerRow) {
      let table = '<table class="report-table"><thead><tr>';
      cellsOf(headerRow).forEach((c) => { table += `<th>${escapeHtml(c)}</th>`; });
      table += "</tr></thead><tbody>";
      bodyRows.forEach((row) => {
        table += "<tr>";
        cellsOf(row).forEach((c) => { table += `<td>${linkifyInline(c)}</td>`; });
        table += "</tr>";
      });
      table += "</tbody></table>";
      parts.push(table);
    }
    tableBuffer = [];
  };

  const flushList = () => {
    if (listBuffer.length === 0) return;
    parts.push(`<ul>${listBuffer.map((item) => `<li>${linkifyInline(item)}</li>`).join("")}</ul>`);
    listBuffer = [];
  };

  text.split("\n").forEach((rawLine) => {
    const line = rawLine.trim();

    if (line.startsWith("|")) {
      tableBuffer.push(line);
      return;
    }
    flushTable();

    if (line.startsWith("- ")) {
      listBuffer.push(line.slice(2));
      return;
    }
    flushList();

    if (line.startsWith("### ")) {
      parts.push(`<h4>${escapeHtml(line.slice(4))}</h4>`);
    } else if (line.startsWith("## ")) {
      parts.push(`<h3>${escapeHtml(line.slice(3))}</h3>`);
    } else if (line.startsWith("# ")) {
      parts.push(`<h2>${escapeHtml(line.slice(2))}</h2>`);
    } else if (line.startsWith("> ")) {
      parts.push(`<p class="report-quote">${linkifyInline(line.slice(2))}</p>`);
    } else if (line !== "") {
      parts.push(`<p>${linkifyInline(line)}</p>`);
    }
  });
  flushTable();
  flushList();

  return parts.join("\n");
}

async function loadDailyReport() {
  const dateEl = document.getElementById("daily-report-date");
  const contentEl = document.getElementById("daily-report-content");

  try {
    const res = await fetch("/api/daily-report");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    dateEl.textContent = data.date;
    contentEl.innerHTML = renderReportMarkdown(data.content);
  } catch (err) {
    dateEl.textContent = "";
    contentEl.innerHTML = `<p class="error">아직 생성된 리포트가 없습니다.</p>`;
  }
}

async function loadMacroData() {
  const indicesEl = document.getElementById("macro-indices");

  try {
    const res = await fetch("/api/macro-data");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();

    indicesEl.innerHTML = "";
    Object.values(data.series || {}).forEach((series) => {
      const chip = document.createElement("div");
      chip.className = "index-chip";

      if (series.error || series.value == null) {
        chip.innerHTML = `
          <div class="index-name">${escapeHtml(series.name)}</div>
          <div class="index-change">데이터 없음</div>
        `;
      } else {
        const prefix = series.prefix || "";
        const unit = series.unit || "";
        const valueText = `${prefix}${series.value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${unit}`;
        let changeText = "";
        if (series.change != null) {
          const isUp = series.change >= 0;
          chip.classList.add(isUp ? "up" : "down");
          const sign = isUp ? "+" : "-";
          changeText = `${sign}${prefix}${Math.abs(series.change).toFixed(2)}${unit}`;
        }
        chip.innerHTML = `
          <div class="index-name">${escapeHtml(series.name)}</div>
          <div class="index-price">${valueText}</div>
          <div class="index-change">${changeText}</div>
        `;
        if (series.history && series.history.length > 1) {
          chip.addEventListener("click", () => openMacroDetail(series));
        }
      }

      indicesEl.appendChild(chip);
    });
  } catch (err) {
    indicesEl.innerHTML = `<div class="error">매크로 지표를 불러오지 못했습니다.</div>`;
  }
}

// Categorical palette for the SCOOS panels, capped at three series because
// that's the widest set that stays distinguishable under colour-vision
// deficiency. Each slot also gets its own dash pattern, so identity never
// rests on hue alone.
const SCOOS_SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"];
const SCOOS_SERIES_DASHES = [[], [6, 4], [2, 3]];

// Every rendered SCOOS panel, kept so a resize (or a hover leaving the
// canvas) can redraw them without refetching.
const scoosPanels = [];

function formatNetPercent(value) {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

function quarterLabel(dateStr) {
  const [year, month] = dateStr.split("-").map(Number);
  return `${year} Q${Math.floor((month - 1) / 3) + 1}`;
}

async function loadScoosData() {
  const groupsEl = document.getElementById("scoos-groups");
  const quarterEl = document.getElementById("scoos-quarter");
  const sourceEl = document.getElementById("scoos-source");

  scoosPanels.length = 0;

  try {
    const res = await fetch("/api/scoos-data");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();

    quarterEl.textContent = data.latest_quarter ? `${data.latest_quarter} 기준` : "";
    sourceEl.textContent = `출처: ${data.source || "Federal Reserve Board, SCOOS"} · ${data.unit || "순비율(%)"}, 분기`;

    groupsEl.innerHTML = "";
    (data.groups || []).forEach((group) => {
      const groupEl = document.createElement("div");
      groupEl.className = "scoos-group";
      groupEl.innerHTML = `
        <h3 class="scoos-group-title">${escapeHtml(group.title)}</h3>
        <p class="scoos-group-desc">${escapeHtml(group.description || "")}</p>
      `;

      (group.panels || []).forEach((panel) => {
        const drawable = (panel.series || []).filter(
          (s) => !s.error && s.history && s.history.length > 1,
        );
        if (!drawable.length) {
          return;
        }
        groupEl.appendChild(buildScoosPanel(panel.title, drawable));
      });

      groupsEl.appendChild(groupEl);
    });

    redrawScoosPanels();
  } catch (err) {
    groupsEl.innerHTML = `<div class="error">SCOOS 데이터를 불러오지 못했습니다.</div>`;
    quarterEl.textContent = "";
    sourceEl.textContent = "";
  }
}

function buildScoosPanel(title, series) {
  const panelEl = document.createElement("div");
  panelEl.className = "scoos-panel";

  // A lone series is already named by the panel title, so a legend
  // repeating it would just be noise.
  const legend = series.length < 2
    ? ""
    : `<div class="scoos-legend">${series
        .map((s, i) => {
          const style = ["solid", "dashed", "dotted"][i] || "solid";
          return `
            <span class="scoos-legend-item">
              <span class="scoos-legend-line" style="border-top-color:${SCOOS_SERIES_COLORS[i]};border-top-style:${style}"></span>
              ${escapeHtml(s.name)}
            </span>
          `;
        })
        .join("")}</div>`;

  panelEl.innerHTML = `
    <div class="scoos-panel-title">${escapeHtml(title)}</div>
    ${legend}
    <canvas class="scoos-chart"></canvas>
  `;

  const canvas = panelEl.querySelector(".scoos-chart");

  // All the panel's series share the survey calendar, but build the date
  // axis as a union anyway so a series that starts late (or skips a
  // quarter) lines up instead of shifting the whole line sideways.
  const dates = [...new Set(series.flatMap((s) => s.history.map((p) => p.date)))].sort();
  const lines = series.map((s) => {
    const byDate = new Map(s.history.map((p) => [p.date, p.value]));
    return { name: s.name, values: dates.map((d) => (byDate.has(d) ? byDate.get(d) : null)) };
  });

  const state = { canvas, dates, lines, highlight: null };
  scoosPanels.push(state);

  const pick = (event) => {
    const rect = canvas.getBoundingClientRect();
    state.highlight = nearestScoosIndex(state, event.clientX - rect.left, rect.width);
    drawScoosChart(state);
  };
  canvas.addEventListener("pointerdown", pick);
  canvas.addEventListener("pointermove", (event) => {
    // Touch only tracks while the finger is down; a mouse tracks always.
    if (event.pointerType === "mouse" || event.buttons) {
      pick(event);
    }
  });
  canvas.addEventListener("pointerleave", () => {
    state.highlight = null;
    drawScoosChart(state);
  });

  return panelEl;
}

const SCOOS_PAD = { left: 30, right: 8, top: 8, bottom: 18 };

function nearestScoosIndex(state, x, width) {
  const plotWidth = Math.max(width - SCOOS_PAD.left - SCOOS_PAD.right, 1);
  const stepX = plotWidth / Math.max(state.dates.length - 1, 1);
  const index = Math.round((x - SCOOS_PAD.left) / stepX);
  return Math.min(Math.max(index, 0), state.dates.length - 1);
}

function niceAxisScale(min, max, targetTicks = 4) {
  const span = Math.max(max - min, 1);
  const rough = span / targetTicks;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rough)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= rough) || 10 * magnitude;
  return { lo: Math.floor(min / step) * step, hi: Math.ceil(max / step) * step, step };
}

function scoosYearTicks(dates) {
  // Label the first quarter of every other year, matching the Fed's own
  // exhibit charts; fall back to every year for a short series.
  const firstQuarters = dates
    .map((date, index) => ({ date, index }))
    .filter(({ date }) => date.endsWith("-01-01"));
  const everyOther = firstQuarters.filter(({ date }) => Number(date.slice(0, 4)) % 2 === 0);
  const chosen = everyOther.length >= 3 ? everyOther : firstQuarters;
  return chosen.map(({ date, index }) => ({ index, label: date.slice(0, 4) }));
}

function drawScoosChart(state) {
  const { canvas, dates, lines, highlight } = state;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 300;
  const height = canvas.clientHeight || 150;

  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, width, height);

  const allValues = lines.flatMap((line) => line.values.filter((v) => v != null));
  if (!allValues.length) {
    return;
  }

  // Always include zero -- these are net percentages, and the sign is the
  // whole point, so a scale that floats off the zero line would mislead.
  const { lo, hi, step } = niceAxisScale(Math.min(0, ...allValues), Math.max(0, ...allValues));
  const valueRange = hi - lo || 1;

  const plotWidth = Math.max(width - SCOOS_PAD.left - SCOOS_PAD.right, 1);
  const plotHeight = Math.max(height - SCOOS_PAD.top - SCOOS_PAD.bottom, 1);
  const stepX = plotWidth / Math.max(dates.length - 1, 1);
  const toX = (i) => SCOOS_PAD.left + i * stepX;
  const toY = (v) => SCOOS_PAD.top + plotHeight - ((v - lo) / valueRange) * plotHeight;

  ctx.font = "10px -apple-system, sans-serif";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let v = lo; v <= hi + step / 2; v += step) {
    const y = toY(v);
    ctx.beginPath();
    ctx.moveTo(SCOOS_PAD.left, y);
    ctx.lineTo(width - SCOOS_PAD.right, y);
    ctx.strokeStyle = Math.abs(v) < step / 2 ? "#c7c7cc" : "#ececee";
    ctx.lineWidth = 1;
    ctx.setLineDash([]);
    ctx.stroke();
    ctx.fillStyle = "#999";
    ctx.fillText(String(Math.round(v)), SCOOS_PAD.left - 5, y);
  }

  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.fillStyle = "#999";
  scoosYearTicks(dates).forEach((tick) => {
    ctx.fillText(tick.label, toX(tick.index), height - SCOOS_PAD.bottom + 4);
  });

  lines.forEach((line, i) => {
    ctx.beginPath();
    let drawing = false;
    line.values.forEach((value, index) => {
      if (value == null) {
        drawing = false;
        return;
      }
      const x = toX(index);
      const y = toY(value);
      if (drawing) {
        ctx.lineTo(x, y);
      } else {
        ctx.moveTo(x, y);
        drawing = true;
      }
    });
    ctx.strokeStyle = SCOOS_SERIES_COLORS[i % SCOOS_SERIES_COLORS.length];
    ctx.setLineDash(SCOOS_SERIES_DASHES[i % SCOOS_SERIES_DASHES.length]);
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.stroke();
  });
  ctx.setLineDash([]);

  if (highlight != null) {
    drawScoosTooltip(ctx, { width, height, toX, toY, dates, lines, highlight });
  }
}

function drawScoosTooltip(ctx, { width, height, toX, toY, dates, lines, highlight }) {
  const x = toX(highlight);

  ctx.beginPath();
  ctx.moveTo(x, SCOOS_PAD.top);
  ctx.lineTo(x, height - SCOOS_PAD.bottom);
  ctx.strokeStyle = "#c7c7cc";
  ctx.lineWidth = 1;
  ctx.stroke();

  const rows = [];
  lines.forEach((line, i) => {
    const value = line.values[highlight];
    if (value == null) {
      return;
    }
    const color = SCOOS_SERIES_COLORS[i % SCOOS_SERIES_COLORS.length];
    rows.push({ color, text: `${line.name}: ${formatNetPercent(value)}` });

    // 2px surface ring so a marker stays readable where two lines cross.
    const y = toY(value);
    ctx.beginPath();
    ctx.arc(x, y, 4.5, 0, Math.PI * 2);
    ctx.fillStyle = "#fff";
    ctx.fill();
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  });

  if (!rows.length) {
    return;
  }

  const title = quarterLabel(dates[highlight]);
  const padding = 7;
  const swatch = 9;
  const lineHeight = 15;

  ctx.font = "bold 11px -apple-system, sans-serif";
  let boxWidth = ctx.measureText(title).width;
  ctx.font = "11px -apple-system, sans-serif";
  rows.forEach((row) => {
    boxWidth = Math.max(boxWidth, swatch + 5 + ctx.measureText(row.text).width);
  });
  boxWidth += padding * 2;
  const boxHeight = padding * 2 + lineHeight * (rows.length + 1);

  // Sit to the right of the crosshair, but flip to its left rather than
  // clamp when that would run off the canvas -- clamping would park the box
  // right on top of the most recent quarters, which is what you're usually
  // pointing at.
  const flip = x + 10 + boxWidth > width - 2;
  const boxX = Math.max(flip ? x - 10 - boxWidth : x + 10, 2);
  const boxY = Math.min(SCOOS_PAD.top + 4, height - boxHeight - 2);

  ctx.fillStyle = "rgba(40, 40, 42, 0.92)";
  ctx.beginPath();
  ctx.roundRect(boxX, boxY, boxWidth, boxHeight, 5);
  ctx.fill();

  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "#fff";
  ctx.font = "bold 11px -apple-system, sans-serif";
  ctx.fillText(title, boxX + padding, boxY + padding + lineHeight / 2);

  ctx.font = "11px -apple-system, sans-serif";
  rows.forEach((row, i) => {
    const y = boxY + padding + lineHeight * (i + 1) + lineHeight / 2;
    ctx.fillStyle = row.color;
    ctx.fillRect(boxX + padding, y - swatch / 2, swatch, swatch);
    ctx.fillStyle = "#fff";
    ctx.fillText(row.text, boxX + padding + swatch + 5, y);
  });
}

function redrawScoosPanels() {
  scoosPanels.forEach(drawScoosChart);
}

async function loadMarketSummary() {
  const indicesEl = document.getElementById("market-indices");
  const commentEl = document.getElementById("market-comment");

  try {
    const res = await fetch("/api/market-summary");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();

    indicesEl.innerHTML = "";
    (data.indices || []).forEach((idx) => {
      const chip = document.createElement("div");
      chip.className = "index-chip";

      if (idx.error) {
        chip.innerHTML = `
          <div class="index-name">${escapeHtml(idx.name)}</div>
          <div class="index-change">데이터 없음</div>
        `;
      } else {
        const isUp = idx.change_pct >= 0;
        chip.classList.add(isUp ? "up" : "down");
        const sign = isUp ? "+" : "";
        chip.innerHTML = `
          <div class="index-name">${escapeHtml(idx.name)}</div>
          <div class="index-price">${idx.price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
          <div class="index-change">${sign}${idx.change.toFixed(2)} (${sign}${idx.change_pct.toFixed(2)}%)</div>
        `;
        chip.addEventListener("click", () => openIndexDetail(idx.symbol, idx.name));
      }

      indicesEl.appendChild(chip);
    });

    commentEl.textContent = data.summary || "";
  } catch (err) {
    indicesEl.innerHTML = `<div class="error">시황 정보를 불러오지 못했습니다.</div>`;
    commentEl.textContent = "";
  }
}

async function loadQuotes() {
  const cardsEl = document.getElementById("cards");
  const updatedEl = document.getElementById("updated-at");

  try {
    const res = await fetch("/api/quotes");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();

    cardsEl.innerHTML = "";
    data.forEach((item) => {
      const card = document.createElement("div");
      card.className = "card";

      if (item.error) {
        card.innerHTML = `
          <div class="ticker">${escapeHtml(item.ticker)}</div>
          <div class="error">데이터 없음</div>
        `;
      } else {
        const isUp = item.change_pct >= 0;
        card.classList.add(isUp ? "up" : "down");
        const sign = isUp ? "+" : "";
        card.innerHTML = `
          <div class="ticker">${escapeHtml(item.ticker)}</div>
          <div class="price">$${item.price.toFixed(2)}</div>
          <div class="change">${sign}${item.change.toFixed(2)} (${sign}${item.change_pct.toFixed(2)}%)</div>
        `;
        card.addEventListener("click", () => openDetail(item.ticker));
      }

      cardsEl.appendChild(card);
    });

    updatedEl.textContent = `마지막 업데이트: ${new Date().toLocaleTimeString("ko-KR")}`;
  } catch (err) {
    cardsEl.innerHTML = `<div class="error">데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.</div>`;
  }
}

async function refreshAll() {
  const btn = document.getElementById("refresh-btn");

  btn.disabled = true;
  btn.textContent = "불러오는 중...";

  try {
    await Promise.all([
      loadMarketSummary(),
      loadMacroData(),
      loadScoosData(),
      loadQuotes(),
      loadDailyReport(),
    ]);
  } finally {
    btn.disabled = false;
    btn.textContent = "새로고침";
  }
}

async function openDetail(ticker) {
  const overlay = document.getElementById("modal-overlay");
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");

  title.textContent = ticker;
  body.innerHTML = "<p>불러오는 중...</p>";
  overlay.classList.remove("hidden");

  try {
    const res = await fetch(`/api/quote/${encodeURIComponent(ticker)}`);
    const data = await res.json();

    if (!res.ok || data.error) {
      body.innerHTML = "<p>상세 정보를 불러올 수 없습니다.</p>";
      return;
    }

    const volumeText = data.volume != null ? data.volume.toLocaleString("en-US") : "-";
    const newsHtml = (data.news && data.news.length > 0)
      ? `
        <div class="news-list">
          <h3>최근 뉴스</h3>
          <ul>
            ${data.news.map((n) => `
              <li>
                ${isSafeHttpUrl(n.link)
                  ? `<a href="${escapeHtml(n.link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(n.title)}</a>`
                  : `<span>${escapeHtml(n.title)}</span>`}
                ${n.publisher ? `<div class="publisher">${escapeHtml(n.publisher)}</div>` : ""}
              </li>
            `).join("")}
          </ul>
        </div>
      `
      : `<div class="news-list"><h3>최근 뉴스</h3><p>표시할 뉴스가 없습니다.</p></div>`;

    body.innerHTML = `
      ${renderAfterHoursPrice(data.stats)}
      <div class="chart-section">
        <div class="chart-range-buttons">
          ${CHART_RANGES.map((r) => `
            <button type="button" class="range-btn${r.value === DEFAULT_CHART_RANGE ? " active" : ""}" data-range="${r.value}">${r.label}</button>
          `).join("")}
        </div>
        <canvas class="detail-chart"></canvas>
        <div class="chart-meta">
          <span class="chart-meta-low"></span>
          <span class="chart-meta-high"></span>
        </div>
      </div>
      <div class="detail-grid">
        <div><div class="label">현재가</div><div class="value">$${data.close.toFixed(2)}</div></div>
        <div><div class="label">전일 종가</div><div class="value">$${data.prev_close.toFixed(2)}</div></div>
        <div><div class="label">시가</div><div class="value">$${data.open.toFixed(2)}</div></div>
        <div><div class="label">고가</div><div class="value">$${data.high.toFixed(2)}</div></div>
        <div><div class="label">저가</div><div class="value">$${data.low.toFixed(2)}</div></div>
        <div><div class="label">거래량</div><div class="value">${volumeText}</div></div>
      </div>
      ${renderStatsGrid(data.stats)}
      ${newsHtml}
    `;

    setupChart((range) => `/api/quote/${encodeURIComponent(ticker)}/history?range=${encodeURIComponent(range)}`, body);
  } catch (err) {
    body.innerHTML = "<p>상세 정보를 불러올 수 없습니다.</p>";
  }
}

function setupChart(historyUrlFor, container, formatValue = (v) => `$${v.toFixed(2)}`) {
  const buttons = container.querySelectorAll(".range-btn");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      loadChart(historyUrlFor, btn.dataset.range, container, formatValue);
    });
  });
  loadChart(historyUrlFor, DEFAULT_CHART_RANGE, container, formatValue);
}

async function loadChart(historyUrlFor, range, container, formatValue = (v) => `$${v.toFixed(2)}`) {
  const canvas = container.querySelector(".detail-chart");
  const lowEl = container.querySelector(".chart-meta-low");
  const highEl = container.querySelector(".chart-meta-high");

  lowEl.textContent = "";
  highEl.textContent = "";
  drawLineChart(canvas, null);

  try {
    const res = await fetch(historyUrlFor(range));
    const data = await res.json();
    const points = (res.ok && data.points) ? data.points : [];

    drawLineChart(canvas, points, formatValue);

    if (points.length > 0) {
      const { minIndex, maxIndex } = findMinMaxIndices(points);
      lowEl.textContent = `저 ${formatValue(points[minIndex].close)} (${points[minIndex].date})`;
      highEl.textContent = `고 ${formatValue(points[maxIndex].close)} (${points[maxIndex].date})`;
    }
  } catch (err) {
    drawLineChart(canvas, null);
  }
}

function findMinMaxIndices(points) {
  let minIndex = 0;
  let maxIndex = 0;
  points.forEach((p, i) => {
    if (p.close < points[minIndex].close) minIndex = i;
    if (p.close > points[maxIndex].close) maxIndex = i;
  });
  return { minIndex, maxIndex };
}

function parseChartDate(dateStr) {
  // "YYYY-MM-DD" or "YYYY-MM-DD HH:MM" -- always UTC to avoid local-TZ drift.
  const [datePart] = dateStr.split(" ");
  const [y, m, d] = datePart.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

function nearestIndexForDate(points, targetTime) {
  let lo = 0;
  let hi = points.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (parseChartDate(points[mid].date).getTime() < targetTime) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
  }
  return lo;
}

function evenlySpacedTicks(points, count, labelFn) {
  const n = points.length;
  const tickCount = Math.min(count, n);
  const ticks = [];
  for (let i = 0; i < tickCount; i++) {
    const idx = Math.round((i * (n - 1)) / Math.max(tickCount - 1, 1));
    ticks.push({ index: idx, label: labelFn(points[idx].date) });
  }
  return ticks;
}

function pickXAxisTicks(points) {
  // Intraday points ("1d"/"1w" stock ranges) are evenly spaced by the
  // minute, so index-based ticks read fine -- just label with the time.
  if (points[0].date.includes(":")) {
    return evenlySpacedTicks(points, 4, (d) => d.slice(11));
  }

  const first = parseChartDate(points[0].date);
  const last = parseChartDate(points[points.length - 1].date);
  const spanDays = (last - first) / 86400000;

  // Too short a span for calendar month ticks to make sense -- fall back
  // to evenly-spaced index ticks labeled "MM/DD".
  if (spanDays <= 40) {
    return evenlySpacedTicks(points, 5, (d) => d.slice(5).replace("-", "/"));
  }

  let stepMonths;
  if (spanDays <= 450) stepMonths = 1;
  else if (spanDays <= 1000) stepMonths = 3;
  else if (spanDays <= 2200) stepMonths = 6;
  else stepMonths = 12;

  const ticks = [];
  const cursor = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), 1));
  while (cursor <= last) {
    const idx = nearestIndexForDate(points, cursor.getTime());
    const shortYear = String(cursor.getUTCFullYear()).slice(-2);
    const label = stepMonths >= 12
      ? `${shortYear}`
      : `${shortYear}.${String(cursor.getUTCMonth() + 1).padStart(2, "0")}`;
    if (ticks.length === 0 || ticks[ticks.length - 1].index !== idx) {
      ticks.push({ index: idx, label });
    }
    cursor.setUTCMonth(cursor.getUTCMonth() + stepMonths);
  }
  return ticks;
}

function drawLineChart(canvas, points, formatValue = (v) => v.toFixed(2)) {
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 300;
  const height = canvas.clientHeight || 140;

  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, width, height);

  if (!points || points.length < 2) {
    ctx.fillStyle = "#999";
    ctx.font = "13px -apple-system, sans-serif";
    ctx.fillText("차트 데이터를 불러오는 중...", 10, height / 2);
    return;
  }

  const closes = points.map((p) => p.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const valueRange = max - min || 1;
  const isUp = closes[closes.length - 1] >= closes[0];
  const lineColor = isUp ? "#e53935" : "#1e88e5";
  const fillColor = isUp ? "rgba(229, 57, 53, 0.12)" : "rgba(30, 136, 229, 0.12)";

  const padLeft = 8;
  const padRight = 8;
  const padTop = 20;
  const padBottom = 16;
  const plotWidth = Math.max(width - padLeft - padRight, 1);
  const plotHeight = Math.max(height - padTop - padBottom, 1);

  const stepX = points.length > 1 ? plotWidth / (points.length - 1) : 0;
  const toX = (i) => padLeft + i * stepX;
  const toY = (price) => padTop + plotHeight - ((price - min) / valueRange) * plotHeight;

  // X-axis date labels, spaced by calendar month/quarter/year so they
  // can't be misread as lining up with the low/high point.
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.fillStyle = "#999";
  pickXAxisTicks(points).forEach((tick) => {
    ctx.fillText(tick.label, toX(tick.index), height - padBottom + 2);
  });

  ctx.beginPath();
  points.forEach((p, i) => {
    const x = toX(i);
    const y = toY(p.close);
    if (i === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.strokeStyle = lineColor;
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.stroke();

  ctx.lineTo(toX(points.length - 1), padTop + plotHeight);
  ctx.lineTo(padLeft, padTop + plotHeight);
  ctx.closePath();
  ctx.fillStyle = fillColor;
  ctx.fill();

  // Mark the actual high/low points directly on the line (instead of a
  // separate Y-axis) so the value can't be misread as belonging to a
  // different point in time.
  const { minIndex, maxIndex } = findMinMaxIndices(points);
  const markPoint = (index, value, labelAbove) => {
    const x = toX(index);
    const y = toY(value);

    // White halo behind the dot so it stays visible where the line/fill
    // pass right through it.
    ctx.beginPath();
    ctx.arc(x, y, 4.5, 0, Math.PI * 2);
    ctx.fillStyle = "#fff";
    ctx.fill();
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fillStyle = lineColor;
    ctx.fill();

    ctx.font = "bold 11px -apple-system, sans-serif";
    ctx.textBaseline = labelAbove ? "bottom" : "top";
    const nearLeftEdge = x < padLeft + plotWidth * 0.15;
    const nearRightEdge = x > padLeft + plotWidth * 0.85;
    ctx.textAlign = nearLeftEdge ? "left" : nearRightEdge ? "right" : "center";
    const labelY = labelAbove ? y - 6 : y + 6;
    const label = formatValue(value);
    // Same white-halo trick for the label text -- a thick white stroke
    // behind the colored fill keeps it legible over the line/fill/gridlines.
    ctx.lineWidth = 3;
    ctx.strokeStyle = "#fff";
    ctx.lineJoin = "round";
    ctx.strokeText(label, x, labelY);
    ctx.fillStyle = lineColor;
    ctx.fillText(label, x, labelY);
  };
  // Both labels sit above their point -- the low point is always at the
  // very bottom of the plot area, so "below" would collide with the
  // X-axis date labels underneath it.
  markPoint(maxIndex, max, true);
  if (minIndex !== maxIndex) {
    markPoint(minIndex, min, true);
  }
}

async function openIndexDetail(symbol, name) {
  const overlay = document.getElementById("modal-overlay");
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");

  title.textContent = name;
  body.innerHTML = "<p>불러오는 중...</p>";
  overlay.classList.remove("hidden");

  try {
    const res = await fetch(`/api/index/${encodeURIComponent(symbol)}`);
    const data = await res.json();

    if (!res.ok || data.error) {
      body.innerHTML = "<p>상세 정보를 불러올 수 없습니다.</p>";
      return;
    }

    const fmt = (n) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    body.innerHTML = `
      <div class="chart-section">
        <div class="chart-range-buttons">
          ${CHART_RANGES.map((r) => `
            <button type="button" class="range-btn${r.value === DEFAULT_CHART_RANGE ? " active" : ""}" data-range="${r.value}">${r.label}</button>
          `).join("")}
        </div>
        <canvas class="detail-chart"></canvas>
        <div class="chart-meta">
          <span class="chart-meta-low"></span>
          <span class="chart-meta-high"></span>
        </div>
      </div>
      <div class="detail-grid">
        <div><div class="label">현재가</div><div class="value">${fmt(data.close)}</div></div>
        <div><div class="label">전일 종가</div><div class="value">${fmt(data.prev_close)}</div></div>
        <div><div class="label">시가</div><div class="value">${fmt(data.open)}</div></div>
        <div><div class="label">고가</div><div class="value">${fmt(data.high)}</div></div>
        <div><div class="label">저가</div><div class="value">${fmt(data.low)}</div></div>
      </div>
    `;

    setupChart((range) => `/api/index/${encodeURIComponent(symbol)}/history?range=${encodeURIComponent(range)}`, body, fmt);
  } catch (err) {
    body.innerHTML = "<p>상세 정보를 불러올 수 없습니다.</p>";
  }
}

function openMacroDetail(series) {
  const overlay = document.getElementById("modal-overlay");
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");

  title.textContent = series.name;
  body.innerHTML = `
    <div class="chart-section">
      <canvas class="detail-chart"></canvas>
      <div class="chart-meta">
        <span class="chart-meta-low"></span>
        <span class="chart-meta-high"></span>
      </div>
    </div>
  `;
  overlay.classList.remove("hidden");

  const canvas = body.querySelector(".detail-chart");
  const lowEl = body.querySelector(".chart-meta-low");
  const highEl = body.querySelector(".chart-meta-high");

  const points = series.history.map((p) => ({ date: p.date, close: p.value }));
  const prefix = series.prefix || "";
  const unit = series.unit || "";
  drawLineChart(canvas, points, (v) => `${prefix}${v.toFixed(2)}${unit}`);

  const { minIndex, maxIndex } = findMinMaxIndices(points);
  lowEl.textContent = `저 ${prefix}${points[minIndex].close.toFixed(2)}${unit} (${points[minIndex].date})`;
  highEl.textContent = `고 ${prefix}${points[maxIndex].close.toFixed(2)}${unit} (${points[maxIndex].date})`;
}

function closeDetail() {
  document.getElementById("modal-overlay").classList.add("hidden");
}

document.getElementById("refresh-btn").addEventListener("click", refreshAll);
document.getElementById("modal-close").addEventListener("click", closeDetail);
document.getElementById("modal-overlay").addEventListener("click", (e) => {
  if (e.target.id === "modal-overlay") {
    closeDetail();
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeDetail();
  }
});

// The SCOOS charts are laid out inline (not in a modal), so they have to
// re-render at the new width when the window or phone orientation changes.
let scoosResizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(scoosResizeTimer);
  scoosResizeTimer = setTimeout(redrawScoosPanels, 150);
});

window.addEventListener("DOMContentLoaded", refreshAll);
