let videoInput = null;
let intervalInput = null;
let uploadBtn = null;
let refreshBtn = null;
let uploadStatus = null;
let videoList = null;
let queryInput = null;
let topKInput = null;
let searchBtn = null;
let resultsGrid = null;
let videoPlayer = null;
let playerMeta = null;
let activeCaseMeta = null;
let caseList = null;
let workspace = null;
let caseSidebar = null;
let sidebarResizeHandle = null;

const state = {
  cases: [],
  activeCaseId: null,
};
let caseSwitchVersion = 0;
let caseStateVersion = 0;
let listenersBound = false;
let initStarted = false;
const playbackCache = new Map();
const searchCache = new Map();
const SIDEBAR_MIN_WIDTH = 220;
const SIDEBAR_MAX_WIDTH = 560;

function bindDomElements() {
  videoInput = document.getElementById("videoInput");
  intervalInput = document.getElementById("intervalInput");
  uploadBtn = document.getElementById("uploadBtn");
  refreshBtn = document.getElementById("refreshBtn");
  uploadStatus = document.getElementById("uploadStatus");
  videoList = document.getElementById("videoList");
  queryInput = document.getElementById("queryInput");
  topKInput = document.getElementById("topKInput");
  searchBtn = document.getElementById("searchBtn");
  resultsGrid = document.getElementById("resultsGrid");
  videoPlayer = document.getElementById("videoPlayer");
  playerMeta = document.getElementById("playerMeta");
  activeCaseMeta = document.getElementById("activeCaseMeta");
  caseList = document.getElementById("caseList");
  workspace = document.querySelector(".workspace");
  caseSidebar = document.querySelector(".case-sidebar");
  sidebarResizeHandle = document.getElementById("sidebarResizeHandle");
}

function setStatus(message, kind = "") {
  if (!uploadStatus) {
    return;
  }
  uploadStatus.textContent = message;
  uploadStatus.className = `status ${kind}`.trim();
}

function formatError(error) {
  if (!error) return "Unknown error";

  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === "string") {
    return error;
  }

  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function formatTime(totalSeconds) {
  const sec = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const hours = Math.floor(sec / 3600);
  const minutes = Math.floor((sec % 3600) / 60);
  const seconds = sec % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function formatCaseCreatedAt(createdAt) {
  const raw = String(createdAt || "").trim();
  if (!raw) {
    return "Unknown";
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    return raw;
  }
  return parsed.toLocaleString();
}

function ensureActiveCaseId() {
  if (!state.activeCaseId) {
    throw new Error("No active case available. Create a case first.");
  }
  return state.activeCaseId;
}

function withCaseQuery(path, caseId) {
  return `${path}?case_id=${encodeURIComponent(caseId)}`;
}

function setPlaybackUrl(filename, timestampSeconds) {
  const url = new URL(window.location.href);
  if (state.activeCaseId) {
    url.searchParams.set("case", state.activeCaseId);
  }
  url.searchParams.set("video", filename);
  url.searchParams.set("t", Number(timestampSeconds).toFixed(2));
  history.replaceState({}, "", url);
}

function setCaseUrl(caseId) {
  const url = new URL(window.location.href);
  if (caseId) {
    url.searchParams.set("case", String(caseId));
  } else {
    url.searchParams.delete("case");
  }
  url.searchParams.delete("video");
  url.searchParams.delete("t");
  history.replaceState({}, "", url);
}

function setPlaybackCache(caseId, filename, timestampSeconds) {
  const normalizedCaseId = String(caseId || "").trim();
  const normalizedFilename = String(filename || "").trim();
  if (!normalizedCaseId || !normalizedFilename) {
    return;
  }
  const parsedTimestamp = Number(timestampSeconds);
  const safeTimestamp = Number.isFinite(parsedTimestamp) && parsedTimestamp >= 0
    ? parsedTimestamp
    : 0;
  playbackCache.set(normalizedCaseId, {
    filename: normalizedFilename,
    timestampSeconds: safeTimestamp,
  });
}

function clearPlaybackCache(caseId) {
  if (!caseId) {
    return;
  }
  playbackCache.delete(String(caseId));
}

function saveActiveCasePlaybackSnapshot() {
  if (!videoPlayer || !state.activeCaseId) {
    return;
  }
  const filename = String(videoPlayer.dataset.filename || "").trim();
  if (!filename) {
    return;
  }
  setPlaybackCache(state.activeCaseId, filename, videoPlayer.currentTime || 0);
}

async function fetchJson(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    throw new Error(`Network error: ${formatError(error)}`);
  }

  let rawBody = "";
  try {
    rawBody = await response.text();
  } catch {
    rawBody = "";
  }

  let payload = null;
  if (rawBody) {
    try {
      payload = JSON.parse(rawBody);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    let detail = "";
    if (payload && typeof payload === "object") {
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      } else if (payload.detail !== undefined && payload.detail !== null) {
        detail = formatError(payload.detail);
      } else {
        detail = formatError(payload);
      }
    } else if (rawBody.trim()) {
      detail = rawBody.trim();
    } else {
      detail = response.statusText || "Request failed";
    }
    throw new Error(`[${response.status}] ${detail}`);
  }

  if (!rawBody) {
    return {};
  }

  if (payload === null) {
    throw new Error(`[${response.status}] Invalid JSON response`);
  }

  return payload;
}

