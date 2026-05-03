let videoInput = null;
let intervalInput = null;
let uploadBtn = null;
let refreshBtn = null;
let uploadStatus = null;
let taskProgress = null;
let taskProgressLabel = null;
let taskProgressPercent = null;
let taskProgressBar = null;
let taskProgressMeta = null;
let videoList = null;
let embeddingProfileSelect = null;
let embeddingDeviceSelect = null;
let saveEmbeddingSettingsBtn = null;
let embeddingSettingsMeta = null;
let analysisStatus = null;
let runFacePeopleSelectedBtn = null;
let runVehiclesSelectedBtn = null;
let mainTabSemanticBtn = null;
let mainTabFacePeopleBtn = null;
let mainTabVehiclesBtn = null;
let tabSemantic = null;
let tabFacePeople = null;
let tabVehicles = null;
let facePeopleVideoSelectList = null;
let vehicleVideoSelectList = null;
let facePeopleQueryInput = null;
let facePeopleSearchBtn = null;
let vehicleQueryInput = null;
let vehicleSearchBtn = null;
let faceWall = null;
let peopleWall = null;
let vehicleWall = null;
let facePeoplePlayer = null;
let facePeoplePlayerMeta = null;
let vehiclePlayer = null;
let vehiclePlayerMeta = null;
let vehicleStatus = null;
let semanticPopup = null;
let semanticPopupVideo = null;
let semanticPopupMeta = null;
let semanticPopupCloseBtn = null;
let semanticPopupBackdrop = null;
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
  caseVideos: new Map(),
  activeMainTab: "semantic",
  embeddingProfiles: [],
  embeddingSettings: null,
};
let caseSwitchVersion = 0;
let caseStateVersion = 0;
let listenersBound = false;
let initStarted = false;
let taskProgressHideTimerId = null;
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
  taskProgress = document.getElementById("taskProgress");
  taskProgressLabel = document.getElementById("taskProgressLabel");
  taskProgressPercent = document.getElementById("taskProgressPercent");
  taskProgressBar = document.getElementById("taskProgressBar");
  taskProgressMeta = document.getElementById("taskProgressMeta");
  videoList = document.getElementById("videoList");
  embeddingProfileSelect = document.getElementById("embeddingProfileSelect");
  embeddingDeviceSelect = document.getElementById("embeddingDeviceSelect");
  saveEmbeddingSettingsBtn = document.getElementById("saveEmbeddingSettingsBtn");
  embeddingSettingsMeta = document.getElementById("embeddingSettingsMeta");
  analysisStatus = document.getElementById("analysisStatus");
  runFacePeopleSelectedBtn = document.getElementById("runFacePeopleSelectedBtn");
  runVehiclesSelectedBtn = document.getElementById("runVehiclesSelectedBtn");
  mainTabSemanticBtn = document.getElementById("mainTabSemanticBtn");
  mainTabFacePeopleBtn = document.getElementById("mainTabFacePeopleBtn");
  mainTabVehiclesBtn = document.getElementById("mainTabVehiclesBtn");
  tabSemantic = document.getElementById("tabSemantic");
  tabFacePeople = document.getElementById("tabFacePeople");
  tabVehicles = document.getElementById("tabVehicles");
  facePeopleVideoSelectList = document.getElementById("facePeopleVideoSelectList");
  vehicleVideoSelectList = document.getElementById("vehicleVideoSelectList");
  facePeopleQueryInput = document.getElementById("facePeopleQueryInput");
  facePeopleSearchBtn = document.getElementById("facePeopleSearchBtn");
  vehicleQueryInput = document.getElementById("vehicleQueryInput");
  vehicleSearchBtn = document.getElementById("vehicleSearchBtn");
  faceWall = document.getElementById("faceWall");
  peopleWall = document.getElementById("peopleWall");
  vehicleWall = document.getElementById("vehicleWall");
  facePeoplePlayer = document.getElementById("facePeoplePlayer");
  facePeoplePlayerMeta = document.getElementById("facePeoplePlayerMeta");
  vehiclePlayer = document.getElementById("vehiclePlayer");
  vehiclePlayerMeta = document.getElementById("vehiclePlayerMeta");
  vehicleStatus = document.getElementById("vehicleStatus");
  semanticPopup = document.getElementById("semanticPopup");
  semanticPopupVideo = document.getElementById("semanticPopupVideo");
  semanticPopupMeta = document.getElementById("semanticPopupMeta");
  semanticPopupCloseBtn = document.getElementById("semanticPopupCloseBtn");
  semanticPopupBackdrop = document.getElementById("semanticPopupBackdrop");
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

function setEmbeddingStatus(message, kind = "") {
  if (!embeddingSettingsMeta) {
    return;
  }
  embeddingSettingsMeta.textContent = message;
  embeddingSettingsMeta.className = `status ${kind}`.trim();
}

function setAnalysisStatus(message, kind = "") {
  if (!analysisStatus) {
    return;
  }
  analysisStatus.textContent = message;
  analysisStatus.className = `status ${kind}`.trim();
}

function setVehicleStatus(message, kind = "") {
  if (!vehicleStatus) {
    return;
  }
  vehicleStatus.textContent = message;
  vehicleStatus.className = `status ${kind}`.trim();
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

function clampPercent(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 0;
  }
  return Math.max(0, Math.min(100, numeric));
}

function estimateEtaSeconds(startedAtMs, completed, total) {
  const completedCount = Number(completed);
  const totalCount = Number(total);
  if (!Number.isFinite(completedCount) || !Number.isFinite(totalCount) || completedCount <= 0) {
    return null;
  }
  const remaining = totalCount - completedCount;
  if (remaining <= 0) {
    return 0;
  }
  const elapsedSec = Math.max(0, (Date.now() - Number(startedAtMs || 0)) / 1000);
  if (!Number.isFinite(elapsedSec) || elapsedSec <= 0) {
    return null;
  }
  return (elapsedSec / completedCount) * remaining;
}

function formatEtaLabel(etaSeconds) {
  if (etaSeconds === null || etaSeconds === undefined) {
    return "ETA: calculating...";
  }
  const numeric = Number(etaSeconds);
  if (!Number.isFinite(numeric)) {
    return "ETA: calculating...";
  }
  if (numeric <= 0) {
    return "ETA: < 1s";
  }
  return `ETA: ${formatTime(Math.ceil(numeric))}`;
}

function setTaskProgressUi(label, percent, meta) {
  if (!taskProgress || !taskProgressLabel || !taskProgressPercent || !taskProgressBar || !taskProgressMeta) {
    return;
  }
  if (taskProgressHideTimerId !== null) {
    window.clearTimeout(taskProgressHideTimerId);
    taskProgressHideTimerId = null;
  }
  const safePercent = clampPercent(percent);
  taskProgress.hidden = false;
  taskProgressLabel.textContent = String(label || "Working...");
  taskProgressPercent.textContent = `${Math.round(safePercent)}%`;
  taskProgressBar.style.width = `${safePercent.toFixed(1)}%`;
  taskProgressMeta.textContent = String(meta || "");
}

