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

// Categorical palette for the multi-series panel charts, in fixed order
// (never cycled). Validated as a line-chart palette on the white card
// surface; the three lighter slots sit under 3:1 contrast, which is why
// every series also gets its own dash pattern and a legend with its
// current value, so identity never rests on hue alone.
const PANEL_SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"];
const PANEL_SERIES_DASHES = [[], [6, 4], [2, 3], [9, 3, 2, 3], [14, 4]];

// Every rendered panel chart, kept so a resize (or a hover leaving the
// canvas) can redraw them without refetching.
const panelCharts = [];

function legendSwatch(i) {
  // An SVG stroke with the same dash array as the canvas line, so the
  // legend shows exactly what the chart draws.
  const color = PANEL_SERIES_COLORS[i % PANEL_SERIES_COLORS.length];
  const dash = PANEL_SERIES_DASHES[i % PANEL_SERIES_DASHES.length].join(" ");
  return `<svg class="chart-legend-line" width="18" height="4" aria-hidden="true">
    <line x1="0" y1="2" x2="18" y2="2" stroke="${color}" stroke-width="2"${dash ? ` stroke-dasharray="${dash}"` : ""}/>
  </svg>`;
}

function legendItem(line, i, withSwatch) {
  const value = line.legendValue
    ? `<span class="chart-legend-value">${escapeHtml(line.legendValue)}</span>`
    : "";
  const change = line.legendChange
    ? `<span class="chart-legend-change ${line.legendChange.dir}">${escapeHtml(line.legendChange.text)}</span>`
    : "";
  const note = line.legendNote
    ? `<span class="chart-legend-note">${escapeHtml(line.legendNote)}</span>`
    : "";
  return `
    <span class="chart-legend-item">
      ${withSwatch ? legendSwatch(i) : ""}
      ${escapeHtml(line.name)} ${value} ${change} ${note}
    </span>
  `;
}

/* Build one multi-series panel: title, legend, canvas and pointer handling.
 *
 * `lines` is [{name, values}] where every `values` array is the same length
 * -- one entry per x position, null for a gap. A line may also carry
 * `legendValue`/`legendChange`/`legendNote` for the legend, and
 * `describe(i)` for its tooltip row (defaults to `formatValue(value)`).
 *
 * `options` supplies what the x axis means -- `xTicks` as [{index, label}],
 * `pointLabel(i)` for the tooltip heading -- plus how to draw:
 *   includeZero  keep 0 on the y scale (default true)
 *   refLine      a value to mark with a dashed rule, e.g. a 1.0 threshold
 *   connectGaps  draw straight through null days instead of breaking
 *   yFormat      label for a y tick, (value, decimals) => string; decimals
 *                is what suits the tick step (default: just that)
 *   size         "main" or the shorter "sub"
 */
function buildChartPanel(title, lines, options) {
  const {
    xTicks,
    pointLabel,
    formatValue = (v) => String(v),
    includeZero = true,
    refLine = null,
    connectGaps = false,
    yFormat = null,
    size = "main",
  } = options;
  const panelEl = document.createElement("div");
  panelEl.className = "chart-panel";

  // A lone series is already named by the panel title, so it only gets a
  // legend line when there's a current value to show, and no swatch.
  let legend = "";
  if (lines.length > 1) {
    legend = `<div class="chart-legend">${lines.map((line, i) => legendItem(line, i, true)).join("")}</div>`;
  } else if (lines.length === 1 && lines[0].legendValue) {
    legend = `<div class="chart-legend">${legendItem(lines[0], 0, false)}</div>`;
  }

  panelEl.innerHTML = `
    ${title ? `<div class="chart-panel-title">${escapeHtml(title)}</div>` : ""}
    ${legend}
    <canvas class="panel-chart${size === "sub" ? " sub" : ""}"></canvas>
  `;

  const canvas = panelEl.querySelector(".panel-chart");

  const state = {
    canvas,
    lines,
    xTicks,
    pointLabel,
    formatValue,
    includeZero,
    refLine,
    connectGaps,
    yFormat,
    pointCount: lines[0] ? lines[0].values.length : 0,
    highlight: null,
  };
  panelCharts.push(state);

  const pick = (event) => {
    const rect = canvas.getBoundingClientRect();
    state.highlight = nearestPanelIndex(state, event.clientX - rect.left, rect.width);
    drawPanelChart(state);
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
    drawPanelChart(state);
  });

  return panelEl;
}