function normalizeCases(rawCases) {
  const list = Array.isArray(rawCases) ? rawCases : [];
  const normalized = [];
  for (const item of list) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const caseId = typeof item.case_id === "string" ? item.case_id.trim() : "";
    if (!caseId) {
      continue;
    }
    const name =
      typeof item.name === "string" && item.name.trim()
        ? item.name.trim()
        : caseId;
    const createdAt = typeof item.created_at === "string" ? item.created_at.trim() : "";
    normalized.push({ case_id: caseId, name, created_at: createdAt });
  }
  return normalized;
}

function clearResults() {
  renderResults([]);
}

function syncWorkspaceVisibility() {
  if (!workspace) {
    return;
  }
  workspace.style.display = state.activeCaseId ? "flex" : "none";
  if (activeCaseMeta) {
    if (!state.activeCaseId) {
      activeCaseMeta.textContent = "";
    } else {
      const activeCase = state.cases.find((item) => item.case_id === state.activeCaseId);
      const activeName = activeCase?.name || state.activeCaseId;
      const createdAtLabel = formatCaseCreatedAt(activeCase?.created_at);
      activeCaseMeta.textContent = `Active Case: ${activeName} (${state.activeCaseId}) | Created: ${createdAtLabel}`;
    }
  }
}

function defaultCaseName() {
  return `Case ${String(state.cases.length + 1).padStart(3, "0")}`;
}

function clampSidebarWidth(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return SIDEBAR_MIN_WIDTH;
  }
  return Math.max(SIDEBAR_MIN_WIDTH, Math.min(SIDEBAR_MAX_WIDTH, Math.round(numeric)));
}

function setSidebarWidth(widthPx) {
  const clamped = clampSidebarWidth(widthPx);
  document.documentElement.style.setProperty("--sidebar-width", `${clamped}px`);
}

function setupSidebarResize() {
  if (!caseSidebar || !sidebarResizeHandle) {
    return;
  }

  let resizing = false;
  let startX = 0;
  let startWidth = 0;

  const onPointerMove = (event) => {
    if (!resizing) {
      return;
    }
    const deltaX = event.clientX - startX;
    setSidebarWidth(startWidth + deltaX);
  };

  const stopResize = () => {
    if (!resizing) {
      return;
    }
    resizing = false;
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", stopResize);
    window.removeEventListener("pointercancel", stopResize);
  };

  sidebarResizeHandle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    resizing = true;
    startX = event.clientX;
    startWidth = caseSidebar.getBoundingClientRect().width;
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", stopResize);
    window.addEventListener("pointercancel", stopResize);
  });
}

function normalizeTopK(value, fallback = 10) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(1, Math.min(100, parsed));
}

function defaultTopK() {
  if (!topKInput) {
    return 10;
  }
  const fromDefault = normalizeTopK(topKInput.defaultValue, NaN);
  if (Number.isFinite(fromDefault)) {
    return fromDefault;
  }
  const fromAttr = normalizeTopK(topKInput.getAttribute("value"), NaN);
  if (Number.isFinite(fromAttr)) {
    return fromAttr;
  }
  return 10;
}

function searchKey(query, topK) {
  return `${query}\u0000${topK}`;
}