function completeTaskProgressUi(label, meta) {
  setTaskProgressUi(label, 100, meta);
  if (!taskProgress) {
    return;
  }
  taskProgressHideTimerId = window.setTimeout(() => {
    if (!taskProgress) {
      return;
    }
    taskProgress.hidden = true;
  }, 1600);
}

function hideTaskProgressUi() {
  if (!taskProgress) {
    return;
  }
  if (taskProgressHideTimerId !== null) {
    window.clearTimeout(taskProgressHideTimerId);
    taskProgressHideTimerId = null;
  }
  taskProgress.hidden = true;
}

function normalizedVideoAnalysis(video) {
  const payload = video && typeof video.analysis === "object" ? video.analysis : {};
  const facePeople =
    payload.face_people && typeof payload.face_people === "object" ? payload.face_people : {};
  const vehicles =
    payload.vehicles && typeof payload.vehicles === "object" ? payload.vehicles : {};
  return {
    face_people: {
      processed: Boolean(facePeople.processed),
      face_count: Number(facePeople.face_count || 0),
      people_count: Number(facePeople.people_count || 0),
      hit_frames: Number(facePeople.hit_frames || 0),
      first_hit_seconds:
        facePeople.first_hit_seconds === null || facePeople.first_hit_seconds === undefined
          ? null
          : Number(facePeople.first_hit_seconds),
    },
    vehicles: {
      processed: Boolean(vehicles.processed),
      vehicle_count: Number(vehicles.vehicle_count || 0),
      hit_frames: Number(vehicles.hit_frames || 0),
      first_hit_seconds:
        vehicles.first_hit_seconds === null || vehicles.first_hit_seconds === undefined
          ? null
          : Number(vehicles.first_hit_seconds),
    },
  };
}

function formatFirstHit(firstHitSeconds) {
  if (firstHitSeconds === null || firstHitSeconds === undefined) {
    return "n/a";
  }
  const numeric = Number(firstHitSeconds);
  if (!Number.isFinite(numeric) || numeric < 0) {
    return "n/a";
  }
  return formatTime(numeric);
}

function formatVideoAnalysis(analysis) {
  const normalized = normalizedVideoAnalysis({ analysis });
  const facePeople = normalized.face_people;
  const vehicles = normalized.vehicles;
  const faceProcessed = facePeople.processed;
  const vehicleProcessed = vehicles.processed;

  const parts = [];
  parts.push(
    faceProcessed
      ? `Face&People: ${facePeople.face_count + facePeople.people_count}`
      : "Face&People: not run",
  );
  parts.push(
    vehicleProcessed
      ? `Vehicles: ${vehicles.vehicle_count}`
      : "Vehicles: not run",
  );
  return parts.join(" | ");
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

function renderMainTabs() {
  const semanticActive = state.activeMainTab === "semantic";
  const faceActive = state.activeMainTab === "face_people";
  const vehicleActive = state.activeMainTab === "vehicles";

  mainTabSemanticBtn?.classList.toggle("active", semanticActive);
  mainTabFacePeopleBtn?.classList.toggle("active", faceActive);
  mainTabVehiclesBtn?.classList.toggle("active", vehicleActive);

  tabSemantic?.classList.toggle("active", semanticActive);
  tabFacePeople?.classList.toggle("active", faceActive);
  tabVehicles?.classList.toggle("active", vehicleActive);
}

function setActiveMainTab(tabKey) {
  const normalized =
    tabKey === "face_people" || tabKey === "vehicles" ? tabKey : "semantic";
  state.activeMainTab = normalized;
  renderMainTabs();
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

async function postFormDataWithProgress(url, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url, true);
    xhr.responseType = "text";
    xhr.timeout = 0;

    xhr.upload.onprogress = (event) => {
      if (typeof onProgress !== "function") {
        return;
      }
      onProgress({
        loaded: Number(event.loaded || 0),
        total: Number(event.total || 0),
        lengthComputable: Boolean(event.lengthComputable),
      });
    };

    xhr.onerror = () => {
      reject(new Error("Network error while uploading files"));
    };

    xhr.ontimeout = () => {
      reject(new Error("Upload timed out"));
    };

    xhr.onload = () => {
      const status = Number(xhr.status || 0);
      const rawBody = String(xhr.responseText || "");

      let payload = null;
      if (rawBody) {
        try {
          payload = JSON.parse(rawBody);
        } catch {
          payload = null;
        }
      }

      if (status < 200 || status >= 300) {
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
          detail = xhr.statusText || "Request failed";
        }
        reject(new Error(`[${status || 0}] ${detail}`));
        return;
      }

      if (!rawBody) {
        resolve({});
        return;
      }

      if (payload === null) {
        reject(new Error(`[${status}] Invalid JSON response`));
        return;
      }

      resolve(payload);
    };

    try {
      xhr.send(formData);
    } catch (error) {
      reject(new Error(`Upload failed: ${formatError(error)}`));
    }
  });
}

function normalizeEmbeddingProfiles(rawProfiles) {
  const list = Array.isArray(rawProfiles) ? rawProfiles : [];
  const normalized = [];
  for (const item of list) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const id = String(item.id || "").trim();
    const label = String(item.label || "").trim();
    const modelName = String(item.model_name || "").trim();
    const pretrained = String(item.pretrained || "").trim();
    if (!id || !modelName || !pretrained) {
      continue;
    }
    normalized.push({
      id,
      label: label || `${modelName} / ${pretrained}`,
      model_name: modelName,
      pretrained,
    });
  }
  return normalized;
}

function findEmbeddingProfileId(modelName, pretrained) {
  const targetModel = String(modelName || "").trim();
  const targetPretrained = String(pretrained || "").trim();
  if (!targetModel || !targetPretrained) {
    return null;
  }
  const profile = state.embeddingProfiles.find(
    (item) => item.model_name === targetModel && item.pretrained === targetPretrained,
  );
  return profile ? profile.id : null;
}

function getEmbeddingProfileById(profileId) {
  const normalizedId = String(profileId || "").trim();
  if (!normalizedId) {
    return null;
  }
  const profile = state.embeddingProfiles.find((item) => item.id === normalizedId);
  return profile || null;
}