const PANEL_PAD = { left: 30, right: 8, top: 8, bottom: 18 };

function nearestPanelIndex(state, x, width) {
  const plotWidth = Math.max(width - PANEL_PAD.left - PANEL_PAD.right, 1);
  const stepX = plotWidth / Math.max(state.pointCount - 1, 1);
  const index = Math.round((x - PANEL_PAD.left) / stepX);
  return Math.min(Math.max(index, 0), state.pointCount - 1);
}

function niceAxisScale(min, max, targetTicks = 4) {
  // A flat series still needs a non-zero span to pick a step from.
  const span = max - min || Math.abs(max) * 0.1 || 1;
  const rough = span / targetTicks;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rough)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= rough) || 10 * magnitude;
  return { lo: Math.floor(min / step) * step, hi: Math.ceil(max / step) * step, step };
}

function axisDecimals(step) {
  if (step >= 1) return 0;
  if (step >= 0.1) return 1;
  if (step >= 0.01) return 2;
  return 3;
}

function drawPanelChart(state) {
  const { canvas, lines, xTicks, pointCount, highlight, includeZero, refLine, connectGaps, yFormat } = state;
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

  // Zero stays on the scale by default: for spreads and rebased % the
  // distance from zero is the point, and a floating scale would exaggerate
  // every wiggle. Level panels like yields or VIX opt out. A reference line
  // is always kept in view, or it couldn't mark its threshold.
  const extent = [...allValues];
  if (includeZero) extent.push(0);
  if (refLine != null) extent.push(refLine);
  const { lo, hi, step } = niceAxisScale(Math.min(...extent), Math.max(...extent));
  const valueRange = hi - lo || 1;
  const decimals = axisDecimals(step);
  const tickLabel = yFormat || ((v, d) => v.toFixed(d));

  const plotWidth = Math.max(width - PANEL_PAD.left - PANEL_PAD.right, 1);
  const plotHeight = Math.max(height - PANEL_PAD.top - PANEL_PAD.bottom, 1);
  const stepX = plotWidth / Math.max(pointCount - 1, 1);
  const toX = (i) => PANEL_PAD.left + i * stepX;
  const toY = (v) => PANEL_PAD.top + plotHeight - ((v - lo) / valueRange) * plotHeight;

  ctx.font = "10px -apple-system, sans-serif";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  // Ticks computed from an index rather than by repeated addition, so
  // 0.1-sized steps don't drift into labels like 0.30000000000000004.
  const tickCount = Math.round((hi - lo) / step);
  for (let k = 0; k <= tickCount; k++) {
    const v = lo + k * step;
    const y = toY(v);
    ctx.beginPath();
    ctx.moveTo(PANEL_PAD.left, y);
    ctx.lineTo(width - PANEL_PAD.right, y);
    ctx.strokeStyle = Math.abs(v) < step / 2 ? "#c7c7cc" : "#ececee";
    ctx.lineWidth = 1;
    ctx.setLineDash([]);
    ctx.stroke();
    ctx.fillStyle = "#999";
    ctx.fillText(tickLabel(v, decimals), PANEL_PAD.left - 5, y);
  }

  if (refLine != null) {
    const y = toY(refLine);
    ctx.beginPath();
    ctx.moveTo(PANEL_PAD.left, y);
    ctx.lineTo(width - PANEL_PAD.right, y);
    ctx.strokeStyle = "#8e8e93";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 3]);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.fillStyle = "#999";
  xTicks.forEach((tick) => {
    // Nudge the end labels inward instead of letting them run off the
    // canvas -- a bucket label like "15년+" sits right on the last point,
    // so centring it would clip half of it.
    const half = ctx.measureText(tick.label).width / 2;
    const x = Math.min(Math.max(toX(tick.index), half + 1), width - half - 1);
    ctx.fillText(tick.label, x, height - PANEL_PAD.bottom + 4);
  });

  lines.forEach((line, i) => {
    ctx.beginPath();
    let drawing = false;
    line.values.forEach((value, index) => {
      if (value == null) {
        // Markets close on different holidays; with connectGaps the line
        // runs straight through a missing day rather than breaking.
        if (!connectGaps) drawing = false;
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
    ctx.strokeStyle = PANEL_SERIES_COLORS[i % PANEL_SERIES_COLORS.length];
    ctx.setLineDash(PANEL_SERIES_DASHES[i % PANEL_SERIES_DASHES.length]);
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.stroke();
  });
  ctx.setLineDash([]);

  if (highlight != null) {
    drawPanelTooltip(ctx, { width, height, toX, toY, state, highlight });
  }
}

function drawPanelTooltip(ctx, { width, height, toX, toY, state, highlight }) {
  const { lines, pointLabel, formatValue } = state;
  const x = toX(highlight);

  ctx.beginPath();
  ctx.moveTo(x, PANEL_PAD.top);
  ctx.lineTo(x, height - PANEL_PAD.bottom);
  ctx.strokeStyle = "#c7c7cc";
  ctx.lineWidth = 1;
  ctx.stroke();

  const rows = [];
  lines.forEach((line, i) => {
    const value = line.values[highlight];
    if (value == null) {
      return;
    }
    const color = PANEL_SERIES_COLORS[i % PANEL_SERIES_COLORS.length];
    const detail = line.describe ? line.describe(highlight) : formatValue(value);
    rows.push({ color, text: `${line.name}: ${detail}` });

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

  const title = pointLabel(highlight);
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
  const boxY = Math.min(PANEL_PAD.top + 4, height - boxHeight - 2);

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

function redrawPanelCharts() {
  panelCharts.forEach(drawPanelChart);
}

async function loadCreditCurve() {
  const panelsEl = document.getElementById("credit-curve-panels");
  const sourceEl = document.getElementById("credit-curve-source");

  try {
    const res = await fetch("/api/credit-curve");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();

    const buckets = data.buckets || [];
    const snapshots = (data.snapshots || []).filter((s) => s.values.some((v) => v != null));
    if (!buckets.length || !snapshots.length) {
      throw new Error("no curve");
    }

    sourceEl.textContent = `출처: ${data.source || "ICE BofA (FRED)"} · ${data.unit || "bp"}, ${data.latest_date || ""} 기준`;

    const lines = snapshots.map((snapshot) => ({ name: snapshot.name, values: snapshot.values }));

    panelsEl.innerHTML = "";
    panelsEl.appendChild(
      buildChartPanel("만기별 스프레드 (투자등급 전체)", lines, {
        // One tick per maturity bucket -- the x axis is the bucket itself,
        // not a date, so every position gets a label.
        xTicks: buckets.map((label, index) => ({ index, label })),
        pointLabel: (i) => buckets[i],
        formatValue: (v) => `${Math.round(v)}bp`,
      }),
    );

    redrawPanelCharts();
  } catch (err) {
    panelsEl.innerHTML = `<div class="error">회사채 스프레드 커브를 불러오지 못했습니다.</div>`;
    sourceEl.textContent = "";
  }
}

// --- market comparison cards (data/market_charts.json) --------------------

function formatSeriesValue(series, value) {
  const number = value.toLocaleString("en-US", {
    minimumFractionDigits: series.decimals,
    maximumFractionDigits: series.decimals,
  });
  return `${series.prefix}${number}${series.suffix}`;
}

// Mirrors change_value() in fetch_market_charts.py, for tooltip rows.
function seriesChange(kind, value, previous) {
  if (previous == null) return null;
  if (kind === "bp") return (value - previous) * 100;
  if (kind === "abs") return value - previous;
  if (previous === 0) return null;
  return (value / previous - 1) * 100;
}

function formatSeriesChange(kind, change, decimals) {
  if (change == null) return null;
  const sign = change < 0 ? "-" : "+";
  const size = Math.abs(change);
  if (kind === "bp") return `${sign}${size.toFixed(0)}bp`;
  if (kind === "abs") return `${sign}${size.toFixed(decimals)}`;
  return `${sign}${size.toFixed(2)}%`;
}

/* What a panel plots, given the raw values:
 *   rebased  % change from each series' first value in the window
 *   minmax   position within the series' own 6-month low..high, 0..100,
 *            for overlaying series whose units don't share a scale
 *   level    the values as they are
 * Tooltips and legends always show the raw values either way.
 */
function plottedValues(mode, values) {
  const present = values.filter((v) => v != null);
  if (!present.length) return values;
  if (mode === "rebased") {
    const base = present[0];
    return values.map((v) => (v == null || !base ? null : (v / base - 1) * 100));
  }
  if (mode === "minmax") {
    const low = Math.min(...present);
    const span = Math.max(...present) - low;
    return values.map((v) => (v == null ? null : span ? ((v - low) / span) * 100 : 50));
  }
  return values;
}

function panelYFormat(mode) {
  if (mode === "rebased") return (v, decimals) => `${v.toFixed(decimals)}%`;
  // A min-max axis has no units to read off, only its two ends.
  if (mode === "minmax") return (v) => (v === 0 ? "최저" : v === 100 ? "최고" : "");
  return null;
}

function marketLine(series, mode) {
  const { latest } = series;
  const describe = (i) => {
    const value = series.values[i];
    let previous = null;
    for (let j = i - 1; j >= 0; j--) {
      if (series.values[j] != null) {
        previous = series.values[j];
        break;
      }
    }
    const change = formatSeriesChange(series.change, seriesChange(series.change, value, previous), series.decimals);
    return change ? `${formatSeriesValue(series, value)} ${change}` : formatSeriesValue(series, value);
  };
  const changeText = formatSeriesChange(series.change, latest.change, series.decimals);
  return {
    name: series.name,
    values: plottedValues(mode, series.values),
    describe,
    legendValue: latest.display || formatSeriesValue(series, latest.value),
    legendChange: changeText ? { text: changeText, dir: latest.change < 0 ? "down" : "up" } : null,
    legendNote: latest.note || null,
  };
}

function buildMarketCard(card) {
  const section = document.createElement("section");
  section.className = "market-summary market-chart-card";

  const status = card.status
    ? `<p class="chart-status ${card.status.level}">${card.status.level === "warning" ? "⚠️ " : ""}${escapeHtml(card.status.text)}</p>`
    : "";
  section.innerHTML = `
    <h2 class="market-summary-title">${escapeHtml(card.title)}</h2>
    ${status}
    <div class="market-chart-panels"></div>
    <p class="chart-group-desc">${escapeHtml(card.description)}</p>
  `;

  const panelsEl = section.querySelector(".market-chart-panels");
  const dates = card.dates || [];
  const xTicks = dates.length ? pickXAxisTicks(dates.map((date) => ({ date }))) : [];

  (card.panels || []).forEach((panel) => {
    // A series whose source failed this run is dropped rather than drawn
    // as an empty line; the rest of the panel still renders.
    const lines = panel.series
      .filter((s) => s.latest && s.values.some((v) => v != null))
      .map((s) => marketLine(s, panel.mode));
    if (!lines.length) return;

    panelsEl.appendChild(
      buildChartPanel(panel.title, lines, {
        xTicks,
        pointLabel: (i) => dates[i],
        includeZero: panel.include_zero,
        refLine: panel.ref_line,
        connectGaps: true,
        yFormat: panelYFormat(panel.mode),
        size: panel.size,
      }),
    );
  });

  if (!panelsEl.children.length) {
    panelsEl.innerHTML = `<div class="error">데이터를 불러오지 못했습니다.</div>`;
  }
  return section;
}

async function loadMarketCharts() {
  const container = document.getElementById("market-charts");

  try {
    const res = await fetch("/api/market-charts");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();

    container.innerHTML = "";
    (data.cards || []).forEach((card) => container.appendChild(buildMarketCard(card)));
    redrawPanelCharts();
  } catch (err) {
    container.innerHTML = `
      <section class="market-summary">
        <div class="error">시장 비교 차트를 불러오지 못했습니다.</div>
      </section>
    `;
  }
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

  // Panel sections rebuild their canvases from scratch, so drop the old
  // chart states here rather than inside a loader -- loaders run
  // concurrently, and one clearing the shared list would discard another's
  // freshly registered panels.
  panelCharts.length = 0;

  try {
    await Promise.all([
      loadMarketSummary(),
      loadMacroData(),
      loadCreditCurve(),
      loadMarketCharts(),
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

// The panel charts are laid out inline (not in a modal), so they have to
// re-render at the new width when the window or phone orientation changes.
let panelResizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(panelResizeTimer);
  panelResizeTimer = setTimeout(redrawPanelCharts, 150);
});

window.addEventListener("DOMContentLoaded", refreshAll);