function ensureCaseSearchCache(caseId) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    return null;
  }
  let caseCache = searchCache.get(normalizedCaseId);
  if (!caseCache) {
    caseCache = {
      activeKey: null,
      entries: new Map(),
    };
    searchCache.set(normalizedCaseId, caseCache);
  }
  return caseCache;
}

function cacheSearchResults(caseId, query, topK, results, count) {
  const caseCache = ensureCaseSearchCache(caseId);
  if (!caseCache) {
    return;
  }
  const normalizedQuery = String(query || "").trim();
  const normalizedTopK = normalizeTopK(topK, defaultTopK());
  const key = searchKey(normalizedQuery, normalizedTopK);
  const normalizedResults = Array.isArray(results) ? results : [];
  caseCache.entries.set(key, {
    query: normalizedQuery,
    topK: normalizedTopK,
    results: normalizedResults,
    count: Number.isFinite(Number(count)) ? Number(count) : normalizedResults.length,
  });
  caseCache.activeKey = key;
}

function getActiveSearchCache(caseId) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    return null;
  }
  const caseCache = searchCache.get(normalizedCaseId);
  if (!caseCache || !caseCache.activeKey) {
    return null;
  }
  return caseCache.entries.get(caseCache.activeKey) || null;
}

function clearSearchUiForCase() {
  if (queryInput) {
    queryInput.value = "";
  }
  if (topKInput) {
    topKInput.value = String(defaultTopK());
  }
  clearResults();
}

function restoreSearchForCase(caseId) {
  const cached = getActiveSearchCache(caseId);
  if (!cached) {
    clearSearchUiForCase();
    return false;
  }
  if (queryInput) {
    queryInput.value = cached.query;
  }
  if (topKInput) {
    topKInput.value = String(cached.topK);
  }
  renderResults(cached.results);
  return true;
}

function removeVideoFromSearchCache(caseId, filename) {
  const normalizedCaseId = String(caseId || "").trim();
  const normalizedFilename = String(filename || "").trim();
  if (!normalizedCaseId || !normalizedFilename) {
    return;
  }

  const caseCache = searchCache.get(normalizedCaseId);
  if (!caseCache) {
    return;
  }

  for (const [key, entry] of caseCache.entries.entries()) {
    if (!entry || !Array.isArray(entry.results)) {
      continue;
    }
    const filteredResults = entry.results.filter(
      (item) => item && item.video_filename !== normalizedFilename,
    );
    caseCache.entries.set(key, {
      ...entry,
      results: filteredResults,
      count: filteredResults.length,
    });
  }
}

function resetPlayerForCase(caseId = null) {
  if (!videoPlayer || !playerMeta) {
    return;
  }
  const normalizedCaseId = caseId ? String(caseId) : "";
  videoPlayer.pause();
  videoPlayer.removeAttribute("src");
  videoPlayer.load();
  videoPlayer.dataset.filename = "";
  videoPlayer.dataset.videoUrl = "";
  videoPlayer.dataset.caseId = normalizedCaseId;
  playerMeta.textContent = normalizedCaseId
    ? `Case ${normalizedCaseId}: select a result to play.`
    : "Select a result to play.";
}

function restorePlaybackForCase(caseId, videos) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    resetPlayerForCase(null);
    return;
  }

  const cached = playbackCache.get(normalizedCaseId);
  if (!cached) {
    resetPlayerForCase(normalizedCaseId);
    return;
  }

  const list = Array.isArray(videos) ? videos : [];
  const match = list.find((item) => item && item.filename === cached.filename);
  if (!match) {
    clearPlaybackCache(normalizedCaseId);
    resetPlayerForCase(normalizedCaseId);
    return;
  }

  const fallbackVideoUrl = `/media/cases/${encodeURIComponent(normalizedCaseId)}/videos/${encodeURIComponent(cached.filename)}`;
  playVideoAt(
    cached.filename,
    match.video_url || fallbackVideoUrl,
    cached.timestampSeconds || 0,
    { autoPlay: false },
  );
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function markCaseStateChanged() {
  caseStateVersion += 1;
}