function renderEmbeddingSettings(payload) {
  if (!embeddingProfileSelect || !embeddingDeviceSelect) {
    return;
  }

  const settingsPayload = payload && typeof payload === "object" ? payload : {};
  const profiles = normalizeEmbeddingProfiles(settingsPayload.profiles);
  state.embeddingProfiles = profiles;
  state.embeddingSettings = settingsPayload;

  embeddingProfileSelect.innerHTML = "";
  if (!profiles.length) {
    const fallback = document.createElement("option");
    fallback.value = "";
    fallback.textContent = "No model profiles available";
    embeddingProfileSelect.appendChild(fallback);
    embeddingProfileSelect.disabled = true;
  } else {
    embeddingProfileSelect.disabled = false;
    profiles.forEach((profile) => {
      const option = document.createElement("option");
      option.value = profile.id;
      option.textContent = profile.label;
      embeddingProfileSelect.appendChild(option);
    });
  }

  const effective = settingsPayload.effective_next_startup || {};
  const loaded = settingsPayload.loaded || {};
  const loadedModel = String(loaded.model_name || "").trim();
  const loadedPretrained = String(loaded.pretrained || "").trim();
  const loadedDevice = String(loaded.device || "").trim();
  const effectiveDevice = String(effective.device_preference || "auto").trim().toLowerCase();

  const selectedProfileId =
    settingsPayload.effective_profile_id
    || findEmbeddingProfileId(effective.model_name, effective.pretrained)
    || settingsPayload.loaded_profile_id
    || findEmbeddingProfileId(loadedModel, loadedPretrained)
    || (profiles.length ? profiles[0].id : "");
  embeddingProfileSelect.value = String(selectedProfileId || "");

  embeddingDeviceSelect.value = effectiveDevice || "auto";

  const envOverrides = settingsPayload.env_overrides || {};
  const hasEnvOverride = Object.values(envOverrides).some((value) => Boolean(value));
  const restartRequired = Boolean(settingsPayload.restart_required);
  const modelSummary = loadedModel && loadedPretrained
    ? `${loadedModel} / ${loadedPretrained}`
    : "n/a";
  const loadedDeviceSummary = loadedDevice || "n/a";
  let statusMessage = `Loaded now: ${modelSummary} on ${loadedDeviceSummary}.`;
  if (restartRequired) {
    statusMessage += " Saved settings differ; restart app to apply.";
  } else {
    statusMessage += " Saved settings already match loaded engine.";
  }
  if (hasEnvOverride) {
    statusMessage += " Env vars are overriding startup settings.";
  }
  setEmbeddingStatus(statusMessage, restartRequired ? "working" : "ok");
}

async function loadEmbeddingSettings() {
  if (!embeddingProfileSelect || !embeddingDeviceSelect) {
    return;
  }
  try {
    const payload = await fetchJson("/settings/embedding");
    renderEmbeddingSettings(payload);
  } catch (error) {
    setEmbeddingStatus(`Embedding settings unavailable: ${formatError(error)}`, "error");
  }
}

