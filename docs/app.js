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
  battleAStage: "",
  battleBStage: "",
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
  battleConditionOptions: document.querySelector("#battle-condition-options"),
  battleA: document.querySelector("#battle-a"),
  battleB: document.querySelector("#battle-b"),
  battleAStage: document.querySelector("#battle-a-stage"),
  battleBStage: document.querySelector("#battle-b-stage"),
  battleOptions: document.querySelector("#battle-character-options"),
  battleAStageOptions: document.querySelector("#battle-a-stage-options"),
  battleBStageOptions: document.querySelector("#battle-b-stage-options"),
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
  state.battleAStage = params.get("aStage") ?? "";
  state.battleBStage = params.get("bStage") ?? "";

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
    if (state.battleAStage) params.set("aStage", state.battleAStage);
    if (state.battleBStage) params.set("bStage", state.battleBStage);
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
  elements.battleAStage.value = state.battleAStage;
  elements.battleBStage.value = state.battleBStage;
  elements.battleMode.value = state.battleMode;
  document.querySelectorAll(".condition-filter").forEach((checkbox) => {
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

  const battleOptions = characters
    .map(
      (character) =>
        `<option value="${escapeHtml(character.name)}" label="${escapeHtml(`${character.universe} / ${mediaLabels[character.media_type] ?? character.media_type}`)}"></option>`,
    )
    .join("");
  elements.battleOptions.innerHTML = battleOptions;
  updateBattleStageOptions();

  if (!state.battleA) {
    state.battleA = characters[0]?.name ?? "";
  }
  if (!state.battleB) {
    state.battleB = characters[1]?.name ?? characters[0]?.name ?? "";
  }

  const conditionOptionsHtml = renderConditionOptions();
  elements.conditionOptions.innerHTML = conditionOptionsHtml;
  elements.battleConditionOptions.innerHTML = conditionOptionsHtml;
  syncControls();
}

function renderConditionOptions() {
  return conditionMeta
    .map(
      (item) => `
        <label>
          <input type="checkbox" value="${escapeHtml(item.key)}" class="condition-filter">
          ${escapeHtml(item.label)}
        </label>
      `,
    )
    .join("");
}

function stageOptionsHtml(character) {
  return characterVersions(character)
    .map((version) => {
      const aliases = stageCandidates(version)
        .filter((candidate) => candidate !== version.label)
        .join(" / ");
      const label = aliases ? ` label="${escapeHtml(aliases)}"` : "";
      return `<option value="${escapeHtml(version.label)}"${label}></option>`;
    })
    .join("");
}

function updateBattleStageOptions() {
  if (!elements.battleAStageOptions || !elements.battleBStageOptions) return;
  elements.battleAStageOptions.innerHTML = stageOptionsHtml(battleCharacter(state.battleA));
  elements.battleBStageOptions.innerHTML = stageOptionsHtml(battleCharacter(state.battleB));
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
  const explicitItems = character.explicit_iq_evidence ?? [];
  const items = character.iq_evidence ?? [];
  if (!explicitItems.length && !items.length) {
    return '<li class="evidence-item"><strong>知性スコア</strong><span class="evidence-rule">一致するWikipedia根拠なし</span></li>';
  }
  const explicitEvidence = explicitItems
    .slice(0, 2)
    .map(
      (item) => `
        <li class="evidence-item">
          <strong>明示IQ ${escapeHtml(item.value)}</strong>: ${escapeHtml(item.sentence)}
          <span class="evidence-rule">${escapeHtml(item.rule)}</span>
        </li>
      `,
    )
    .join("");
  const scoreEvidence = items
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
  return explicitEvidence + scoreEvidence;
}

function characterInitials(name) {
  return Array.from(String(name ?? "").trim()).slice(0, 2).join("") || "?";
}

function explicitIqText(character) {
  const value = character.explicit_iq;
  return value !== null && value !== undefined && Number.isFinite(Number(value)) ? String(value) : "記述なし";
}

function explicitIqNumber(character) {
  const value = character.explicit_iq;
  return value !== null && value !== undefined && Number.isFinite(Number(value)) ? Number(value) : null;
}

function estimatedIqText(character) {
  const estimated = character.estimated_iq ?? {};
  const label = estimated.label || "推定不可";
  return estimated.range ? `${label}（${estimated.range}）` : label;
}

function confidenceText(character) {
  const confidence = character.estimated_iq?.confidence || "low";
  return { low: "低", medium: "中", high: "高" }[confidence] || confidence;
}

function intelligenceSummary(character) {
  return `
    <div class="intelligence-summary">
      <div>
        <span>明示IQ</span>
        <strong>${escapeHtml(explicitIqText(character))}</strong>
      </div>
      <div>
        <span>推定IQ</span>
        <strong>${escapeHtml(estimatedIqText(character))}</strong>
      </div>
      <div>
        <span>信頼度</span>
        <strong>${escapeHtml(confidenceText(character))}</strong>
      </div>
    </div>
  `;
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

function imageCredit(character) {
  if (!character.image_credit) {
    return "";
  }
  const sourceUrl = character.image_landing_url || character.image_license_url || "";
  const sourceLabel = character.image_license
    ? `${character.image_credit} / ${String(character.image_license).toUpperCase()}`
    : character.image_credit;
  if (sourceUrl) {
    return `<div class="image-credit">画像: <a href="${escapeHtml(sourceUrl)}">${escapeHtml(sourceLabel)}</a></div>`;
  }
  return `<div class="image-credit">画像: ${escapeHtml(sourceLabel)}</div>`;
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
          ${imageCredit(character)}
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
      ${intelligenceSummary(character)}
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

function normalizedQuery(value) {
  return String(value ?? "").trim().toLocaleLowerCase("ja");
}

function characterVersions(character) {
  return Array.isArray(character?.versions) ? character.versions : [];
}

function stageCandidates(version) {
  return [version?.label, ...(Array.isArray(version?.aliases) ? version.aliases : [])]
    .map((value) => String(value ?? "").trim())
    .filter(Boolean);
}

function battleCharacter(query) {
  const normalized = normalizedQuery(query);
  if (!normalized) return characters[0];
  return (
    characters.find((character) => normalizedQuery(character.name) === normalized) ??
    characters.find((character) => normalizedQuery(character.name).startsWith(normalized)) ??
    characters.find((character) => normalizedQuery(character.name).includes(normalized)) ??
    characters.find((character) => normalizedQuery(character.universe).includes(normalized)) ??
    characters[0]
  );
}

function battleVersion(character, stage) {
  const normalized = normalizedQuery(stage);
  if (!character || !normalized) return null;
  const versions = characterVersions(character);
  const byExact = versions.find((version) =>
    stageCandidates(version).some((candidate) => normalizedQuery(candidate) === normalized),
  );
  if (byExact) return byExact;
  const byPrefix = versions.find((version) =>
    stageCandidates(version).some((candidate) => normalizedQuery(candidate).startsWith(normalized)),
  );
  if (byPrefix) return byPrefix;
  return (
    versions.find((version) =>
      stageCandidates(version).some((candidate) => normalizedQuery(candidate).includes(normalized)),
    ) ?? null
  );
}

function battleEntry(characterQuery, stageQuery) {
  const character = battleCharacter(characterQuery);
  const requestedStage = String(stageQuery ?? "").trim();
  const version = battleVersion(character, requestedStage);
  return {
    character,
    record: version ?? character,
    requestedStage,
    stageLabel: version?.label ?? requestedStage,
    matchedVersion: Boolean(version),
  };
}

function battleDisplayName(entry) {
  const cleanStage = String(entry.stageLabel ?? "").trim();
  const name = entry.character?.name ?? entry.record?.name ?? "";
  return cleanStage ? `${name}（${cleanStage}）` : name;
}

function battleScore(entry) {
  return scoreFor(entry.record, state.battleMode);
}

function entryConditionFlags(entry) {
  return entry.record?.condition_flags ?? entry.character?.condition_flags ?? {};
}

function selectedConditionKeys() {
  return [...state.conditions].filter((key) => conditionKeys.includes(key));
}

function conditionMatchCount(entry, keys = selectedConditionKeys()) {
  const flags = entryConditionFlags(entry);
  return keys.filter((key) => Boolean(flags[key])).length;
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
  return `${battleDisplayName(winner)} が ${diff} 点差で${label}です。`;
}

function battleConditionSummary(a, b) {
  const keys = selectedConditionKeys();
  if (!keys.length) return "";
  const aCount = conditionMatchCount(a, keys);
  const bCount = conditionMatchCount(b, keys);
  const aFlags = entryConditionFlags(a);
  const bFlags = entryConditionFlags(b);
  const rows = keys
    .map((key) => {
      const aMatch = Boolean(aFlags[key]);
      const bMatch = Boolean(bFlags[key]);
      return `
        <tr>
          <td>${escapeHtml(conditionLabels[key] ?? key)}</td>
          <td>${aMatch ? "該当" : "非該当"}</td>
          <td>${bMatch ? "該当" : "非該当"}</td>
        </tr>
      `;
    })
    .join("");
  return `
    <section class="condition-match-panel">
      <div class="condition-match-summary">
        <span>A 条件一致 ${aCount}/${keys.length}</span>
        <span>B 条件一致 ${bCount}/${keys.length}</span>
      </div>
      <table class="comparison-table condition-table">
        <thead>
          <tr><th>条件</th><th>A</th><th>B</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </section>
  `;
}

function battleRows(a, b) {
  const aName = battleDisplayName(a);
  const bName = battleDisplayName(b);
  const aRecord = a.record;
  const bRecord = b.record;
  const rows = scoreKeys.map((key) => {
    const aValue = Number(aRecord.scores?.[key] ?? 0);
    const bValue = Number(bRecord.scores?.[key] ?? 0);
    const edge = aValue === bValue ? "互角" : aValue > bValue ? aName : bName;
    return `<tr><td>${escapeHtml(scoreLabels[key] ?? key)}</td><td>${aValue}</td><td>${bValue}</td><td>${escapeHtml(edge)}</td></tr>`;
  });

  const iqEdge =
    Number(aRecord.iq_score ?? 0) === Number(bRecord.iq_score ?? 0)
      ? "互角"
      : Number(aRecord.iq_score ?? 0) > Number(bRecord.iq_score ?? 0)
        ? aName
        : bName;
  rows.push(
    `<tr><td>知性スコア</td><td>${Number(aRecord.iq_score ?? 0)}</td><td>${Number(bRecord.iq_score ?? 0)}</td><td>${escapeHtml(iqEdge)}</td></tr>`,
  );
  const aExplicitIq = explicitIqNumber(aRecord);
  const bExplicitIq = explicitIqNumber(bRecord);
  const explicitEdge =
    aExplicitIq !== null && bExplicitIq !== null
      ? aExplicitIq === bExplicitIq
        ? "互角"
        : aExplicitIq > bExplicitIq
          ? aName
          : bName
      : "比較不可";
  rows.push(
    `<tr><td>明示IQ</td><td>${escapeHtml(explicitIqText(aRecord))}</td><td>${escapeHtml(explicitIqText(bRecord))}</td><td>${escapeHtml(explicitEdge)}</td></tr>`,
  );
  rows.push(
    `<tr><td>推定IQ</td><td>${escapeHtml(estimatedIqText(aRecord))}</td><td>${escapeHtml(estimatedIqText(bRecord))}</td><td>${escapeHtml(iqEdge)}</td></tr>`,
  );
  return rows.join("");
}

function battleEvidence(entry) {
  const character = entry.record;
  const items =
    state.battleMode === "iq"
      ? [...(character.explicit_iq_evidence ?? []), ...(character.iq_evidence ?? [])]
      : state.battleMode === "balanced"
        ? [
            ...(character.explicit_iq_evidence ?? []),
            ...(character.iq_evidence ?? []),
            ...scoreKeys.flatMap((key) => character.score_evidence?.[key] ?? []),
          ]
      : scoreKeys.flatMap((key) => character.score_evidence?.[key] ?? []);

  const sorted = [...items].sort((a, b) => Number(b.points ?? b.value ?? 0) - Number(a.points ?? a.value ?? 0)).slice(0, 4);
  if (!sorted.length) {
    return '<li class="evidence-item">一致するWikipedia根拠なし</li>';
  }
  return sorted
    .map(
      (item) => `
        <li class="evidence-item">
          ${escapeHtml(item.sentence)}
          <span class="evidence-rule">${escapeHtml(item.rule)}${item.value ? ` / IQ ${escapeHtml(item.value)}` : ` / +${escapeHtml(item.points)}`}</span>
        </li>
      `,
    )
    .join("");
}

function stageNotice(entry, label) {
  if (!entry.requestedStage) return "";
  if (entry.matchedVersion) {
    return `<p class="stage-note">${escapeHtml(label)}: ${escapeHtml(entry.stageLabel)} の時点別データを使用中</p>`;
  }
  return `<p class="stage-note">${escapeHtml(label)}: 「${escapeHtml(entry.requestedStage)}」の時点別データがないため通常データで比較</p>`;
}

function renderBattle() {
  if (!characters.length) return;
  const a = battleEntry(state.battleA, state.battleAStage);
  const b = battleEntry(state.battleB, state.battleBStage);
  const aName = battleDisplayName(a);
  const bName = battleDisplayName(b);
  const stageNotes = [stageNotice(a, "A"), stageNotice(b, "B")].join("");

  elements.battleResult.innerHTML = `
    <div class="verdict">
      <h3>${escapeHtml(battleVerdict(a, b))}</h3>
      <div class="score-stack">
        <span class="score-badge">A ${battleScore(a)}</span>
        <span class="score-badge">B ${battleScore(b)}</span>
      </div>
    </div>
    ${stageNotes ? `<div class="stage-notes">${stageNotes}</div>` : ""}
    ${battleConditionSummary(a, b)}
    <table class="comparison-table">
      <thead>
        <tr><th>項目</th><th>A</th><th>B</th><th>優勢</th></tr>
      </thead>
      <tbody>${battleRows(a, b)}</tbody>
    </table>
    <div class="battle-evidence">
      <article class="character-card">
        <h3>${escapeHtml(aName)}</h3>
        <details class="evidence-details">
          <summary>比較根拠を表示</summary>
          <ul class="evidence-list">${battleEvidence(a)}</ul>
        </details>
      </article>
      <article class="character-card">
        <h3>${escapeHtml(bName)}</h3>
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
  updateBattleStageOptions();
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
  [elements.conditionOptions, elements.battleConditionOptions].forEach((container) => {
    container.addEventListener("change", (event) => {
      if (!event.target.classList.contains("condition-filter")) return;
      if (event.target.checked) {
        state.conditions.add(event.target.value);
      } else {
        state.conditions.delete(event.target.value);
      }
      render();
    });
  });
  elements.battleA.addEventListener("input", (event) => {
    state.battleA = event.target.value;
    render();
  });
  elements.battleB.addEventListener("input", (event) => {
    state.battleB = event.target.value;
    render();
  });
  elements.battleAStage.addEventListener("input", (event) => {
    state.battleAStage = event.target.value;
    render();
  });
  elements.battleBStage.addEventListener("input", (event) => {
    state.battleBStage = event.target.value;
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
