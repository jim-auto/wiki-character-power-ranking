const scoreKeys = ["attack", "defense", "speed", "abilities", "feats", "scale"];
const scoreLabels = {
  attack: "攻撃",
  defense: "防御",
  speed: "速度",
  abilities: "能力",
  feats: "実績",
  scale: "影響範囲",
};
const mediaLabels = {
  manga: "漫画",
  anime: "アニメ",
  movie: "映画",
  comic: "コミック",
};
const conditionMeta = [
  { key: "superpower", label: "超能力あり" },
  { key: "modified", label: "改造あり" },
  { key: "technology", label: "技術/装備" },
  { key: "magic", label: "魔法/呪い" },
  { key: "weapon", label: "武器あり" },
  { key: "non_human", label: "人間以外" },
  { key: "god_or_deity", label: "神格" },
  { key: "alien", label: "宇宙人" },
  { key: "robot_ai", label: "ロボット/AI" },
  { key: "martial_artist", label: "格闘" },
  { key: "military", label: "軍人/兵士" },
  { key: "leader", label: "リーダー" },
  { key: "detective_genius", label: "天才/探偵" },
  { key: "transformation", label: "変身" },
  { key: "immortal", label: "不死/再生" },
];
const conditionKeys = conditionMeta.map((item) => item.key);
const conditionLabels = Object.fromEntries(conditionMeta.map((item) => [item.key, item.label]));

const state = {
  view: "power",
  search: "",
  media: "all",
  universe: "all",
  collection: "all",
  min: "",
  max: "",
  conditions: new Set(),
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
  collectionFilter: document.querySelector("#collection-filter"),
  minScore: document.querySelector("#min-score"),
  maxScore: document.querySelector("#max-score"),
  conditionOptions: document.querySelector("#condition-options"),
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

function applyQueryState() {
  const params = new URLSearchParams(window.location.search);
  const view = params.get("view");
  const media = params.get("media");
  const collection = params.get("collection");
  const battleMode = params.get("battleMode");

  if (["power", "iq", "battle"].includes(view)) state.view = view;
  if (["all", "manga", "anime", "movie", "comic"].includes(media)) state.media = media;
  if (["all", "jump_manga", "marvel", "dc"].includes(collection)) state.collection = collection;
  if (["power", "iq", "balanced"].includes(battleMode)) state.battleMode = battleMode;

  state.search = params.get("q") ?? "";
  state.universe = params.get("universe") ?? "all";
  state.min = params.get("min") ?? "";
  state.max = params.get("max") ?? "";
  state.battleA = params.get("a") ?? "";
  state.battleB = params.get("b") ?? "";

  const conditions = (params.get("conditions") ?? "")
    .split(",")
    .map((value) => value.trim())
    .filter((value) => conditionKeys.includes(value));
  conditionKeys.forEach((key) => {
    if (params.get(key) === "1") conditions.push(key);
  });
  state.conditions = new Set(conditions);
}

function updateUrl() {
  const params = new URLSearchParams();
  if (state.view !== "power") params.set("view", state.view);
  if (state.search) params.set("q", state.search);
  if (state.media !== "all") params.set("media", state.media);
  if (state.universe !== "all") params.set("universe", state.universe);
  if (state.collection !== "all") params.set("collection", state.collection);
  if (state.min !== "") params.set("min", state.min);
  if (state.max !== "") params.set("max", state.max);
  if (state.conditions.size) params.set("conditions", [...state.conditions].join(","));
  if (state.view === "battle") {
    if (state.battleA) params.set("a", state.battleA);
    if (state.battleB) params.set("b", state.battleB);
    if (state.battleMode !== "power") params.set("battleMode", state.battleMode);
  }

  const nextUrl = params.toString()
    ? `${window.location.pathname}?${params.toString()}`
    : window.location.pathname;
  window.history.replaceState(null, "", nextUrl);
}

function syncControls() {
  elements.searchFilter.value = state.search;
  elements.mediaFilter.value = state.media;
  elements.universeFilter.value = state.universe;
  elements.collectionFilter.value = state.collection;
  elements.minScore.value = state.min;
  elements.maxScore.value = state.max;
  elements.battleA.value = state.battleA;
  elements.battleB.value = state.battleB;
  elements.battleMode.value = state.battleMode;
  elements.conditionOptions.querySelectorAll(".condition-filter").forEach((checkbox) => {
    checkbox.checked = state.conditions.has(checkbox.value);
  });
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
        ...(character.collection_tags ?? []),
        character.wikipedia_url,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    })
    .filter((character) => state.media === "all" || character.media_type === state.media)
    .filter((character) => state.universe === "all" || character.universe === state.universe)
    .filter(
      (character) =>
        state.collection === "all" || (character.collection_tags ?? []).includes(state.collection),
    )
    .filter((character) => {
      if (!state.conditions.size) return true;
      const flags = character.condition_flags ?? {};
      return [...state.conditions].every((key) => Boolean(flags[key]));
    })
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
    '<option value="all">すべて</option>',
    ...universes.map((universe) => `<option value="${escapeHtml(universe)}">${escapeHtml(universe)}</option>`),
  ].join("");
  if (state.universe !== "all" && !universes.includes(state.universe)) state.universe = "all";

  const options = characters
    .map((character) => `<option value="${escapeHtml(character.name)}">${escapeHtml(character.name)}</option>`)
    .join("");
  elements.battleA.innerHTML = options;
  elements.battleB.innerHTML = options;

  if (!characters.some((character) => character.name === state.battleA)) {
    state.battleA = characters[0]?.name ?? "";
  }
  if (!characters.some((character) => character.name === state.battleB)) {
    state.battleB = characters[1]?.name ?? characters[0]?.name ?? "";
  }

  elements.conditionOptions.innerHTML = conditionMeta
    .map(
      (item) => `
        <label>
          <input type="checkbox" value="${escapeHtml(item.key)}" class="condition-filter">
          ${escapeHtml(item.label)}
        </label>
      `,
    )
    .join("");
  syncControls();
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
            <span>${escapeHtml(scoreLabels[key] ?? key)}</span>
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
        return `<li class="evidence-item"><strong>${escapeHtml(scoreLabels[key] ?? key)}</strong><span class="evidence-rule">一致するWikipedia根拠なし</span></li>`;
      }
      const top = items[0];
      return `
        <li class="evidence-item">
          <strong>${escapeHtml(scoreLabels[key] ?? key)}</strong>: ${escapeHtml(top.sentence)}
          <span class="evidence-rule">${escapeHtml(top.rule)} / +${escapeHtml(top.points)}</span>
        </li>
      `;
    })
    .join("");
}