async function saveEmbeddingSettings() {
  if (!embeddingProfileSelect || !embeddingDeviceSelect) {
    return;
  }

  const profile = getEmbeddingProfileById(embeddingProfileSelect.value);
  if (!profile) {
    setEmbeddingStatus("Choose a valid model type first.", "error");
    return;
  }
  const devicePreference = String(embeddingDeviceSelect.value || "auto").trim().toLowerCase();
  if (!["auto", "cuda", "cpu"].includes(devicePreference)) {
    setEmbeddingStatus("Choose a valid device option.", "error");
    return;
  }

  try {
    setEmbeddingStatus("Saving embedding settings...", "working");
    const payload = await fetchJson("/settings/embedding", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model_name: profile.model_name,
        pretrained: profile.pretrained,
        device_preference: devicePreference,
      }),
    });
    renderEmbeddingSettings(payload);
    const envOverrides = payload && payload.env_overrides ? payload.env_overrides : {};
    const hasEnvOverride = Object.values(envOverrides).some((value) => Boolean(value));
    const restartRequired = Boolean(payload && payload.restart_required);
    let message = restartRequired
      ? "Embedding settings saved. Restart app to apply."
      : "Embedding settings saved and already active.";
    if (Boolean(payload && payload.reindex_required_if_model_changes)) {
      message += " Re-index semantic embeddings after model changes.";
    }
    if (hasEnvOverride) {
      message += " Active environment variables currently override startup settings.";
    }
    setEmbeddingStatus(message, restartRequired ? "working" : "ok");
  } catch (error) {
    setEmbeddingStatus(`Save failed: ${formatError(error)}`, "error");
  }
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
  renderMainTabs();
  if (activeCaseMeta) {
    if (!state.activeCaseId) {
      activeCaseMeta.textContent = "";
      setAnalysisStatus("", "");
      setVehicleStatus("", "");
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

function formatEmbeddingEngineLabel(enginePayload) {
  if (!enginePayload || typeof enginePayload !== "object") {
    return "";
  }
  const modelName = String(enginePayload.model_name || "").trim();
  const pretrained = String(enginePayload.pretrained || "").trim();
  const device = String(enginePayload.device || enginePayload.device_preference || "").trim();
  if (!modelName && !pretrained && !device) {
    return "";
  }
  const modelPart = [modelName, pretrained].filter(Boolean).join("/");
  const devicePart = device ? ` on ${device.toUpperCase()}` : "";
  return `${modelPart || "embedding"}${devicePart}`;
}

function getLoadedEmbeddingEngineLabel() {
  const payload = state.embeddingSettings && state.embeddingSettings.loaded
    ? state.embeddingSettings.loaded
    : null;
  const label = formatEmbeddingEngineLabel(payload);
  return label || "embedding engine";
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

function resetAuxPlayers(caseId = null) {
  const normalizedCaseId = caseId ? String(caseId) : "";
  closeSemanticPopup();
  if (facePeoplePlayer && facePeoplePlayerMeta) {
    facePeoplePlayer.pause();
    facePeoplePlayer.removeAttribute("src");
    facePeoplePlayer.load();
    facePeoplePlayer.dataset.filename = "";
    facePeoplePlayer.dataset.videoUrl = "";
    facePeoplePlayer.dataset.caseId = normalizedCaseId;
    facePeoplePlayerMeta.textContent = normalizedCaseId
      ? `Case ${normalizedCaseId}: select a face or person result.`
      : "Select a face or person result.";
  }
  if (vehiclePlayer && vehiclePlayerMeta) {
    vehiclePlayer.pause();
    vehiclePlayer.removeAttribute("src");
    vehiclePlayer.load();
    vehiclePlayer.dataset.filename = "";
    vehiclePlayer.dataset.videoUrl = "";
    vehiclePlayer.dataset.caseId = normalizedCaseId;
    vehiclePlayerMeta.textContent = normalizedCaseId
      ? `Case ${normalizedCaseId}: select a vehicle result.`
      : "Select a vehicle result.";
  }
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
  for (const cachedCaseId of state.caseVideos.keys()) {
    if (!validCaseIds.has(cachedCaseId)) {
      state.caseVideos.delete(cachedCaseId);
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
    const analysisText = formatVideoAnalysis(video.analysis);
    const indexedFrames = Number(video.indexed_frames || 0);
    const indexedWindows = Number(video.indexed_windows || 0);
    detail.textContent = `${formatBytes(video.size_bytes)} | indexed frames: ${indexedFrames} | indexed windows: ${indexedWindows} | ${analysisText}`;

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

function getCaseVideos(caseId = null) {
  const resolvedCaseId = caseId || state.activeCaseId;
  if (!resolvedCaseId) {
    return [];
  }
  const videos = state.caseVideos.get(String(resolvedCaseId));
  return Array.isArray(videos) ? videos : [];
}

function createInsightEmptyElement(message) {
  const empty = document.createElement("div");
  empty.className = "empty";
  empty.textContent = message;
  return empty;
}

function createPopupIconButton(ariaLabel, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "thumb-popup-btn";
  button.title = "Open popup preview";
  button.setAttribute("aria-label", String(ariaLabel || "Open popup preview"));

  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 24 24");
  icon.setAttribute("aria-hidden", "true");
  icon.setAttribute("focusable", "false");

  const pathPrimary = document.createElementNS("http://www.w3.org/2000/svg", "path");
  pathPrimary.setAttribute("d", "M14 4h6v6");
  const pathArrow = document.createElementNS("http://www.w3.org/2000/svg", "path");
  pathArrow.setAttribute("d", "M10 14L20 4");
  const pathFrame = document.createElementNS("http://www.w3.org/2000/svg", "path");
  pathFrame.setAttribute("d", "M20 14v6H4V4h6");

  icon.appendChild(pathPrimary);
  icon.appendChild(pathArrow);
  icon.appendChild(pathFrame);
  button.appendChild(icon);

  button.addEventListener("click", (event) => {
    event.stopPropagation();
    onClick();
  });
  return button;
}

function playInPlayer(
  player,
  meta,
  filename,
  videoUrl,
  timestampSeconds,
  options = {},
) {
  if (!player || !meta) {
    return;
  }
  const autoPlay = options.autoPlay === true;
  const forceRenderPausedFrame = options.forceRenderPausedFrame === true;
  const posterUrl = typeof options.posterUrl === "string" ? options.posterUrl.trim() : "";
  const targetTime = Math.max(0, Number(timestampSeconds) || 0);
  const activeCaseId = String(state.activeCaseId || "");
  const hasSource = Boolean(String(player.getAttribute("src") || "").trim());
  const changedVideo =
    player.dataset.filename !== filename
    || player.dataset.videoUrl !== videoUrl
    || player.dataset.caseId !== activeCaseId
    || !hasSource;
  const currentRequestId = String((Number(player.dataset.seekRequestId || "0") || 0) + 1);
  player.dataset.seekRequestId = currentRequestId;
  player.preload = "auto";

  const seek = () => {
    const duration = Number.isFinite(player.duration) ? player.duration : null;
    const safeTime = duration && duration > 0
      ? Math.min(targetTime, Math.max(0, duration - 0.05))
      : targetTime;

    let settled = false;
    let fallbackTimerId = null;
    let hasDecodedFrame = player.readyState >= 2;
    let seekCompleted = Math.abs((Number(player.currentTime) || 0) - safeTime) < 0.01;
    const isStale = () => player.dataset.seekRequestId !== currentRequestId;
    const cleanup = () => {
      player.removeEventListener("loadeddata", onLoadedData);
      player.removeEventListener("canplay", onCanPlay);
      player.removeEventListener("seeked", onSeeked);
      if (fallbackTimerId !== null) {
        window.clearTimeout(fallbackTimerId);
        fallbackTimerId = null;
      }
    };
    const finalize = () => {
      if (settled || isStale()) {
        return;
      }
      settled = true;
      cleanup();
      if (autoPlay) {
        player.play().catch(() => {});
      } else if (forceRenderPausedFrame) {
        const previousMuted = player.muted;
        player.muted = true;
        const renderPlayback = player.play();
        if (renderPlayback && typeof renderPlayback.then === "function") {
          renderPlayback
            .then(() => {
              window.setTimeout(() => {
                if (isStale()) {
                  player.muted = previousMuted;
                  return;
                }
                player.pause();
                trySeek(safeTime);
                player.muted = previousMuted;
              }, 60);
            })
            .catch(() => {
              if (!isStale()) {
                player.pause();
              }
              player.muted = previousMuted;
            });
        } else {
          player.pause();
          player.muted = previousMuted;
        }
      } else {
        player.pause();
      }
    };
    const tryFinalize = () => {
      if (seekCompleted && hasDecodedFrame) {
        finalize();
      }
    };

    const trySeek = (value) => {
      try {
        player.currentTime = value;
      } catch {
        // Ignore transient seek errors while media is still warming up.
      }
    };

    function onLoadedData() {
      if (isStale()) {
        return;
      }
      hasDecodedFrame = true;
      tryFinalize();
    }

    function onCanPlay() {
      if (isStale()) {
        return;
      }
      hasDecodedFrame = true;
      tryFinalize();
    }

    function onSeeked() {
      if (isStale()) {
        return;
      }
      seekCompleted = true;
      tryFinalize();
    }

    player.addEventListener("loadeddata", onLoadedData);
    player.addEventListener("canplay", onCanPlay);
    player.addEventListener("seeked", onSeeked);

    trySeek(safeTime);
    fallbackTimerId = window.setTimeout(() => {
      if (settled || isStale()) {
        return;
      }
      hasDecodedFrame = hasDecodedFrame || player.readyState >= 2;
      seekCompleted = seekCompleted || Math.abs((Number(player.currentTime) || 0) - safeTime) < 0.2;
      if (!seekCompleted) {
        // Some codec/container combos need a tiny nudged re-seek to render the paused frame.
        const nudgedTime = safeTime > 0.02 ? safeTime - 0.001 : safeTime + 0.001;
        trySeek(Math.max(0, nudgedTime));
      }
      tryFinalize();
      if (!settled) {
        finalize();
      }
    }, 1000);
    tryFinalize();
  };

  if (changedVideo) {
    player.dataset.filename = filename;
    player.dataset.videoUrl = videoUrl;
    player.dataset.caseId = activeCaseId;
    if (posterUrl) {
      player.setAttribute("poster", posterUrl);
    } else {
      player.removeAttribute("poster");
    }
    player.src = videoUrl;
    player.load();
    player.addEventListener("loadedmetadata", seek, { once: true });
  } else if (player.readyState >= 1) {
    if (posterUrl) {
      player.setAttribute("poster", posterUrl);
    }
    seek();
  } else {
    if (posterUrl) {
      player.setAttribute("poster", posterUrl);
    }
    player.addEventListener("loadedmetadata", seek, { once: true });
  }

  meta.textContent = `${filename} @ ${formatTime(targetTime)}`;
}

function closeSemanticPopup() {
  if (!semanticPopup || !semanticPopupVideo) {
    return;
  }
  semanticPopup.classList.remove("open");
  semanticPopup.setAttribute("hidden", "");
  semanticPopupVideo.dataset.seekRequestId = String(
    (Number(semanticPopupVideo.dataset.seekRequestId || "0") || 0) + 1,
  );
  semanticPopupVideo.dataset.filename = "";
  semanticPopupVideo.dataset.videoUrl = "";
  semanticPopupVideo.dataset.caseId = "";
  semanticPopupVideo.pause();
  semanticPopupVideo.removeAttribute("src");
  semanticPopupVideo.removeAttribute("poster");
  semanticPopupVideo.load();
  if (semanticPopupMeta) {
    semanticPopupMeta.textContent = "Jump to a semantic result to preview here.";
  }
}

function openSemanticPopupAt(filename, videoUrl, timestampSeconds, options = {}) {
  if (!semanticPopup || !semanticPopupVideo) {
    return;
  }
  semanticPopup.removeAttribute("hidden");
  semanticPopup.classList.add("open");
  if (semanticPopupMeta) {
    semanticPopupMeta.textContent = "Loading preview...";
  }
  playInPlayer(
    semanticPopupVideo,
    semanticPopupMeta,
    filename,
    videoUrl,
    timestampSeconds,
    {
      autoPlay: options.autoPlay === true,
      forceRenderPausedFrame: true,
      posterUrl: typeof options.posterUrl === "string" ? options.posterUrl : "",
    },
  );
}

function buildFirstDetectionButton(video, firstHitSeconds, player, meta) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ghost";
  button.textContent = "Play First Detection";
  const numeric = Number(firstHitSeconds);
  if (!Number.isFinite(numeric) || numeric < 0) {
    button.disabled = true;
    button.title = "No detected timestamp";
    return button;
  }
  button.addEventListener("click", () => {
    const fallbackVideoUrl = state.activeCaseId
      ? `/media/cases/${encodeURIComponent(state.activeCaseId)}/videos/${encodeURIComponent(video.filename)}`
      : "";
    playInPlayer(
      player,
      meta,
      video.filename,
      video.video_url || fallbackVideoUrl,
      numeric,
      { autoPlay: false },
    );
  });
  return button;
}

function buildSelectionLabel(video, category) {
  const label = document.createElement("label");
  label.className = "analysis-video-label";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.className = "analysis-select-checkbox";
  checkbox.dataset.category = category;
  checkbox.dataset.filename = video.filename;
  const text = document.createElement("span");
  text.className = "analysis-video-name";
  text.textContent = video.filename;
  label.appendChild(checkbox);
  label.appendChild(text);
  return label;
}

function renderAnalysisSelectionList(container, category) {
  if (!container) {
    return;
  }
  container.innerHTML = "";

  if (!state.activeCaseId) {
    container.appendChild(
      createInsightEmptyElement("Select a case first."),
    );
    return;
  }

  const videos = getCaseVideos();
  if (!videos.length) {
    container.appendChild(
      createInsightEmptyElement("No videos in this case yet."),
    );
    return;
  }

  const sortedVideos = [...videos].sort((a, b) => String(a.filename).localeCompare(String(b.filename)));
  sortedVideos.forEach((video) => {
    const analysis = normalizedVideoAnalysis(video)[category];
    const row = document.createElement("div");
    row.className = "analysis-video-item";

    const label = buildSelectionLabel(video, category);
    const checkbox = label.querySelector("input.analysis-select-checkbox");
    if (checkbox) {
      checkbox.disabled = analysis.processed;
      checkbox.checked = false;
    }

    const status = document.createElement("div");
    status.className = "analysis-video-status";
    if (category === "face_people") {
      if (analysis.processed) {
        status.textContent = `Done | faces ${analysis.face_count} | people ${analysis.people_count} | first ${formatFirstHit(analysis.first_hit_seconds)}`;
      } else {
        status.textContent = "Not analyzed";
      }
    } else {
      if (analysis.processed) {
        status.textContent = `Done | vehicles ${analysis.vehicle_count} | first ${formatFirstHit(analysis.first_hit_seconds)}`;
      } else {
        status.textContent = "Not analyzed";
      }
    }
    row.appendChild(label);
    row.appendChild(status);
    container.appendChild(row);
  });
}

function renderAnalysisSelectionLists() {
  renderAnalysisSelectionList(facePeopleVideoSelectList, "face_people");
  renderAnalysisSelectionList(vehicleVideoSelectList, "vehicles");
}

function renderWall(
  container,
  items,
  emptyMessage,
  player,
  playerMetaElement,
) {
  if (!container) {
    return;
  }
  container.innerHTML = "";
  if (!items || !items.length) {
    container.appendChild(createInsightEmptyElement(emptyMessage));
    return;
  }

  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "wall-card";

    const thumbWrap = document.createElement("div");
    thumbWrap.className = "wall-thumb-wrap";

    const image = document.createElement("img");
    image.src = item.crop_url;
    image.alt = `${item.kind} crop from ${item.video_filename}`;
    image.loading = "lazy";
    const thumbButton = document.createElement("button");
    thumbButton.type = "button";
    thumbButton.className = "thumb-target-btn wall-thumb-target";
    thumbButton.title = "Load in player at timestamp";
    thumbButton.setAttribute(
      "aria-label",
      `Load ${item.video_filename} at ${formatTime(item.timestamp_seconds)} in player`,
    );
    thumbButton.addEventListener("click", () => {
      playInPlayer(
        player,
        playerMetaElement,
        item.video_filename,
        item.video_url,
        item.timestamp_seconds,
        { autoPlay: false },
      );
    });
    thumbButton.appendChild(image);

    const popupBtn = createPopupIconButton(
      `Open popup preview for ${item.video_filename} at ${formatTime(item.timestamp_seconds)}`,
      () => {
        openSemanticPopupAt(
          item.video_filename,
          item.video_url,
          item.timestamp_seconds,
          { autoPlay: false, posterUrl: item.crop_url },
        );
      },
    );
    thumbWrap.appendChild(thumbButton);
    thumbWrap.appendChild(popupBtn);

    const info = document.createElement("div");
    info.className = "wall-card-info";
    const title = document.createElement("div");
    title.className = "wall-card-title";
    title.textContent = item.video_filename;
    const sub = document.createElement("div");
    sub.className = "wall-card-sub";
    const scoreText = Number.isFinite(Number(item.similarity_score))
      ? ` | score ${Number(item.similarity_score).toFixed(4)}`
      : "";
    sub.textContent = `${formatTime(item.timestamp_seconds)}${scoreText}`;

    info.appendChild(title);
    info.appendChild(sub);
    card.appendChild(thumbWrap);
    card.appendChild(info);
    container.appendChild(card);
  });
}

async function fetchAnalysisGallery(category, query = "") {
  const caseId = ensureActiveCaseId();
  const payload = await fetchJson("/analysis_gallery", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      case_id: caseId,
      category,
      query: String(query || "").trim(),
      top_k: 180,
      limit: 500,
    }),
  });
  return payload && typeof payload === "object" ? payload : {};
}