function upsertCase(caseId, name, createdAt = "") {
  const normalizedId = String(caseId || "").trim();
  if (!normalizedId) {
    return;
  }
  const normalizedName = String(name || normalizedId).trim() || normalizedId;
  const normalizedCreatedAt = String(createdAt || "").trim();
  const existingIndex = state.cases.findIndex((item) => item.case_id === normalizedId);
  if (existingIndex >= 0) {
    state.cases[existingIndex] = {
      ...state.cases[existingIndex],
      name: normalizedName,
      created_at: normalizedCreatedAt || state.cases[existingIndex].created_at || "",
    };
  } else {
    state.cases = [
      ...state.cases,
      { case_id: normalizedId, name: normalizedName, created_at: normalizedCreatedAt },
    ];
  }
}

function renderCaseList() {
  if (!caseList) {
    return;
  }
  caseList.innerHTML = "";

  if (!state.cases.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No cases yet. Click + New Case to begin.";
    caseList.appendChild(empty);
    return;
  }

  state.cases.forEach((item) => {
    const row = document.createElement("div");
    row.className = "case-row";

    const caseButton = document.createElement("button");
    caseButton.type = "button";
    caseButton.className = "case-item";
    if (item.case_id === state.activeCaseId) {
      caseButton.classList.add("active");
    }

    const caseName = document.createElement("span");
    caseName.className = "case-item-name";
    caseName.textContent = item.name;
    caseButton.title = item.case_id;

    caseButton.appendChild(caseName);
    caseButton.addEventListener("click", () => {
      selectCase(item.case_id);
    });

    const renameButton = document.createElement("button");
    renameButton.type = "button";
    renameButton.className = "case-rename-btn";
    renameButton.textContent = "Rename";
    renameButton.title = `Rename ${item.case_id}`;
    renameButton.addEventListener("click", (event) => {
      event.stopPropagation();
      renameCase(item.case_id);
    });

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "case-delete-btn";
    deleteButton.textContent = "Delete";
    deleteButton.title = `Delete ${item.case_id}`;
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteCase(item.case_id);
    });

    row.appendChild(caseButton);
    row.appendChild(renameButton);
    row.appendChild(deleteButton);
    caseList.appendChild(row);
  });
}

async function loadCases() {
  const requestVersion = caseStateVersion;
  const payload = await fetchJson("/cases");
  const rawCases = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.cases)
      ? payload.cases
      : [];
  const backendCases = normalizeCases(rawCases);
  const stateChangedDuringRequest = requestVersion !== caseStateVersion;
  console.log("RAW /cases response:", payload);
  console.log("NORMALIZED cases:", backendCases);

  if (backendCases.length > 0) {
    if (!stateChangedDuringRequest) {
      state.cases = backendCases;
    } else {
      const merged = [...state.cases];
      backendCases.forEach((item) => {
        const existingIndex = merged.findIndex((entry) => entry.case_id === item.case_id);
        if (existingIndex >= 0) {
          merged[existingIndex] = item;
        } else {
          merged.push(item);
        }
      });
      state.cases = merged;
    }
  } else if (!state.cases.length) {
    state.cases = [];
  }

  if (state.cases.length > 0) {
    if (
      !stateChangedDuringRequest
      && (
        !state.activeCaseId
        || !state.cases.some((item) => item.case_id === state.activeCaseId)
      )
    ) {
      state.activeCaseId = state.cases[0].case_id;
    }
  } else if (!stateChangedDuringRequest) {
    state.activeCaseId = null;
  }

  const validCaseIds = new Set(state.cases.map((item) => item.case_id));
  for (const cachedCaseId of playbackCache.keys()) {
    if (!validCaseIds.has(cachedCaseId)) {
      playbackCache.delete(cachedCaseId);
    }
  }
  for (const cachedCaseId of searchCache.keys()) {
    if (!validCaseIds.has(cachedCaseId)) {
      searchCache.delete(cachedCaseId);
    }
  }

  console.log("Active case:", state.activeCaseId);
  syncWorkspaceVisibility();
  return state.cases;
}

async function loadCasesWithRetry(maxAttempts = 3) {
  let lastError = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      return await loadCases();
    } catch (error) {
      lastError = error;
      if (attempt < maxAttempts) {
        await sleep(300 * attempt);
      }
    }
  }
  throw lastError || new Error("Unable to load cases");
}