function evidenceForIq(character) {
  const items = character.iq_evidence ?? [];
  if (!items.length) {
    return '<li class="evidence-item"><strong>知性スコア</strong><span class="evidence-rule">一致するWikipedia根拠なし</span></li>';
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

function characterInitials(name) {
  return Array.from(String(name ?? "").trim()).slice(0, 2).join("") || "?";
}

function characterImage(character) {
  const alt = character.image_alt || character.name || "";
  if (!character.image_url) {
    return `<div class="character-image is-empty" aria-hidden="true"><span>${escapeHtml(characterInitials(character.name))}</span></div>`;
  }
  return `
    <div class="character-image">
      <img
        src="${escapeHtml(character.image_url)}"
        alt="${escapeHtml(alt)}"
        loading="lazy"
        decoding="async"
        onerror="this.closest('.character-image').classList.add('is-empty'); this.remove();"
      >
      <span aria-hidden="true">${escapeHtml(characterInitials(character.name))}</span>
    </div>
  `;
}

function characterCard(character, index) {
  const primaryScore = scoreFor(character);
  const titleScore = state.view === "iq" ? `知性スコア ${primaryScore}点` : `${primaryScore}/60`;
  const evidence = state.view === "iq" ? evidenceForIq(character) : evidenceForPower(character);
  const iqWidth = Math.max(0, Math.min(100, Number(character.iq_score ?? 0) * 10));
  const flags = character.condition_flags ?? {};
  const flagChips = conditionKeys
    .filter((key) => flags[key])
    .map((key) => `<span class="flag-chip">${escapeHtml(conditionLabels[key] ?? key)}</span>`)
    .join("");

  return `
    <article class="character-card">
      <div class="character-main">
        <div class="rank-token">${index + 1}</div>
        ${characterImage(character)}
        <div>
          <h3>${escapeHtml(character.name)}</h3>
          <div class="meta-line">
            <span>${escapeHtml(mediaLabels[character.media_type] ?? character.media_type)}</span>
            <span>${escapeHtml(character.universe)}</span>
            <a href="${escapeHtml(character.wikipedia_url)}">出典</a>
          </div>
          <div class="flag-line">${flagChips}</div>
        </div>
        <div class="score-stack">
          <span class="score-badge">${escapeHtml(titleScore)}</span>
          <span class="tier-badge">Tier ${escapeHtml(character.tier ?? "C")}</span>
        </div>
      </div>
      <div class="dimension-grid">${dimensionBars(character)}</div>
      <div class="dimension">
        <div class="dimension-label"><span>知性スコア</span><span>${escapeHtml(character.iq_score ?? 0)}</span></div>
        <div class="bar" aria-hidden="true"><div class="bar-fill iq" style="width: ${iqWidth}%"></div></div>
      </div>
      <details class="evidence-details">
        <summary>根拠文を表示</summary>
        <ul class="evidence-list">${evidence}</ul>
      </details>
    </article>
  `;
}

function renderRanking() {
  const ranked = filteredCharacters();
  elements.rankingTitle.textContent = state.view === "iq" ? "知性スコアランキング" : "強さランキング";
  elements.resultCount.textContent = String(ranked.length);
  elements.rankingList.innerHTML = ranked.length
    ? ranked.map(characterCard).join("")
    : '<div class="empty-state">該当するキャラクターがありません。</div>';
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
    return "現在の根拠スコアでは引き分けです。";
  }
  const winner = aScore > bScore ? a : b;
  const label = diff >= 8 ? "優勢" : "やや優勢";
  return `${winner.name} が ${diff} 点差で${label}です。`;
}

function battleRows(a, b) {
  const rows = scoreKeys.map((key) => {
    const aValue = Number(a.scores?.[key] ?? 0);
    const bValue = Number(b.scores?.[key] ?? 0);
    const edge = aValue === bValue ? "互角" : aValue > bValue ? a.name : b.name;
    return `<tr><td>${escapeHtml(scoreLabels[key] ?? key)}</td><td>${aValue}</td><td>${bValue}</td><td>${escapeHtml(edge)}</td></tr>`;
  });

  const iqEdge =
    Number(a.iq_score ?? 0) === Number(b.iq_score ?? 0)
      ? "互角"
      : Number(a.iq_score ?? 0) > Number(b.iq_score ?? 0)
        ? a.name
        : b.name;
  rows.push(
    `<tr><td>知性スコア</td><td>${Number(a.iq_score ?? 0)}</td><td>${Number(b.iq_score ?? 0)}</td><td>${escapeHtml(iqEdge)}</td></tr>`,
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
    return '<li class="evidence-item">一致するWikipedia根拠なし</li>';
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
        <tr><th>項目</th><th>A</th><th>B</th><th>優勢</th></tr>
      </thead>
      <tbody>${battleRows(a, b)}</tbody>
    </table>
    <div class="battle-evidence">
      <article class="character-card">
        <h3>${escapeHtml(a.name)}</h3>
        <details class="evidence-details">
          <summary>比較根拠を表示</summary>
          <ul class="evidence-list">${battleEvidence(a)}</ul>
        </details>
      </article>
      <article class="character-card">
        <h3>${escapeHtml(b.name)}</h3>
        <details class="evidence-details">
          <summary>比較根拠を表示</summary>
          <ul class="evidence-list">${battleEvidence(b)}</ul>
        </details>
      </article>
    </div>
  `;
}

function render() {
  renderTabs();
  syncControls();
  if (state.view === "battle") {
    renderBattle();
  } else {
    renderRanking();
  }
  updateUrl();
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
  elements.collectionFilter.addEventListener("change", (event) => {
    state.collection = event.target.value;
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
  elements.conditionOptions.addEventListener("change", (event) => {
    if (!event.target.classList.contains("condition-filter")) return;
    if (event.target.checked) {
      state.conditions.add(event.target.value);
    } else {
      state.conditions.delete(event.target.value);
    }
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
      throw new Error(`データの読み込みに失敗しました: ${response.status}`);
    }
    characters = await response.json();
    applyQueryState();
    populateFilters();
    bindEvents();
    render();
  } catch (error) {
    elements.rankingList.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  }
}

boot();