async function refreshFacePeopleWall() {
  if (!state.activeCaseId) {
    renderWall(faceWall, [], "Select a case first.", facePeoplePlayer, facePeoplePlayerMeta);
    renderWall(peopleWall, [], "Select a case first.", facePeoplePlayer, facePeoplePlayerMeta);
    return;
  }
  try {
    const query = String(facePeopleQueryInput?.value || "").trim();
    const payload = await fetchAnalysisGallery("face_people", query);
    const faces = Array.isArray(payload.faces) ? payload.faces : [];
    const people = Array.isArray(payload.people) ? payload.people : [];
    renderWall(
      faceWall,
      faces,
      query ? "No matching face crops." : "No face detections yet. Run Face & People analysis.",
      facePeoplePlayer,
      facePeoplePlayerMeta,
    );
    renderWall(
      peopleWall,
      people,
      query ? "No matching people crops." : "No people detections yet. Run Face & People analysis.",
      facePeoplePlayer,
      facePeoplePlayerMeta,
    );
  } catch (error) {
    setAnalysisStatus(`Face & People wall failed: ${formatError(error)}`, "error");
  }
}

async function refreshVehicleWall() {
  if (!state.activeCaseId) {
    renderWall(vehicleWall, [], "Select a case first.", vehiclePlayer, vehiclePlayerMeta);
    return;
  }
  try {
    const query = String(vehicleQueryInput?.value || "").trim();
    const payload = await fetchAnalysisGallery("vehicles", query);
    const vehicles = Array.isArray(payload.vehicles) ? payload.vehicles : [];
    renderWall(
      vehicleWall,
      vehicles,
      query ? "No matching vehicle crops." : "No vehicle detections yet. Run Vehicle analysis.",
      vehiclePlayer,
      vehiclePlayerMeta,
    );
  } catch (error) {
    setVehicleStatus(`Vehicle wall failed: ${formatError(error)}`, "error");
  }
}

