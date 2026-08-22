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
      }

      indicesEl.appendChild(chip);
    });
  } catch (err) {
    indicesEl.innerHTML = `<div class="error">매크로 지표를 불러오지 못했습니다.</div>`;
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

  try {
    await Promise.all([loadMarketSummary(), loadMacroData(), loadQuotes(), loadDailyReport()]);
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

    setupChart(ticker, body);
  } catch (err) {
    body.innerHTML = "<p>상세 정보를 불러올 수 없습니다.</p>";
  }
}

function setupChart(ticker, container) {
  const buttons = container.querySelectorAll(".range-btn");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      loadChart(ticker, btn.dataset.range, container);
    });
  });
  loadChart(ticker, DEFAULT_CHART_RANGE, container);
}

async function loadChart(ticker, range, container) {
  const canvas = container.querySelector(".detail-chart");
  const lowEl = container.querySelector(".chart-meta-low");
  const highEl = container.querySelector(".chart-meta-high");

  lowEl.textContent = "";
  highEl.textContent = "";
  drawLineChart(canvas, null);

  try {
    const res = await fetch(`/api/quote/${encodeURIComponent(ticker)}/history?range=${encodeURIComponent(range)}`);
    const data = await res.json();
    const points = (res.ok && data.points) ? data.points : [];

    drawLineChart(canvas, points);

    if (points.length > 0) {
      const closes = points.map((p) => p.close);
      const min = Math.min(...closes);
      const max = Math.max(...closes);
      lowEl.textContent = `저 $${min.toFixed(2)} (${points[0].date})`;
      highEl.textContent = `고 $${max.toFixed(2)} (${points[points.length - 1].date})`;
    }
  } catch (err) {
    drawLineChart(canvas, null);
  }
}

function drawLineChart(canvas, points) {
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
  const range = max - min || 1;
  const padding = 8;
  const isUp = closes[closes.length - 1] >= closes[0];
  const lineColor = isUp ? "#e53935" : "#1e88e5";
  const fillColor = isUp ? "rgba(229, 57, 53, 0.12)" : "rgba(30, 136, 229, 0.12)";

  const stepX = (width - padding * 2) / (points.length - 1);
  const toY = (price) => height - padding - ((price - min) / range) * (height - padding * 2);

  ctx.beginPath();
  points.forEach((p, i) => {
    const x = padding + i * stepX;
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

  ctx.lineTo(padding + (points.length - 1) * stepX, height - padding);
  ctx.lineTo(padding, height - padding);
  ctx.closePath();
  ctx.fillStyle = fillColor;
  ctx.fill();
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
      <div class="detail-grid">
        <div><div class="label">현재가</div><div class="value">${fmt(data.close)}</div></div>
        <div><div class="label">전일 종가</div><div class="value">${fmt(data.prev_close)}</div></div>
        <div><div class="label">시가</div><div class="value">${fmt(data.open)}</div></div>
        <div><div class="label">고가</div><div class="value">${fmt(data.high)}</div></div>
        <div><div class="label">저가</div><div class="value">${fmt(data.low)}</div></div>
      </div>
    `;
  } catch (err) {
    body.innerHTML = "<p>상세 정보를 불러올 수 없습니다.</p>";
  }
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

window.addEventListener("DOMContentLoaded", refreshAll);