function renderVideoList(videos) {
  if (!videoList) {
    return;
  }
  videoList.innerHTML = "";
  if (!videos.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No uploaded videos yet.";
    videoList.appendChild(empty);
    return;
  }

  videos.forEach((video) => {
    const row = document.createElement("div");
    row.className = "video-row";

    const meta = document.createElement("div");
    meta.className = "video-meta";

    const name = document.createElement("div");
    name.className = "video-name";
    name.textContent = video.filename;

    const detail = document.createElement("div");
    detail.className = "video-detail";
    detail.textContent = `${formatBytes(video.size_bytes)} | indexed frames: ${video.indexed_frames}`;

    meta.appendChild(name);
    meta.appendChild(detail);

    const openBtn = document.createElement("button");
    openBtn.type = "button";
    openBtn.className = "ghost";
    openBtn.textContent = "Play";
    openBtn.addEventListener("click", () => {
      playVideoAt(video.filename, video.video_url, 0);
    });

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "danger";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", () => {
      deleteVideo(video.filename);
    });

    const actions = document.createElement("div");
    actions.className = "video-actions";
    actions.appendChild(openBtn);
    actions.appendChild(deleteBtn);

    row.appendChild(meta);
    row.appendChild(actions);
    videoList.appendChild(row);
  });
}

async function refreshVideos(caseId = null, expectedSwitchVersion = null) {
  const resolvedCaseId = caseId || ensureActiveCaseId();
  if (!resolvedCaseId) {
    renderVideoList([]);
    return;
  }

  const switchVersionAtRequest = expectedSwitchVersion;
  const payload = await fetchJson(withCaseQuery("/videos", resolvedCaseId));
  if (
    switchVersionAtRequest !== null
    && (
      switchVersionAtRequest !== caseSwitchVersion
      || resolvedCaseId !== state.activeCaseId
    )
  ) {
    return null;
  }
  const videos = Array.isArray(payload.videos) ? payload.videos : [];
  renderVideoList(videos);
  return videos;
}

function playVideoAt(filename, videoUrl, timestampSeconds, options = {}) {
  if (!videoPlayer || !playerMeta) {
    return;
  }
  const autoPlay = options.autoPlay !== false;
  const targetTime = Math.max(0, Number(timestampSeconds) || 0);
  const activeCaseId = String(state.activeCaseId || "");
  const changedVideo =
    videoPlayer.dataset.filename !== filename
    || videoPlayer.dataset.videoUrl !== videoUrl
    || videoPlayer.dataset.caseId !== activeCaseId;

  const seek = () => {
    const duration = Number.isFinite(videoPlayer.duration) ? videoPlayer.duration : null;
    const safeTime = duration && duration > 0 ? Math.min(targetTime, Math.max(0, duration - 0.05)) : targetTime;
    videoPlayer.currentTime = safeTime;
    if (autoPlay) {
      videoPlayer.play().catch(() => {});
    } else {
      videoPlayer.pause();
    }
  };

  if (changedVideo) {
    videoPlayer.dataset.filename = filename;
    videoPlayer.dataset.videoUrl = videoUrl;
    videoPlayer.dataset.caseId = activeCaseId;
    videoPlayer.src = videoUrl;
    videoPlayer.load();
    videoPlayer.addEventListener("loadedmetadata", seek, { once: true });
  } else if (videoPlayer.readyState >= 1) {
    seek();
  } else {
    videoPlayer.addEventListener("loadedmetadata", seek, { once: true });
  }

  playerMeta.textContent = `${filename} @ ${formatTime(targetTime)}`;
  if (activeCaseId) {
    setPlaybackCache(activeCaseId, filename, targetTime);
  }
  setPlaybackUrl(filename, targetTime);
}

function renderResults(results) {
  if (!resultsGrid) {
    return;
  }
  resultsGrid.innerHTML = "";
  if (!results.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No search results.";
    resultsGrid.appendChild(empty);
    return;
  }

  results.forEach((result) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "result-card";
    card.addEventListener("click", () => {
      playVideoAt(result.video_filename, result.video_url, result.timestamp_seconds);
    });

    const thumb = document.createElement("img");
    thumb.src = result.thumbnail_url;
    thumb.alt = `${result.video_filename} frame at ${formatTime(result.timestamp_seconds)}`;
    thumb.loading = "lazy";

    const info = document.createElement("div");
    info.className = "result-info";

    const title = document.createElement("div");
    title.className = "result-title";
    title.textContent = result.video_filename;

    const sub = document.createElement("div");
    sub.className = "result-sub";
    sub.textContent = `Time: ${formatTime(result.timestamp_seconds)} | Score: ${result.similarity_score.toFixed(4)}`;

    info.appendChild(title);
    info.appendChild(sub);
    card.appendChild(thumb);
    card.appendChild(info);
    resultsGrid.appendChild(card);
  });
}