async function refreshAnalysisWalls() {
  if (!state.activeCaseId) {
    renderWall(faceWall, [], "Select a case first.", facePeoplePlayer, facePeoplePlayerMeta);
    renderWall(peopleWall, [], "Select a case first.", facePeoplePlayer, facePeoplePlayerMeta);
    renderWall(vehicleWall, [], "Select a case first.", vehiclePlayer, vehiclePlayerMeta);
    return;
  }
  await Promise.all([refreshFacePeopleWall(), refreshVehicleWall()]);
}

async function runFacePeopleCropSearch() {
  await refreshFacePeopleWall();
}

async function runVehicleCropSearch() {
  await refreshVehicleWall();
}

function getSelectedInsightFilenames(category) {
  const selector = `input.analysis-select-checkbox[data-category="${category}"]:checked`;
  const roots = category === "vehicles" ? vehicleVideoSelectList : facePeopleVideoSelectList;
  if (!roots) {
    return [];
  }
  return Array.from(roots.querySelectorAll(selector))
    .map((input) => String(input.dataset.filename || "").trim())
    .filter((name) => Boolean(name));
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
  state.caseVideos.set(String(resolvedCaseId), videos);
  renderVideoList(videos);
  if (resolvedCaseId === state.activeCaseId) {
    renderAnalysisSelectionLists();
    await refreshAnalysisWalls();
  }
  return videos;
}

