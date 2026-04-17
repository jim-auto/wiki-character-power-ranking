const scoreKeys = ["attack", "defense", "speed", "abilities", "feats", "scale"];

const state = {
  view: "power",
  search: "",
  media: "all",
  universe: "all",
  min: "",
  max: "",
  battleA: "",
  battleB: "",
  battleMode: "power",
};

let characters = [];

const elements = {
  tabs: [...document.querySelectorAll(".tab-button")],
  controls: document.querySelector(".controls"),
  rankingView: document.querySelector("#ranking-view"),
  battleView: document.querySelector("#battle-view"),
  rankingTitle: document.querySelector("#ranking-title"),
  resultCount: document.querySelector("#result-count"),
  rankingList: document.querySelector("#ranking-list"),
  searchFilter: document.querySelector("#search-filter"),
  mediaFilter: document.querySelector("#media-filter"),
  universeFilter: document.querySelector("#universe-filter"),
  minScore: document.querySelector("#min-score"),
  maxScore: document.querySelector("#max-score"),
  battleA: document.querySelector("#battle-a"),
  battleB: document.querySelector("#battle-b"),
  battleMode: document.querySelector("#battle-mode"),
  battleResult: document.querySelector("#battle-result"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function scoreFor(character, view = state.view) {
  if (view === "iq") {
    return Number(character.iq_score ?? 0);
  }
  if (view === "balanced") {
    return Number(character.total_score ?? 0) + Number(character.iq_score ?? 0);
  }
  return Number(character.total_score ?? 0);
}

function scoreLimit() {
  return state.view === "iq" ? 10 : 60;
}

function currentScoreForFilter(character) {
  return state.view === "iq" ? Number(character.iq_score ?? 0) : Number(character.total_score ?? 0);
}

function filteredCharacters() {
  const min = state.min === "" ? null : Number(state.min);
  const max = state.max === "" ? null : Number(state.max);
  const query = state.search.trim().toLowerCase();

  return characters
    .filter((character) => {
      if (!query) return true;
      const haystack = [
        character.name,
        character.universe,
        character.media_type,
        character.wikipedia_url,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    })
    .filter((character) => state.media === "all" || character.media_type === state.media)
    .filter((character) => state.universe === "all" || character.universe === state.universe)
    .filter((character) => {
      const score = currentScoreForFilter(character);
      if (min !== null && score < min) return false;
      if (max !== null && score > max) return false;
      return true;
    })
    .sort((a, b) => scoreFor(b) - scoreFor(a) || String(a.name).localeCompare(String(b.name), "ja"));
}

function populateFilters() {
  const universes = [...new Set(characters.map((character) => character.universe).filter(Boolean))].sort();
  elements.universeFilter.innerHTML = [
    '<option value="all">All</option>',
    ...universes.map((universe) => `<option value="${escapeHtml(universe)}">${escapeHtml(universe)}</option>`),
  ].join("");

  const options = characters
    .map((character) => `<option value="${escapeHtml(character.name)}">${escapeHtml(character.name)}</option>`)
    .join("");
  elements.battleA.innerHTML = options;
  elements.battleB.innerHTML = options;

  state.battleA = characters[0]?.name ?? "";
  state.battleB = characters[1]?.name ?? characters[0]?.name ?? "";
  elements.battleA.value = state.battleA;
  elements.battleB.value = state.battleB;
}

function renderTabs() {
  elements.tabs.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === state.view);
  });
  elements.controls.classList.toggle("is-hidden", state.view === "battle");
  elements.rankingView.classList.toggle("is-hidden", state.view === "battle");
  elements.battleView.classList.toggle("is-hidden", state.view !== "battle");
  elements.minScore.max = String(scoreLimit());
  elements.maxScore.max = String(scoreLimit());
}

function dimensionBars(character) {
  const scores = character.scores ?? {};
  return scoreKeys
    .map((key) => {
      const value = Number(scores[key] ?? 0);
      const width = Math.max(0, Math.min(100, value * 10));
      return `
        <div class="dimension">
          <div class="dimension-label">
            <span>${escapeHtml(key)}</span>
            <span>${value}</span>
          </div>
          <div class="bar" aria-hidden="true">
            <div class="bar-fill ${escapeHtml(key)}" style="width: ${width}%"></div>
          </div>
        </div>
      `;
    })
    .join("");
}

