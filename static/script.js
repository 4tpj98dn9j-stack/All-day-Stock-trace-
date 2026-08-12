const CHART_RANGES = [
  { value: "1mo", label: "1개월" },
  { value: "3mo", label: "3개월" },
  { value: "6mo", label: "6개월" },
  { value: "1y", label: "1년" },
];
const DEFAULT_CHART_RANGE = "3mo";

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
    await Promise.all([loadMarketSummary(), loadQuotes()]);
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

function renderOptionsRows(rows) {
  if (!rows || rows.length === 0) {
    return `<tr><td colspan="4" class="options-empty">데이터 없음</td></tr>`;
  }
  return rows.map((r) => `
    <tr>
      <td>${r.strike.toFixed(2)}</td>
      <td>${r.last_price != null ? r.last_price.toFixed(2) : "-"}</td>
      <td>${r.volume != null ? r.volume.toLocaleString("en-US") : "-"}</td>
      <td>${r.open_interest != null ? r.open_interest.toLocaleString("en-US") : "-"}</td>
    </tr>
  `).join("");
}

function renderOptionsSection(options) {
  if (!options || options.status === "error") {
    return `
      <div class="options-section">
        <h3>옵션 체인</h3>
        <p>일시적으로 옵션 데이터를 불러오지 못했습니다. 새로고침 후 다시 시도해주세요.</p>
      </div>
    `;
  }

  if (options.status === "unavailable") {
    return `
      <div class="options-section">
        <h3>옵션 체인</h3>
        <p>이 지수는 옵션 데이터를 제공하지 않습니다.</p>
      </div>
    `;
  }

  return `
    <div class="options-section">
      <h3>옵션 체인 (만기 ${escapeHtml(options.expiration)})</h3>
      <p class="options-subtitle">콜(Call) — 행사가 근접 ${options.calls.length}건</p>
      <table class="options-table">
        <thead><tr><th>행사가</th><th>현재가</th><th>거래량</th><th>미결제약정</th></tr></thead>
        <tbody>${renderOptionsRows(options.calls)}</tbody>
      </table>
      <p class="options-subtitle">풋(Put) — 행사가 근접 ${options.puts.length}건</p>
      <table class="options-table">
        <thead><tr><th>행사가</th><th>현재가</th><th>거래량</th><th>미결제약정</th></tr></thead>
        <tbody>${renderOptionsRows(options.puts)}</tbody>
      </table>
    </div>
  `;
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

    const optionsHtml = renderOptionsSection(data.options);

    body.innerHTML = `
      <div class="detail-grid">
        <div><div class="label">현재가</div><div class="value">${fmt(data.close)}</div></div>
        <div><div class="label">전일 종가</div><div class="value">${fmt(data.prev_close)}</div></div>
        <div><div class="label">시가</div><div class="value">${fmt(data.open)}</div></div>
        <div><div class="label">고가</div><div class="value">${fmt(data.high)}</div></div>
        <div><div class="label">저가</div><div class="value">${fmt(data.low)}</div></div>
      </div>
      ${optionsHtml}
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