function playVideoAt(filename, videoUrl, timestampSeconds, options = {}) {
  if (!videoPlayer || !playerMeta) {
    return;
  }
  const autoPlay = options.autoPlay !== false;
  const targetTime = Math.max(0, Number(timestampSeconds) || 0);
  const activeCaseId = String(state.activeCaseId || "");
  playInPlayer(
    videoPlayer,
    playerMeta,
    filename,
    videoUrl,
    targetTime,
    { autoPlay },
  );
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
    const card = document.createElement("article");
    card.className = "result-card";

    const preview = document.createElement("div");
    preview.className = "result-preview";

    const thumbWrap = document.createElement("div");
    thumbWrap.className = "result-thumb-wrap";

    const thumb = document.createElement("img");
    thumb.src = result.thumbnail_url;
    thumb.alt = `${result.video_filename} frame at ${formatTime(result.timestamp_seconds)}`;
    thumb.loading = "lazy";
    const thumbButton = document.createElement("button");
    thumbButton.type = "button";
    thumbButton.className = "thumb-target-btn result-thumb-target";
    thumbButton.title = "Load in player at timestamp";
    thumbButton.setAttribute(
      "aria-label",
      `Load ${result.video_filename} at ${formatTime(result.timestamp_seconds)} in player`,
    );
    thumbButton.addEventListener("click", () => {
      playVideoAt(
        result.video_filename,
        result.video_url,
        result.timestamp_seconds,
        { autoPlay: false },
      );
    });
    thumbButton.appendChild(thumb);

    const popupBtn = createPopupIconButton(
      `Open popup preview for ${result.video_filename} at ${formatTime(result.timestamp_seconds)}`,
      () => {
        openSemanticPopupAt(
          result.video_filename,
          result.video_url,
          result.timestamp_seconds,
          { autoPlay: false, posterUrl: result.thumbnail_url },
        );
      },
    );
    thumbWrap.appendChild(thumbButton);
    thumbWrap.appendChild(popupBtn);

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
    preview.appendChild(thumbWrap);
    preview.appendChild(info);
    card.appendChild(preview);
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
  resetAuxPlayers(nextCaseId);
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
    setAnalysisStatus("Face & People tab: select videos to run analysis.", "ok");
    setVehicleStatus("Vehicle tab: select videos to run analysis.", "ok");
    setStatus(`Case ${nextCaseId} ready.`, "ok");
  } catch (error) {
    if (switchVersion !== caseSwitchVersion || state.activeCaseId !== nextCaseId) {
      return;
    }
    setAnalysisStatus(`Case switch failed: ${formatError(error)}`, "error");
    setVehicleStatus(`Case switch failed: ${formatError(error)}`, "error");
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
    state.caseVideos.delete(targetCaseId);
    markCaseStateChanged();
    renderCaseList();

    if (!state.cases.length) {
      state.activeCaseId = null;
      clearResults();
      renderVideoList([]);
      resetPlayerForCase(null);
      resetAuxPlayers(null);
      setCaseUrl(null);
      syncWorkspaceVisibility();
      setAnalysisStatus("", "");
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
    hideTaskProgressUi();
    setStatus("Select one or more video files first.", "error");
    return;
  }

  const frameInterval = Number.parseFloat(intervalInput.value);
  if (!Number.isFinite(frameInterval) || frameInterval <= 0) {
    hideTaskProgressUi();
    setStatus("Frame interval must be greater than 0.", "error");
    return;
  }

  try {
    const caseId = ensureActiveCaseId();
    let engineLabel = getLoadedEmbeddingEngineLabel();
    const totalUploadBytes = files.reduce((sum, file) => sum + Number(file.size || 0), 0);
    const uploadStartedAt = Date.now();
    const uploadWeight = 25;
    const indexWeight = 75;
    setStatus(`Uploading videos to ${caseId} (engine: ${engineLabel})...`, "working");
    setTaskProgressUi(
      "Uploading videos",
      0,
      `${files.length} file(s) | ${formatBytes(totalUploadBytes)}`,
    );
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));

    const uploadResult = await postFormDataWithProgress(
      withCaseQuery("/upload", caseId),
      formData,
      (event) => {
        const elapsedSec = Math.max(0.001, (Date.now() - uploadStartedAt) / 1000);
        const estimatedTotal = event.lengthComputable && event.total > 0
          ? event.total
          : totalUploadBytes;
        const loadedBytes = Math.min(event.loaded, estimatedTotal || event.loaded);
        const fraction = estimatedTotal > 0 ? loadedBytes / estimatedTotal : 0;
        const progressPercent = clampPercent(fraction * uploadWeight);
        const speedBytesPerSecond = loadedBytes / elapsedSec;
        const remainingBytes = Math.max(0, estimatedTotal - loadedBytes);
        const etaSeconds = speedBytesPerSecond > 0 ? remainingBytes / speedBytesPerSecond : null;
        const meta = [
          `${formatBytes(loadedBytes)} / ${formatBytes(estimatedTotal || totalUploadBytes)}`,
          `${formatBytes(speedBytesPerSecond)}/s`,
          formatEtaLabel(etaSeconds),
        ].join(" | ");
        setTaskProgressUi("Uploading videos", progressPercent, meta);
      },
    );

    const uploaded = uploadResult.uploaded || [];
    const errors = uploadResult.errors || [];
    const transcoded = uploadResult.transcoded || [];
    const indexErrors = [];
    let indexedCount = 0;
    let skippedCount = 0;
    let indexedWindows = 0;
    const indexStartedAt = Date.now();

    if (!uploaded.length) {
      setTaskProgressUi(
        "Upload complete",
        100,
        "No new files were uploaded for indexing.",
      );
    }

    for (let i = 0; i < uploaded.length; i += 1) {
      const filename = uploaded[i];
      const progressStart = uploadWeight + ((i / uploaded.length) * indexWeight);
      const etaBefore = estimateEtaSeconds(indexStartedAt, i, uploaded.length);
      setTaskProgressUi(
        "Indexing uploaded videos",
        progressStart,
        `Processing ${filename} (${i + 1}/${uploaded.length}) | ${formatEtaLabel(etaBefore)}`,
      );
      setStatus(
        `Base indexing ${filename} (${i + 1}/${uploaded.length}) in ${caseId} using ${engineLabel}...`,
        "working",
      );
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
            analysis_face_people: false,
            analysis_vehicles: false,
            analysis_only: false,
          }),
        });
        const responseEngineLabel = formatEmbeddingEngineLabel(processResult.embedding_engine);
        if (responseEngineLabel) {
          engineLabel = responseEngineLabel;
        }

        if (processResult.status === "skipped") {
          skippedCount += 1;
        } else {
          indexedCount += 1;
        }
        indexedWindows += Number(processResult.indexed_windows || 0);
      } catch (error) {
        indexErrors.push(`${filename}: ${formatError(error)}`);
      }

      const processedCount = i + 1;
      const etaAfter = estimateEtaSeconds(indexStartedAt, processedCount, uploaded.length);
      const progressAfter = uploadWeight + ((processedCount / uploaded.length) * indexWeight);
      setTaskProgressUi(
        "Indexing uploaded videos",
        progressAfter,
        `Processed ${processedCount}/${uploaded.length} | indexed ${indexedCount}, skipped ${skippedCount} | ${formatEtaLabel(etaAfter)}`,
      );
    }

    const allErrors = [...errors, ...indexErrors];
    const successNote = `Case ${caseId}: uploaded ${uploaded.length}, indexed ${indexedCount}, skipped ${skippedCount}, temporal windows ${indexedWindows}, transcoded ${transcoded.length}, engine ${engineLabel}.`;
    const errorNote = allErrors.length ? ` Errors: ${allErrors.join(" | ")}` : "";
    setStatus(`${successNote}${errorNote}`, allErrors.length ? "error" : "ok");
    videoInput.value = "";
    setTaskProgressUi(
      "Refreshing case view",
      99,
      `Finalizing results for ${caseId}...`,
    );
    await refreshVideos(caseId);
    completeTaskProgressUi(
      allErrors.length ? "Completed with warnings" : "Upload + indexing completed",
      successNote,
    );
  } catch (error) {
    setStatus(`Upload/index failed: ${formatError(error)}`, "error");
    setTaskProgressUi(
      "Upload/index failed",
      100,
      formatError(error),
    );
  }
}