function evidenceForPower(character) {
  const evidence = character.score_evidence ?? {};
  return scoreKeys
    .map((key) => {
      const items = evidence[key] ?? [];
      if (!items.length) {
        return `<li class="evidence-item"><strong>${escapeHtml(key)}</strong><span class="evidence-rule">no matched Wikipedia evidence</span></li>`;
      }
      const top = items[0];
      return `
        <li class="evidence-item">
          <strong>${escapeHtml(key)}</strong>: ${escapeHtml(top.sentence)}
          <span class="evidence-rule">${escapeHtml(top.rule)} / +${escapeHtml(top.points)}</span>
        </li>
      `;
    })
    .join("");
}

function evidenceForIq(character) {
  const items = character.iq_evidence ?? [];
  if (!items.length) {
    return '<li class="evidence-item"><strong>iq</strong><span class="evidence-rule">no matched Wikipedia evidence</span></li>';
  }
  return items
    .slice(0, 3)
    .map(
      (item) => `
        <li class="evidence-item">
          ${escapeHtml(item.sentence)}
          <span class="evidence-rule">${escapeHtml(item.rule)} / +${escapeHtml(item.points)}</span>
        </li>
      `,
    )
    .join("");
}

function characterCard(character, index) {
  const primaryScore = scoreFor(character);
  const titleScore = state.view === "iq" ? `${primaryScore}/10 IQ` : `${primaryScore}/60`;
  const evidence = state.view === "iq" ? evidenceForIq(character) : evidenceForPower(character);
  const iqWidth = Math.max(0, Math.min(100, Number(character.iq_score ?? 0) * 10));

  return `
    <article class="character-card">
      <div class="character-main">
        <div class="rank-token">${index + 1}</div>
        <div>
          <h3>${escapeHtml(character.name)}</h3>
          <div class="meta-line">
            <span>${escapeHtml(character.media_type)}</span>
            <span>${escapeHtml(character.universe)}</span>
            <a href="${escapeHtml(character.wikipedia_url)}">Wikipedia</a>
          </div>
        </div>
        <div class="score-stack">
          <span class="score-badge">${escapeHtml(titleScore)}</span>
          <span class="tier-badge">Tier ${escapeHtml(character.tier ?? "C")}</span>
        </div>
      </div>
      <div class="dimension-grid">${dimensionBars(character)}</div>
      <div class="dimension">
        <div class="dimension-label"><span>IQ</span><span>${escapeHtml(character.iq_score ?? 0)}</span></div>
        <div class="bar" aria-hidden="true"><div class="bar-fill iq" style="width: ${iqWidth}%"></div></div>
      </div>
      <ul class="evidence-list">${evidence}</ul>
    </article>
  `;
}

function renderRanking() {
  const ranked = filteredCharacters();
  elements.rankingTitle.textContent = state.view === "iq" ? "IQ Ranking" : "Power Ranking";
  elements.resultCount.textContent = String(ranked.length);
  elements.rankingList.innerHTML = ranked.length
    ? ranked.map(characterCard).join("")
    : '<div class="empty-state">No matching records.</div>';
}

function battleCharacter(name) {
  return characters.find((character) => character.name === name) ?? characters[0];
}

function battleScore(character) {
  return scoreFor(character, state.battleMode);
}

function battleVerdict(a, b) {
  const aScore = battleScore(a);
  const bScore = battleScore(b);
  const diff = Math.abs(aScore - bScore);
  if (aScore === bScore) {
    return "Draw by current evidence scores.";
  }
  const winner = aScore > bScore ? a : b;
  const label = diff >= 8 ? "favored" : "slight edge";
  return `${winner.name} is ${label} by ${diff} point(s).`;
}