async function selectCase(caseId) {
  if (!caseId) {
    return;
  }
  const nextCaseId = String(caseId);
  if (!state.cases.some((item) => item.case_id === nextCaseId)) {
    return;
  }
  if (nextCaseId === state.activeCaseId) {
    return;
  }

  saveActiveCasePlaybackSnapshot();
  state.activeCaseId = nextCaseId;
  markCaseStateChanged();
  restoreSearchForCase(nextCaseId);
  resetPlayerForCase(nextCaseId);
  setCaseUrl(nextCaseId);
  renderCaseList();
  syncWorkspaceVisibility();
  const switchVersion = ++caseSwitchVersion;

  try {
    setStatus(`Loading videos for ${nextCaseId}...`, "working");
    const videos = await refreshVideos(nextCaseId, switchVersion);
    if (switchVersion !== caseSwitchVersion || state.activeCaseId !== nextCaseId) {
      return;
    }
    restorePlaybackForCase(nextCaseId, videos);
    setStatus(`Case ${nextCaseId} ready.`, "ok");
  } catch (error) {
    if (switchVersion !== caseSwitchVersion || state.activeCaseId !== nextCaseId) {
      return;
    }
    setStatus(`Case switch failed: ${formatError(error)}`, "error");
  }
}

async function deleteVideo(filename) {
  const caseId = ensureActiveCaseId();
  const safeFilename = String(filename || "").trim();
  if (!safeFilename) {
    return;
  }

  const confirmed = window.confirm(
    `Delete "${safeFilename}" from ${caseId}? This removes the video, embeddings, and thumbnails for that video.`,
  );
  if (!confirmed) {
    return;
  }

  try {
    setStatus(`Deleting ${safeFilename} from ${caseId}...`, "working");
    const url = `${withCaseQuery("/videos", caseId)}&filename=${encodeURIComponent(safeFilename)}`;
    await fetchJson(url, { method: "DELETE" });

    const playback = playbackCache.get(caseId);
    if (playback && playback.filename === safeFilename) {
      clearPlaybackCache(caseId);
    }
    if (
      videoPlayer
      && videoPlayer.dataset.caseId === caseId
      && videoPlayer.dataset.filename === safeFilename
    ) {
      resetPlayerForCase(caseId);
      setCaseUrl(caseId);
    }

    removeVideoFromSearchCache(caseId, safeFilename);
    restoreSearchForCase(caseId);
    await refreshVideos(caseId);
    setStatus(`Deleted ${safeFilename} from ${caseId}.`, "ok");
  } catch (error) {
    setStatus(`Delete video failed: ${formatError(error)}`, "error");
  }
}