async function runSelectedAnalysisForCategory(category) {
  const normalizedCategory = category === "vehicles" ? "vehicles" : "face_people";
  const setCategoryStatus = (message, kind = "") => {
    if (normalizedCategory === "vehicles") {
      setVehicleStatus(message, kind);
    } else {
      setAnalysisStatus(message, kind);
    }
  };
  const filenames = getSelectedInsightFilenames(normalizedCategory);
  if (!filenames.length) {
    const label = normalizedCategory === "vehicles" ? "Vehicles" : "Face & People";
    setCategoryStatus(`Select one or more videos in the ${label} tab first.`, "error");
    return;
  }

  let caseId;
  try {
    caseId = ensureActiveCaseId();
  } catch (error) {
    setCategoryStatus(formatError(error), "error");
    return;
  }

  const label = normalizedCategory === "vehicles" ? "Vehicles" : "Face & People";
  const confirmed = window.confirm(`Run ${label} analysis for ${filenames.length} selected video(s)?`);
  if (!confirmed) {
    return;
  }

  try {
    const frameInterval = Number.parseFloat(intervalInput?.value || "2");
    const safeFrameInterval = Number.isFinite(frameInterval) && frameInterval > 0 ? frameInterval : 2;
    let processed = 0;
    let skipped = 0;
    const warnings = [];
    const analysisStartedAt = Date.now();

    for (let i = 0; i < filenames.length; i += 1) {
      const filename = filenames[i];
      const etaBefore = estimateEtaSeconds(analysisStartedAt, i, filenames.length);
      const percentBefore = clampPercent((i / filenames.length) * 100);
      setCategoryStatus(
        `Running ${label} analysis for ${filename} (${i + 1}/${filenames.length}) | ${Math.round(percentBefore)}% | ${formatEtaLabel(etaBefore)}...`,
        "working",
      );
      try {
        const payload = await fetchJson("/process_video", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            case_id: caseId,
            filename,
            frame_interval_seconds: safeFrameInterval,
            batch_size: 32,
            force: false,
            analysis_face_people: normalizedCategory === "face_people",
            analysis_vehicles: normalizedCategory === "vehicles",
            analysis_only: true,
          }),
        });
        const analysisPayload =
          payload.analysis && typeof payload.analysis === "object" ? payload.analysis : {};
        const status = String(analysisPayload.status || "");
        if (status === "processed") {
          processed += 1;
        } else if (status === "skipped" || status === "not_requested") {
          skipped += 1;
        } else {
          warnings.push(`${filename}: ${analysisPayload.reason || "analysis unavailable"}`);
        }
      } catch (error) {
        warnings.push(`${filename}: ${formatError(error)}`);
      }

      const completed = i + 1;
      const percentAfter = clampPercent((completed / filenames.length) * 100);
      const etaAfter = estimateEtaSeconds(analysisStartedAt, completed, filenames.length);
      setCategoryStatus(
        `${label}: ${completed}/${filenames.length} completed | ${Math.round(percentAfter)}% | ${formatEtaLabel(etaAfter)}.`,
        "working",
      );
    }

    await refreshVideos(caseId);
    const summary = `${label}: processed ${processed}, skipped ${skipped}, warnings ${warnings.length}.`;
    const warningText = warnings.length ? ` ${warnings.join(" | ")}` : "";
    setCategoryStatus(`${summary}${warningText}`, warnings.length ? "error" : "ok");
  } catch (error) {
    setCategoryStatus(`Run ${label} analysis failed: ${formatError(error)}`, "error");
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
    const intent = String(payload.intent || "").trim();
    const mode = String(payload.search_mode || "").trim();
    const engineLabel = formatEmbeddingEngineLabel(payload.embedding_engine);
    const metaParts = [];
    if (intent) {
      metaParts.push(`intent=${intent}`);
    }
    if (mode) {
      metaParts.push(`mode=${mode}`);
    }
    if (engineLabel) {
      metaParts.push(`engine=${engineLabel}`);
    }
    const metaSuffix = metaParts.length ? ` (${metaParts.join(", ")})` : "";
    setStatus(`Case ${caseId}: found ${payload.count || results.length} result(s).${metaSuffix}`, "ok");
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
    state.caseVideos.set(String(newCaseId), []);
    markCaseStateChanged();
    restoreSearchForCase(newCaseId);
    resetPlayerForCase(newCaseId);
    resetAuxPlayers(newCaseId);
    setCaseUrl(newCaseId);
    renderCaseList();
    syncWorkspaceVisibility();
    await refreshVideos(newCaseId);
    setAnalysisStatus("Face & People tab: select videos to run analysis.", "ok");
    setVehicleStatus("Vehicle tab: select videos to run analysis.", "ok");
    setStatus(`Created case ${newCaseId}.`, "ok");
  } catch (error) {
    setAnalysisStatus(`Create case failed: ${formatError(error)}`, "error");
    setVehicleStatus(`Create case failed: ${formatError(error)}`, "error");
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
  saveEmbeddingSettingsBtn?.addEventListener("click", () => {
    saveEmbeddingSettings();
  });
  runFacePeopleSelectedBtn?.addEventListener("click", () => {
    runSelectedAnalysisForCategory("face_people");
  });
  runVehiclesSelectedBtn?.addEventListener("click", () => {
    runSelectedAnalysisForCategory("vehicles");
  });
  mainTabSemanticBtn?.addEventListener("click", () => {
    setActiveMainTab("semantic");
  });
  mainTabFacePeopleBtn?.addEventListener("click", async () => {
    setActiveMainTab("face_people");
    await refreshFacePeopleWall();
  });
  mainTabVehiclesBtn?.addEventListener("click", async () => {
    setActiveMainTab("vehicles");
    await refreshVehicleWall();
  });

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

  facePeopleSearchBtn?.addEventListener("click", () => {
    runFacePeopleCropSearch();
  });
  vehicleSearchBtn?.addEventListener("click", () => {
    runVehicleCropSearch();
  });
  facePeopleQueryInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      runFacePeopleCropSearch();
    }
  });
  vehicleQueryInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      runVehicleCropSearch();
    }
  });
  semanticPopupCloseBtn?.addEventListener("click", () => {
    closeSemanticPopup();
  });
  semanticPopupBackdrop?.addEventListener("click", () => {
    closeSemanticPopup();
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && semanticPopup && !semanticPopup.hasAttribute("hidden")) {
      closeSemanticPopup();
    }
  });

  renderMainTabs();
  renderAnalysisSelectionLists();
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
  setActiveMainTab("semantic");
  await loadEmbeddingSettings();

  clearResults();
  try {
    setStatus("Loading cases...", "working");
    await loadCasesWithRetry(3);
    renderCaseList();

    if (!state.cases.length) {
      state.activeCaseId = null;
      resetPlayerForCase(null);
      resetAuxPlayers(null);
      setCaseUrl(null);
      syncWorkspaceVisibility();
      setAnalysisStatus("", "");
      setVehicleStatus("", "");
      setStatus("No cases yet. Click + New Case to begin.", "ok");
      return;
    }

    const initialCaseId = state.activeCaseId;
    state.activeCaseId = null;
    await selectCase(initialCaseId);
    await restorePlaybackFromUrl();
    setStatus("Ready.", "ok");
  } catch (error) {
    setAnalysisStatus(`Startup failed: ${formatError(error)}`, "error");
    setVehicleStatus(`Startup failed: ${formatError(error)}`, "error");
    setStatus(`Startup failed: ${formatError(error)}. Check backend at http://127.0.0.1:8000/.`, "error");
  }
}

window.addEventListener("load", () => {
  void init();
});

if (document.readyState === "complete") {
  void init();
}