function battleRows(a, b) {
  const rows = scoreKeys.map((key) => {
    const aValue = Number(a.scores?.[key] ?? 0);
    const bValue = Number(b.scores?.[key] ?? 0);
    const edge = aValue === bValue ? "even" : aValue > bValue ? a.name : b.name;
    return `<tr><td>${escapeHtml(key)}</td><td>${aValue}</td><td>${bValue}</td><td>${escapeHtml(edge)}</td></tr>`;
  });

  const iqEdge =
    Number(a.iq_score ?? 0) === Number(b.iq_score ?? 0)
      ? "even"
      : Number(a.iq_score ?? 0) > Number(b.iq_score ?? 0)
        ? a.name
        : b.name;
  rows.push(
    `<tr><td>iq_score</td><td>${Number(a.iq_score ?? 0)}</td><td>${Number(b.iq_score ?? 0)}</td><td>${escapeHtml(iqEdge)}</td></tr>`,
  );
  return rows.join("");
}

function battleEvidence(character) {
  const items =
    state.battleMode === "iq"
      ? character.iq_evidence ?? []
      : scoreKeys.flatMap((key) => character.score_evidence?.[key] ?? []);

  const sorted = [...items].sort((a, b) => Number(b.points ?? 0) - Number(a.points ?? 0)).slice(0, 4);
  if (!sorted.length) {
    return '<li class="evidence-item">no matched Wikipedia evidence</li>';
  }
  return sorted
    .map(
      (item) => `
        <li class="evidence-item">
          ${escapeHtml(item.sentence)}
          <span class="evidence-rule">${escapeHtml(item.rule)} / +${escapeHtml(item.points)}</span>
        </li>
      `,
    )
    .join("");
}

function renderBattle() {
  if (!characters.length) return;
  const a = battleCharacter(state.battleA);
  const b = battleCharacter(state.battleB);

  elements.battleResult.innerHTML = `
    <div class="verdict">
      <h3>${escapeHtml(battleVerdict(a, b))}</h3>
      <div class="score-stack">
        <span class="score-badge">A ${battleScore(a)}</span>
        <span class="score-badge">B ${battleScore(b)}</span>
      </div>
    </div>
    <table class="comparison-table">
      <thead>
        <tr><th>Dimension</th><th>A</th><th>B</th><th>Edge</th></tr>
      </thead>
      <tbody>${battleRows(a, b)}</tbody>
    </table>
    <div class="battle-evidence">
      <article class="character-card">
        <h3>${escapeHtml(a.name)}</h3>
        <ul class="evidence-list">${battleEvidence(a)}</ul>
      </article>
      <article class="character-card">
        <h3>${escapeHtml(b.name)}</h3>
        <ul class="evidence-list">${battleEvidence(b)}</ul>
      </article>
    </div>
  `;
}

function render() {
  renderTabs();
  if (state.view === "battle") {
    renderBattle();
  } else {
    renderRanking();
  }
}

function bindEvents() {
  elements.tabs.forEach((button) => {
    button.addEventListener("click", () => {
      state.view = button.dataset.view;
      render();
    });
  });

  elements.searchFilter.addEventListener("input", (event) => {
    state.search = event.target.value;
    render();
  });
  elements.mediaFilter.addEventListener("change", (event) => {
    state.media = event.target.value;
    render();
  });
  elements.universeFilter.addEventListener("change", (event) => {
    state.universe = event.target.value;
    render();
  });
  elements.minScore.addEventListener("input", (event) => {
    state.min = event.target.value;
    render();
  });
  elements.maxScore.addEventListener("input", (event) => {
    state.max = event.target.value;
    render();
  });
  elements.battleA.addEventListener("change", (event) => {
    state.battleA = event.target.value;
    render();
  });
  elements.battleB.addEventListener("change", (event) => {
    state.battleB = event.target.value;
    render();
  });
  elements.battleMode.addEventListener("change", (event) => {
    state.battleMode = event.target.value;
    render();
  });
}

async function boot() {
  try {
    const response = await fetch("./data/characters.json");
    if (!response.ok) {
      throw new Error(`Failed to load data: ${response.status}`);
    }
    characters = await response.json();
    populateFilters();
    bindEvents();
    render();
  } catch (error) {
    elements.rankingList.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  }
}

boot();