async function renameCase(caseId) {
  const targetCaseId = String(caseId || "").trim();
  if (!targetCaseId) {
    return;
  }

  const caseEntry = state.cases.find((item) => item.case_id === targetCaseId);
  const currentName = String(caseEntry?.name || targetCaseId);
  const prompted = window.prompt("Enter a new case name:", currentName);
  if (prompted === null) {
    return;
  }

  const newName = prompted.trim();
  if (!newName) {
    setStatus("Case name cannot be empty.", "error");
    return;
  }

  if (newName === currentName) {
    return;
  }

  try {
    setStatus(`Renaming case ${targetCaseId}...`, "working");
    const payload = await fetchJson(`/cases/${encodeURIComponent(targetCaseId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName }),
    });

    const payloadCases = normalizeCases(Array.isArray(payload?.cases) ? payload.cases : []);
    if (payloadCases.length > 0) {
      state.cases = payloadCases;
    } else {
      state.cases = state.cases.map((item) => (
        item.case_id === targetCaseId
          ? { ...item, name: newName }
          : item
      ));
    }

    if (state.activeCaseId && !state.cases.some((item) => item.case_id === state.activeCaseId)) {
      state.activeCaseId = state.cases.length ? state.cases[0].case_id : null;
    }

    markCaseStateChanged();
    renderCaseList();
    const finalName = String(payload?.name || newName);
    setStatus(`Renamed ${targetCaseId} to "${finalName}".`, "ok");
  } catch (error) {
    setStatus(`Rename case failed: ${formatError(error)}`, "error");
  }
}

async function deleteCase(caseId) {
  const targetCaseId = String(caseId || "").trim();
  if (!targetCaseId) {
    return;
  }

  const caseEntry = state.cases.find((item) => item.case_id === targetCaseId);
  const caseName = caseEntry?.name || targetCaseId;
  const confirmed = window.confirm(
    `Delete case "${caseName}" (${targetCaseId})? This permanently removes all videos, thumbnails, and embeddings in this case.`,
  );
  if (!confirmed) {
    return;
  }

  try {
    setStatus(`Deleting case ${targetCaseId}...`, "working");
    saveActiveCasePlaybackSnapshot();
    const payload = await fetchJson(`/cases/${encodeURIComponent(targetCaseId)}`, {
      method: "DELETE",
    });

    const payloadCases = normalizeCases(Array.isArray(payload?.cases) ? payload.cases : []);
    if (Array.isArray(payload?.cases)) {
      state.cases = payloadCases;
    } else {
      state.cases = state.cases.filter((item) => item.case_id !== targetCaseId);
    }

    playbackCache.delete(targetCaseId);
    searchCache.delete(targetCaseId);
    markCaseStateChanged();
    renderCaseList();

    if (!state.cases.length) {
      state.activeCaseId = null;
      clearResults();
      renderVideoList([]);
      resetPlayerForCase(null);
      setCaseUrl(null);
      syncWorkspaceVisibility();
      setStatus(`Deleted case ${targetCaseId}. No cases remaining.`, "ok");
      return;
    }

    const fallbackCaseId = state.cases[state.cases.length - 1].case_id;
    state.activeCaseId = null;
    await selectCase(fallbackCaseId);
    setStatus(`Deleted case ${targetCaseId}. Switched to ${fallbackCaseId}.`, "ok");
  } catch (error) {
    setStatus(`Delete case failed: ${formatError(error)}`, "error");
  }
}

async function uploadAndIndex() {
  const files = Array.from(videoInput.files || []);
  if (!files.length) {
    setStatus("Select one or more video files first.", "error");
    return;
  }

  const frameInterval = Number.parseFloat(intervalInput.value);
  if (!Number.isFinite(frameInterval) || frameInterval <= 0) {
    setStatus("Frame interval must be greater than 0.", "error");
    return;
  }

  try {
    const caseId = ensureActiveCaseId();
    setStatus(`Uploading videos to ${caseId}...`, "working");
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));

    const uploadResult = await fetchJson(withCaseQuery("/upload", caseId), {
      method: "POST",
      body: formData,
    });

    const uploaded = uploadResult.uploaded || [];
    const errors = uploadResult.errors || [];
    const transcoded = uploadResult.transcoded || [];
    const indexErrors = [];
    let indexedCount = 0;
    let skippedCount = 0;

    for (let i = 0; i < uploaded.length; i += 1) {
      const filename = uploaded[i];
      setStatus(`Indexing ${filename} (${i + 1}/${uploaded.length}) in ${caseId}...`, "working");
      try {
        const processResult = await fetchJson("/process_video", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            case_id: caseId,
            filename,
            frame_interval_seconds: frameInterval,
            batch_size: 32,
            force: false,
          }),
        });

        if (processResult.status === "skipped") {
          skippedCount += 1;
        } else {
          indexedCount += 1;
        }
      } catch (error) {
        indexErrors.push(`${filename}: ${formatError(error)}`);
      }
    }

    const allErrors = [...errors, ...indexErrors];
    const successNote = `Case ${caseId}: uploaded ${uploaded.length}, indexed ${indexedCount}, skipped ${skippedCount}, transcoded ${transcoded.length}.`;
    const errorNote = allErrors.length ? ` Errors: ${allErrors.join(" | ")}` : "";
    setStatus(`${successNote}${errorNote}`, allErrors.length ? "error" : "ok");
    videoInput.value = "";
    await refreshVideos(caseId);
  } catch (error) {
    setStatus(`Upload/index failed: ${formatError(error)}`, "error");
  }
}

async function runSearch() {
  const query = queryInput.value.trim();
  if (!query) {
    setStatus("Type a search query.", "error");
    return;
  }

  const topK = normalizeTopK(topKInput?.value || "10", 10);
  topKInput.value = String(topK);

  try {
    const caseId = ensureActiveCaseId();
    setStatus(`Searching in ${caseId}...`, "working");
    const payload = await fetchJson("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ case_id: caseId, query, top_k: topK }),
    });
    const results = Array.isArray(payload.results) ? payload.results : [];
    renderResults(results);
    cacheSearchResults(caseId, query, topK, results, payload.count);
    setStatus(`Case ${caseId}: found ${payload.count || results.length} result(s).`, "ok");
  } catch (error) {
    setStatus(`Search failed: ${formatError(error)}`, "error");
  }
}

async function createCase() {
  const suggestedName = defaultCaseName();
  const name = window.prompt("Enter a case name:", suggestedName);
  if (name === null) {
    return;
  }
  const trimmed = name.trim();
  const caseNameToCreate = trimmed || suggestedName;

  try {
    console.log("Creating case...");
    setStatus("Creating case...", "working");
    const payload = await fetchJson("/cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: caseNameToCreate }),
    });
    console.log("Create case response:", payload);

    const newCaseId =
      payload.case_id ||
      payload.id ||
      (payload.case && payload.case.case_id);

    if (!newCaseId) {
      throw new Error("Invalid /cases response: missing case_id");
    }

    const caseName =
      typeof payload.name === "string" && payload.name.trim()
        ? payload.name.trim()
        : caseNameToCreate;
    const createdAt = typeof payload.created_at === "string" ? payload.created_at.trim() : "";
    upsertCase(newCaseId, caseName, createdAt);
    saveActiveCasePlaybackSnapshot();
    state.activeCaseId = newCaseId;
    markCaseStateChanged();
    restoreSearchForCase(newCaseId);
    resetPlayerForCase(newCaseId);
    setCaseUrl(newCaseId);
    renderCaseList();
    syncWorkspaceVisibility();
    await refreshVideos(newCaseId);
    setStatus(`Created case ${newCaseId}.`, "ok");
  } catch (error) {
    setStatus(`Create case failed: ${formatError(error)}`, "error");
  }
}

async function restorePlaybackFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const caseIdFromUrl = params.get("case");
  if (caseIdFromUrl && state.cases.some((item) => item.case_id === caseIdFromUrl)) {
    await selectCase(caseIdFromUrl);
  }

  const filename = params.get("video");
  const t = Number.parseFloat(params.get("t") || "0");
  if (!filename || !state.activeCaseId) {
    return;
  }

  const videoUrl = `/media/cases/${encodeURIComponent(state.activeCaseId)}/videos/${encodeURIComponent(filename)}`;
  playVideoAt(filename, videoUrl, Number.isFinite(t) ? t : 0);
}

function setupListeners() {
  if (listenersBound) {
    return;
  }

  setupSidebarResize();

  const createCaseButton = document.getElementById("createCaseBtn");
  console.log("createCaseButton:", createCaseButton);

  createCaseButton?.addEventListener("click", () => {
    console.log("New Case clicked");
    createCase();
  });

  uploadBtn?.addEventListener("click", uploadAndIndex);

  refreshBtn?.addEventListener("click", async () => {
    try {
      await refreshVideos(ensureActiveCaseId());
      setStatus("Video list refreshed.", "ok");
    } catch (error) {
      setStatus(`Refresh failed: ${formatError(error)}`, "error");
    }
  });

  searchBtn?.addEventListener("click", runSearch);

  queryInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      runSearch();
    }
  });

  listenersBound = true;
}

async function init() {
  if (initStarted) {
    return;
  }
  initStarted = true;
  bindDomElements();
  syncWorkspaceVisibility();
  setupListeners();

  clearResults();
  try {
    setStatus("Loading cases...", "working");
    await loadCasesWithRetry(3);
    renderCaseList();

    if (!state.cases.length) {
      state.activeCaseId = null;
      resetPlayerForCase(null);
      setCaseUrl(null);
      syncWorkspaceVisibility();
      setStatus("No cases yet. Click + New Case to begin.", "ok");
      return;
    }

    await selectCase(state.activeCaseId);
    await restorePlaybackFromUrl();
    setStatus("Ready.", "ok");
  } catch (error) {
    setStatus(`Startup failed: ${formatError(error)}. Check backend at http://127.0.0.1:8000/.`, "error");
  }
}

window.addEventListener("load", () => {
  void init();
});

if (document.readyState === "complete") {
  void init();
}
