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

async function loadQuotes() {
  const btn = document.getElementById("refresh-btn");
  const cardsEl = document.getElementById("cards");
  const updatedEl = document.getElementById("updated-at");

  btn.disabled = true;
  btn.textContent = "불러오는 중...";

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
  } catch (err) {
    body.innerHTML = "<p>상세 정보를 불러올 수 없습니다.</p>";
  }
}

function closeDetail() {
  document.getElementById("modal-overlay").classList.add("hidden");
}

document.getElementById("refresh-btn").addEventListener("click", loadQuotes);
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

window.addEventListener("DOMContentLoaded", loadQuotes);
