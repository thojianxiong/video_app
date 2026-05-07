let videoInput = null;
let intervalInput = null;
let uploadBtn = null;
let refreshBtn = null;
let refreshTriageBtn = null;
let uploadStatus = null;
let preUploadIndexPanel = null;
let preUploadSelectAll = null;
let preUploadIndexList = null;
let existingIndexPanel = null;
let existingIndexSelectAll = null;
let existingIndexList = null;
let runExistingIndexBtn = null;
let taskProgress = null;
let taskProgressLabel = null;
let taskProgressPercent = null;
let taskProgressBar = null;
let taskProgressMeta = null;
let triageStatus = null;
let triageList = null;
let triageDetail = null;
let videoList = null;
let embeddingProfileSelect = null;
let embeddingDeviceSelect = null;
let saveEmbeddingSettingsBtn = null;
let embeddingSettingsMeta = null;
let analysisStatus = null;
let runFacePeopleSelectedBtn = null;
let runVehiclesSelectedBtn = null;
let mainTabTriageBtn = null;
let mainTabSemanticBtn = null;
let mainTabFacePeopleBtn = null;
let mainTabVehiclesBtn = null;
let workspaceBackBtn = null;
let workspaceAnalysisBtn = null;
let workspaceReportBtn = null;
let workspaceSettingsBtn = null;
let workspaceExitBtn = null;
let tabTriage = null;
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
let semanticSearchMeta = null;
let resultsGrid = null;
let triagePlayer = null;
let triagePlayerMeta = null;
let videoPlayer = null;
let playerMeta = null;
let activeCaseMeta = null;
let caseList = null;
let appShell = null;
let workspace = null;
let workspaceSettingsPage = null;
let workspaceReportPage = null;
let caseSidebar = null;
let sidebarResizeHandle = null;

const state = {
  cases: [],
  activeCaseId: null,
  caseVideos: new Map(),
  activeMainTab: "triage",
  workspaceView: "analysis",
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
const triageCache = new Map();
const triageLoading = new Set();
const triageErrors = new Map();
const triageSelection = new Map();
let pendingUploadItems = [];
let triageRefreshToken = 0;
let indexStatusPollToken = 0;
let indexStatusPollCaseId = "";
let uploadFlowActive = false;
const backgroundIndexTerminalSeen = new Map();
const SIDEBAR_MIN_WIDTH = 220;
const SIDEBAR_MAX_WIDTH = 560;

function bindDomElements() {
  videoInput = document.getElementById("videoInput");
  intervalInput = document.getElementById("intervalInput");
  uploadBtn = document.getElementById("uploadBtn");
  refreshBtn = document.getElementById("refreshBtn");
  refreshTriageBtn = document.getElementById("refreshTriageBtn");
  uploadStatus = document.getElementById("uploadStatus");
  preUploadIndexPanel = document.getElementById("preUploadIndexPanel");
  preUploadSelectAll = document.getElementById("preUploadSelectAll");
  preUploadIndexList = document.getElementById("preUploadIndexList");
  existingIndexPanel = document.getElementById("existingIndexPanel");
  existingIndexSelectAll = document.getElementById("existingIndexSelectAll");
  existingIndexList = document.getElementById("existingIndexList");
  runExistingIndexBtn = document.getElementById("runExistingIndexBtn");
  taskProgress = document.getElementById("taskProgress");
  taskProgressLabel = document.getElementById("taskProgressLabel");
  taskProgressPercent = document.getElementById("taskProgressPercent");
  taskProgressBar = document.getElementById("taskProgressBar");
  taskProgressMeta = document.getElementById("taskProgressMeta");
  triageStatus = document.getElementById("triageStatus");
  triageList = document.getElementById("triageList");
  triageDetail = document.getElementById("triageDetail");
  videoList = document.getElementById("videoList");
  embeddingProfileSelect = document.getElementById("embeddingProfileSelect");
  embeddingDeviceSelect = document.getElementById("embeddingDeviceSelect");
  saveEmbeddingSettingsBtn = document.getElementById("saveEmbeddingSettingsBtn");
  embeddingSettingsMeta = document.getElementById("embeddingSettingsMeta");
  analysisStatus = document.getElementById("analysisStatus");
  runFacePeopleSelectedBtn = document.getElementById("runFacePeopleSelectedBtn");
  runVehiclesSelectedBtn = document.getElementById("runVehiclesSelectedBtn");
  mainTabTriageBtn = document.getElementById("mainTabTriageBtn");
  mainTabSemanticBtn = document.getElementById("mainTabSemanticBtn");
  mainTabFacePeopleBtn = document.getElementById("mainTabFacePeopleBtn");
  mainTabVehiclesBtn = document.getElementById("mainTabVehiclesBtn");
  workspaceBackBtn = document.getElementById("workspaceBackBtn");
  workspaceAnalysisBtn = document.getElementById("workspaceAnalysisBtn");
  workspaceReportBtn = document.getElementById("workspaceReportBtn");
  workspaceSettingsBtn = document.getElementById("workspaceSettingsBtn");
  workspaceExitBtn = document.getElementById("workspaceExitBtn");
  tabTriage = document.getElementById("tabTriage");
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
  semanticSearchMeta = document.getElementById("semanticSearchMeta");
  resultsGrid = document.getElementById("resultsGrid");
  triagePlayer = document.getElementById("triagePlayer");
  triagePlayerMeta = document.getElementById("triagePlayerMeta");
  videoPlayer = document.getElementById("videoPlayer");
  playerMeta = document.getElementById("playerMeta");
  activeCaseMeta = document.getElementById("activeCaseMeta");
  caseList = document.getElementById("caseList");
  appShell = document.querySelector("main.app-shell");
  workspace = document.querySelector(".workspace");
  workspaceSettingsPage = document.getElementById("workspaceSettingsPage");
  workspaceReportPage = document.getElementById("workspaceReportPage");
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

function setTriageStatus(message, kind = "") {
  if (!triageStatus) {
    return;
  }
  triageStatus.textContent = message;
  triageStatus.className = `status ${kind}`.trim();
}

function setSemanticSearchMeta(message, kind = "") {
  if (!semanticSearchMeta) {
    return;
  }
  semanticSearchMeta.textContent = String(message || "");
  semanticSearchMeta.className = `status ${kind}`.trim();
}

function formatProcessSummaryForConfirm(processPayload) {
  const processes = Array.isArray(processPayload?.processes) ? processPayload.processes : [];
  if (!processes.length) {
    return "No active background processes found.";
  }

  const lines = processes.map((item, index) => {
    const processType = String(item?.type || "process");
    const caseId = String(item?.case_id || "unknown");
    const status = String(item?.status || "running");
    const currentFilename = String(item?.current_filename || "").trim();
    const completed = Math.max(0, Number(item?.completed || 0));
    const total = Math.max(0, Number(item?.total || 0));
    const progress = Number.isFinite(Number(item?.progress_percent))
      ? Math.max(0, Math.min(100, Number(item.progress_percent)))
      : 0;
    const filePart = currentFilename ? ` | file: ${currentFilename}` : "";
    return `${index + 1}. ${processType} | case=${caseId} | status=${status} | ${completed}/${total} (${progress.toFixed(1)}%)${filePart}`;
  });

  return lines.join("\n");
}

async function requestGracefulExit() {
  try {
    setStatus("Checking active processes before exit...", "working");
    const processPayload = await fetchJson("/processes");
    const processSummary = formatProcessSummaryForConfirm(processPayload);
    const promptMessage = [
      "Graceful exit will stop background work and shut down the local server.",
      "",
      "Current processes:",
      processSummary,
      "",
      "Proceed with graceful exit?",
    ].join("\n");

    const confirmed = window.confirm(promptMessage);
    if (!confirmed) {
      setStatus("Exit cancelled.", "ok");
      return;
    }

    setStatus("Stopping processes and shutting down...", "working");
    const shutdownPayload = await fetchJson("/shutdown", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true }),
    });

    const cancelledCount = Math.max(0, Number(shutdownPayload?.cancelled_count || 0));
    const message = cancelledCount > 0
      ? `Shutdown scheduled. Cancelled ${cancelledCount} background process(es).`
      : "Shutdown scheduled. No background processes were running.";
    setStatus(`${message} Closing tab if allowed...`, "ok");
    setTriageStatus(message, "ok");
    setAnalysisStatus(message, "ok");
    setVehicleStatus(message, "ok");

    window.setTimeout(() => {
      window.close();
    }, 300);
  } catch (error) {
    setStatus(`Exit failed: ${formatError(error)}`, "error");
  }
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

function makePendingUploadSourceKey(file, sourceIndex) {
  const safeIndex = Number.isFinite(Number(sourceIndex)) ? Number(sourceIndex) : 0;
  const safeName = String(file?.name || "");
  const safeSize = Number(file?.size || 0);
  const safeModified = Number(file?.lastModified || 0);
  return `${safeIndex}::${safeName}::${safeSize}::${safeModified}`;
}

function syncPreUploadSelectAllControl() {
  if (!preUploadSelectAll) {
    return;
  }
  if (!pendingUploadItems.length) {
    preUploadSelectAll.checked = false;
    preUploadSelectAll.indeterminate = false;
    preUploadSelectAll.disabled = true;
    return;
  }

  const selectedCount = pendingUploadItems.reduce(
    (count, item) => count + (item.selectedForIndex ? 1 : 0),
    0,
  );
  preUploadSelectAll.disabled = false;
  preUploadSelectAll.checked = selectedCount === pendingUploadItems.length;
  preUploadSelectAll.indeterminate = selectedCount > 0 && selectedCount < pendingUploadItems.length;
}

function renderPreUploadIndexSelection() {
  if (!preUploadIndexPanel || !preUploadIndexList) {
    return;
  }

  preUploadIndexList.innerHTML = "";
  if (!pendingUploadItems.length) {
    preUploadIndexPanel.hidden = true;
    syncPreUploadSelectAllControl();
    return;
  }

  preUploadIndexPanel.hidden = false;
  pendingUploadItems.forEach((item) => {
    const row = document.createElement("div");
    row.className = "analysis-video-item";

    const label = document.createElement("label");
    label.className = "analysis-video-label";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "analysis-select-checkbox";
    checkbox.checked = Boolean(item.selectedForIndex);
    checkbox.dataset.sourceIndex = String(item.sourceIndex);
    checkbox.addEventListener("change", () => {
      item.selectedForIndex = Boolean(checkbox.checked);
      syncPreUploadSelectAllControl();
    });

    const text = document.createElement("span");
    text.className = "analysis-video-name";
    text.textContent = item.name;

    label.appendChild(checkbox);
    label.appendChild(text);

    const status = document.createElement("div");
    status.className = "analysis-video-status";
    status.textContent = formatBytes(item.sizeBytes);

    row.appendChild(label);
    row.appendChild(status);
    preUploadIndexList.appendChild(row);
  });

  syncPreUploadSelectAllControl();
}

function refreshPendingUploadItemsFromInput() {
  const files = Array.from(videoInput?.files || []);
  const previousSelection = new Map(
    pendingUploadItems.map((item) => [item.sourceKey, Boolean(item.selectedForIndex)]),
  );
  pendingUploadItems = files.map((file, sourceIndex) => {
    const sourceKey = makePendingUploadSourceKey(file, sourceIndex);
    const selectedForIndex = previousSelection.has(sourceKey)
      ? Boolean(previousSelection.get(sourceKey))
      : true;
    return {
      sourceIndex,
      sourceKey,
      name: String(file?.name || ""),
      sizeBytes: Number(file?.size || 0),
      selectedForIndex,
    };
  });
  renderPreUploadIndexSelection();
}

function clearPendingUploadItems() {
  pendingUploadItems = [];
  renderPreUploadIndexSelection();
}

function setAllPendingUploadSelection(checked) {
  pendingUploadItems.forEach((item) => {
    item.selectedForIndex = Boolean(checked);
  });
  renderPreUploadIndexSelection();
}

function getSelectedPendingUploadSourceIndices(files) {
  const fileCount = Array.isArray(files) ? files.length : 0;
  if (!fileCount) {
    return new Set();
  }

  if (pendingUploadItems.length !== fileCount) {
    return new Set(Array.from({ length: fileCount }, (_, index) => index));
  }

  const selected = new Set();
  pendingUploadItems.forEach((item) => {
    if (item.selectedForIndex) {
      selected.add(Number(item.sourceIndex));
    }
  });
  return selected;
}

function resolveSelectedSemanticIndexTargets(uploadResult, selectedSourceIndices, files) {
  const uploadedItems = Array.isArray(uploadResult?.uploaded_items)
    ? uploadResult.uploaded_items
    : [];
  const uploadedNames = Array.isArray(uploadResult?.uploaded) ? uploadResult.uploaded : [];
  const targets = [];
  const seen = new Set();

  for (const item of uploadedItems) {
    const sourceIndex = Number(item?.source_index);
    const storedFilename = String(item?.stored_filename || "").trim();
    if (!Number.isFinite(sourceIndex) || !storedFilename) {
      continue;
    }
    if (!selectedSourceIndices.has(sourceIndex) || seen.has(storedFilename)) {
      continue;
    }
    seen.add(storedFilename);
    targets.push(storedFilename);
  }

  if (targets.length > 0) {
    return targets;
  }

  const selectedSourceNames = new Set(
    files
      .map((file, sourceIndex) => ({ file, sourceIndex }))
      .filter((item) => selectedSourceIndices.has(item.sourceIndex))
      .map((item) => String(item.file?.name || "").trim())
      .filter(Boolean),
  );

  for (const uploadedName of uploadedNames) {
    const normalized = String(uploadedName || "").trim();
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    if (selectedSourceNames.has(normalized)) {
      seen.add(normalized);
      targets.push(normalized);
    }
  }

  if (
    targets.length === 0
    && selectedSourceIndices.size === files.length
    && selectedSourceIndices.size > 0
  ) {
    for (const uploadedName of uploadedNames) {
      const normalized = String(uploadedName || "").trim();
      if (!normalized || seen.has(normalized)) {
        continue;
      }
      seen.add(normalized);
      targets.push(normalized);
    }
  }

  return targets;
}

function isVideoSemanticallyIndexed(video) {
  const indexedFrames = Math.max(0, Number(video?.indexed_frames || 0));
  const indexedWindows = Math.max(0, Number(video?.indexed_windows || 0));
  return indexedFrames > 0 || indexedWindows > 0;
}

function getExistingIndexCheckboxes() {
  if (!existingIndexList) {
    return [];
  }
  return Array.from(
    existingIndexList.querySelectorAll("input.existing-index-checkbox[data-filename]"),
  );
}

function syncExistingIndexSelectAllControl() {
  if (!existingIndexSelectAll) {
    return;
  }
  const checkboxes = getExistingIndexCheckboxes();
  if (!checkboxes.length) {
    existingIndexSelectAll.checked = false;
    existingIndexSelectAll.indeterminate = false;
    existingIndexSelectAll.disabled = true;
    return;
  }

  const selectedCount = checkboxes.reduce(
    (count, input) => count + (input.checked ? 1 : 0),
    0,
  );
  existingIndexSelectAll.disabled = false;
  existingIndexSelectAll.checked = selectedCount === checkboxes.length;
  existingIndexSelectAll.indeterminate = selectedCount > 0 && selectedCount < checkboxes.length;
}

function setAllExistingIndexSelection(checked) {
  const checkboxes = getExistingIndexCheckboxes();
  checkboxes.forEach((input) => {
    input.checked = Boolean(checked);
  });
  syncExistingIndexSelectAllControl();
}

function getSelectedExistingIndexFilenames() {
  const checkboxes = getExistingIndexCheckboxes();
  return checkboxes
    .filter((input) => input.checked)
    .map((input) => String(input.dataset.filename || "").trim())
    .filter(Boolean);
}

function renderExistingIndexSelectionList(videos) {
  if (!existingIndexPanel || !existingIndexList) {
    return;
  }

  const activeCaseId = String(state.activeCaseId || "").trim();
  existingIndexList.innerHTML = "";

  if (!activeCaseId) {
    existingIndexPanel.hidden = true;
    if (runExistingIndexBtn) {
      runExistingIndexBtn.disabled = true;
    }
    syncExistingIndexSelectAllControl();
    return;
  }

  existingIndexPanel.hidden = false;
  const list = Array.isArray(videos) ? videos : [];
  if (!list.length) {
    existingIndexList.appendChild(createInsightEmptyElement("No uploaded videos yet."));
    if (runExistingIndexBtn) {
      runExistingIndexBtn.disabled = true;
    }
    syncExistingIndexSelectAllControl();
    return;
  }

  const unindexedVideos = list
    .filter((video) => !isVideoSemanticallyIndexed(video))
    .sort((a, b) => String(a.filename).localeCompare(String(b.filename)));

  if (!unindexedVideos.length) {
    existingIndexList.appendChild(
      createInsightEmptyElement("All uploaded videos are already semantically indexed."),
    );
    if (runExistingIndexBtn) {
      runExistingIndexBtn.disabled = true;
    }
    syncExistingIndexSelectAllControl();
    return;
  }

  unindexedVideos.forEach((video) => {
    const row = document.createElement("div");
    row.className = "analysis-video-item";

    const label = document.createElement("label");
    label.className = "analysis-video-label";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.className = "analysis-select-checkbox existing-index-checkbox";
    checkbox.dataset.filename = String(video.filename || "");
    checkbox.addEventListener("change", () => {
      syncExistingIndexSelectAllControl();
    });

    const text = document.createElement("span");
    text.className = "analysis-video-name";
    text.textContent = String(video.filename || "");

    label.appendChild(checkbox);
    label.appendChild(text);

    const status = document.createElement("div");
    status.className = "analysis-video-status";
    status.textContent = `${formatBytes(video.size_bytes)} | not indexed`;

    row.appendChild(label);
    row.appendChild(status);
    existingIndexList.appendChild(row);
  });

  if (runExistingIndexBtn) {
    runExistingIndexBtn.disabled = false;
  }
  syncExistingIndexSelectAllControl();
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

function isBackgroundIndexRunning(statusPayload) {
  if (!statusPayload || typeof statusPayload !== "object") {
    return false;
  }
  if (Boolean(statusPayload.running)) {
    return true;
  }
  const status = String(statusPayload.status || "").toLowerCase();
  return status === "queued" || status === "running";
}

function backgroundIndexProgressPercent(statusPayload) {
  const total = Math.max(0, Number(statusPayload?.total || 0));
  const completed = Math.max(0, Number(statusPayload?.completed || 0));
  const status = String(statusPayload?.status || "").toLowerCase();
  const currentVideoPercent = Number(statusPayload?.current_video_progress_percent);

  if (
    total > 0
    && (status === "running" || status === "queued")
    && Number.isFinite(currentVideoPercent)
    && currentVideoPercent > 0
  ) {
    return clampPercent(((completed + (Math.min(100, currentVideoPercent) / 100)) / total) * 100);
  }

  const payloadPercent = Number(statusPayload?.progress_percent);
  if (Number.isFinite(payloadPercent)) {
    return clampPercent(payloadPercent);
  }
  if (total <= 0) {
    return 0;
  }
  return clampPercent((completed / total) * 100);
}

function formatBackgroundIndexMeta(statusPayload) {
  const total = Math.max(0, Number(statusPayload?.total || 0));
  const completed = Math.max(0, Number(statusPayload?.completed || 0));
  const processed = Math.max(0, Number(statusPayload?.processed || 0));
  const skipped = Math.max(0, Number(statusPayload?.skipped || 0));
  const failed = Math.max(0, Number(statusPayload?.failed || 0));
  const currentFilename = String(statusPayload?.current_filename || "").trim();
  const currentVideoProcessed = Math.max(0, Number(statusPayload?.current_video_processed_frames || 0));
  const currentVideoTotal = Math.max(0, Number(statusPayload?.current_video_total_frames || 0));
  const currentVideoPercent = clampPercent(Number(statusPayload?.current_video_progress_percent || 0));
  const currentVideoEta = statusPayload?.current_video_eta_seconds;

  const lead = currentFilename ? `Current: ${currentFilename}` : "Waiting for next file";
  const parts = [`${lead}`, `${completed}/${total} done`, `processed ${processed}, skipped ${skipped}, failed ${failed}`];

  if (currentFilename) {
    const totalLabel = currentVideoTotal > 0 ? String(currentVideoTotal) : "?";
    parts.push(`this video ${currentVideoProcessed}/${totalLabel} (${Math.round(currentVideoPercent)}%)`);
    parts.push(formatEtaLabel(currentVideoEta));
  }

  return parts.join(" | ");
}

function stopBackgroundIndexPolling() {
  indexStatusPollToken += 1;
  indexStatusPollCaseId = "";
}

function renderBackgroundIndexStatus(caseId, statusPayload) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId || state.activeCaseId !== normalizedCaseId) {
    return;
  }
  if (uploadFlowActive) {
    return;
  }
  if (!statusPayload || typeof statusPayload !== "object") {
    hideTaskProgressUi();
    return;
  }

  const status = String(statusPayload.status || "").toLowerCase();
  if (status === "idle") {
    hideTaskProgressUi();
    return;
  }

  const progressPercent = backgroundIndexProgressPercent(statusPayload);
  const meta = formatBackgroundIndexMeta(statusPayload);
  if (isBackgroundIndexRunning(statusPayload)) {
    backgroundIndexTerminalSeen.delete(normalizedCaseId);
    setTaskProgressUi("Semantic indexing (background)", progressPercent, meta);
    setStatus(`Semantic indexing is running in background for ${normalizedCaseId}.`, "working");
    return;
  }

  const terminalKey = [
    status,
    String(statusPayload.finished_at || ""),
    String(statusPayload.completed || 0),
    String(statusPayload.failed || 0),
  ].join("|");
  if (backgroundIndexTerminalSeen.get(normalizedCaseId) === terminalKey) {
    return;
  }
  backgroundIndexTerminalSeen.set(normalizedCaseId, terminalKey);

  const failed = Math.max(0, Number(statusPayload.failed || 0));
  const indexedFrames = Math.max(0, Number(statusPayload.indexed_frames || 0));
  const indexedWindows = Math.max(0, Number(statusPayload.indexed_windows || 0));
  const summary = `Background indexing finished for ${normalizedCaseId}: indexed frames ${indexedFrames}, temporal windows ${indexedWindows}, failed ${failed}.`;
  completeTaskProgressUi("Background indexing finished", meta);
  setStatus(summary, failed > 0 ? "error" : "ok");
}

async function readBackgroundIndexStatus(caseId) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    return null;
  }
  try {
    return await fetchJson(withCaseQuery("/index/status", normalizedCaseId));
  } catch (error) {
    console.warn(`Background index status unavailable for ${normalizedCaseId}: ${formatError(error)}`);
    return null;
  }
}

function startBackgroundIndexPolling(caseId) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    return;
  }

  stopBackgroundIndexPolling();
  indexStatusPollCaseId = normalizedCaseId;
  const pollToken = ++indexStatusPollToken;

  const poll = async () => {
    if (pollToken !== indexStatusPollToken || indexStatusPollCaseId !== normalizedCaseId) {
      return;
    }

    const statusPayload = await readBackgroundIndexStatus(normalizedCaseId);
    if (pollToken !== indexStatusPollToken || indexStatusPollCaseId !== normalizedCaseId) {
      return;
    }
    if (!statusPayload) {
      window.setTimeout(poll, 1800);
      return;
    }

    renderBackgroundIndexStatus(normalizedCaseId, statusPayload);
    if (isBackgroundIndexRunning(statusPayload)) {
      window.setTimeout(poll, 1300);
      return;
    }

    if (state.activeCaseId === normalizedCaseId) {
      try {
        await refreshVideos(normalizedCaseId);
      } catch (error) {
        console.warn(`Refresh after background index failed: ${formatError(error)}`);
      }
    }

    if (pollToken === indexStatusPollToken && indexStatusPollCaseId === normalizedCaseId) {
      stopBackgroundIndexPolling();
    }
  };

  void poll();
}

async function syncBackgroundIndexStatus(caseId) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    stopBackgroundIndexPolling();
    hideTaskProgressUi();
    return null;
  }

  const statusPayload = await readBackgroundIndexStatus(normalizedCaseId);
  if (!statusPayload) {
    if (state.activeCaseId === normalizedCaseId) {
      hideTaskProgressUi();
    }
    return null;
  }

  renderBackgroundIndexStatus(normalizedCaseId, statusPayload);
  if (isBackgroundIndexRunning(statusPayload)) {
    startBackgroundIndexPolling(normalizedCaseId);
  } else if (indexStatusPollCaseId === normalizedCaseId) {
    stopBackgroundIndexPolling();
  }
  return statusPayload;
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
  const triageActive = state.activeMainTab === "triage";
  const semanticActive = state.activeMainTab === "semantic";
  const faceActive = state.activeMainTab === "face_people";
  const vehicleActive = state.activeMainTab === "vehicles";

  mainTabTriageBtn?.classList.toggle("active", triageActive);
  mainTabSemanticBtn?.classList.toggle("active", semanticActive);
  mainTabFacePeopleBtn?.classList.toggle("active", faceActive);
  mainTabVehiclesBtn?.classList.toggle("active", vehicleActive);

  tabTriage?.classList.toggle("active", triageActive);
  tabSemantic?.classList.toggle("active", semanticActive);
  tabFacePeople?.classList.toggle("active", faceActive);
  tabVehicles?.classList.toggle("active", vehicleActive);
}

function applyWorkspaceView() {
  const settingsActive = state.workspaceView === "settings" && Boolean(state.activeCaseId);
  const reportActive = state.workspaceView === "report" && Boolean(state.activeCaseId);
  workspace?.classList.toggle("show-settings", settingsActive);
  workspace?.classList.toggle("show-report", reportActive);
  if (workspaceSettingsPage) {
    workspaceSettingsPage.hidden = !settingsActive;
  }
  if (workspaceReportPage) {
    workspaceReportPage.hidden = !reportActive;
  }
  if (workspaceSettingsBtn) {
    workspaceSettingsBtn.classList.toggle("active", settingsActive);
    workspaceSettingsBtn.setAttribute("aria-pressed", settingsActive ? "true" : "false");
  }
  if (workspaceReportBtn) {
    workspaceReportBtn.classList.toggle("active", reportActive);
    workspaceReportBtn.setAttribute("aria-pressed", reportActive ? "true" : "false");
  }
  if (workspaceAnalysisBtn) {
    const analysisActive = !settingsActive && !reportActive && Boolean(state.activeCaseId);
    workspaceAnalysisBtn.classList.toggle("active", analysisActive);
    workspaceAnalysisBtn.setAttribute("aria-pressed", analysisActive ? "true" : "false");
  }
}

function setWorkspaceView(viewKey) {
  if (viewKey === "settings") {
    state.workspaceView = "settings";
  } else if (viewKey === "report") {
    state.workspaceView = "report";
  } else {
    state.workspaceView = "analysis";
  }
  applyWorkspaceView();
}

function setActiveMainTab(tabKey) {
  const normalized =
    tabKey === "triage" || tabKey === "face_people" || tabKey === "vehicles"
      ? tabKey
      : "semantic";
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
  const hasActiveCase = Boolean(state.activeCaseId);
  if (!hasActiveCase) {
    stopBackgroundIndexPolling();
    hideTaskProgressUi();
  }
  if (appShell) {
    appShell.classList.toggle("repository-mode", !hasActiveCase);
    appShell.classList.toggle("workspace-mode", hasActiveCase);
  }
  if (!hasActiveCase && state.workspaceView !== "analysis") {
    state.workspaceView = "analysis";
  }
  applyWorkspaceView();
  renderMainTabs();
  if (activeCaseMeta) {
    if (!hasActiveCase) {
      activeCaseMeta.textContent = "";
      setSemanticSearchMeta("", "");
      setTriageStatus("", "");
      setAnalysisStatus("", "");
      setVehicleStatus("", "");
    } else {
      const activeCase = state.cases.find((item) => item.case_id === state.activeCaseId);
      const activeName = activeCase?.name || state.activeCaseId;
      const createdAtLabel = formatCaseCreatedAt(activeCase?.created_at);
      activeCaseMeta.textContent = `Active Case: ${activeName} (${state.activeCaseId}) | Created: ${createdAtLabel}`;
      setSemanticSearchMeta("Search type will appear here after querying.", "");
    }
  }
}

function backToCaseRepository() {
  if (!state.activeCaseId) {
    stopBackgroundIndexPolling();
    hideTaskProgressUi();
    setWorkspaceView("analysis");
    syncWorkspaceVisibility();
    return;
  }
  saveActiveCasePlaybackSnapshot();
  stopBackgroundIndexPolling();
  hideTaskProgressUi();
  state.activeCaseId = null;
  setWorkspaceView("analysis");
  markCaseStateChanged();
  setCaseUrl(null);
  clearResults();
  renderVideoList([]);
  renderTriagePanels();
  resetPlayerForCase(null);
  resetAuxPlayers(null);
  renderCaseList();
  syncWorkspaceVisibility();
  setStatus("Case repository ready. Select a case to open workspace tabs.", "ok");
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
  if (triagePlayer && triagePlayerMeta) {
    triagePlayer.pause();
    triagePlayer.removeAttribute("src");
    triagePlayer.load();
    triagePlayer.dataset.filename = "";
    triagePlayer.dataset.videoUrl = "";
    triagePlayer.dataset.caseId = normalizedCaseId;
    triagePlayerMeta.textContent = normalizedCaseId
      ? `Case ${normalizedCaseId}: select a triage timeline point.`
      : "Select a timeline point to preview.";
  }
  updateTriageTimelinePlayheads(0);
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

  if (
    state.activeCaseId
    && !state.cases.some((item) => item.case_id === state.activeCaseId)
  ) {
    state.activeCaseId = null;
  }
  if (!state.cases.length && !stateChangedDuringRequest) {
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
  for (const cachedCaseId of triageCache.keys()) {
    if (!validCaseIds.has(cachedCaseId)) {
      triageCache.delete(cachedCaseId);
    }
  }
  for (const key of triageErrors.keys()) {
    const [cachedCaseId] = String(key).split("::", 1);
    if (!validCaseIds.has(cachedCaseId)) {
      triageErrors.delete(key);
    }
  }
  for (const cachedCaseId of triageSelection.keys()) {
    if (!validCaseIds.has(cachedCaseId)) {
      triageSelection.delete(cachedCaseId);
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
    renderExistingIndexSelectionList(Array.isArray(videos) ? videos : []);
    return;
  }
  videoList.innerHTML = "";
  if (!videos.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No uploaded videos yet.";
    videoList.appendChild(empty);
    renderExistingIndexSelectionList(videos);
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
  renderExistingIndexSelectionList(videos);
}

function getCaseVideos(caseId = null) {
  const resolvedCaseId = caseId || state.activeCaseId;
  if (!resolvedCaseId) {
    return [];
  }
  const videos = state.caseVideos.get(String(resolvedCaseId));
  return Array.isArray(videos) ? videos : [];
}

function makeTriageKey(caseId, filename) {
  return `${String(caseId || "").trim()}::${String(filename || "").trim()}`;
}

function ensureCaseTriageCache(caseId) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    return null;
  }
  let caseCache = triageCache.get(normalizedCaseId);
  if (!caseCache) {
    caseCache = new Map();
    triageCache.set(normalizedCaseId, caseCache);
  }
  return caseCache;
}

function getTriagePayload(caseId, filename) {
  const caseCache = ensureCaseTriageCache(caseId);
  if (!caseCache) {
    return null;
  }
  return caseCache.get(String(filename || "").trim()) || null;
}

function setTriagePayload(caseId, filename, payload) {
  const caseCache = ensureCaseTriageCache(caseId);
  if (!caseCache) {
    return;
  }
  caseCache.set(String(filename || "").trim(), payload);
}

function clearCaseTriageCache(caseId) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    return;
  }
  triageCache.delete(normalizedCaseId);
  triageSelection.delete(normalizedCaseId);
  for (const key of triageErrors.keys()) {
    if (String(key).startsWith(`${normalizedCaseId}::`)) {
      triageErrors.delete(key);
    }
  }
}

function ensureSelectedTriageVideo(caseId, videos) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    return "";
  }
  const list = Array.isArray(videos) ? videos : [];
  if (!list.length) {
    triageSelection.delete(normalizedCaseId);
    return "";
  }
  const current = String(triageSelection.get(normalizedCaseId) || "").trim();
  if (current && list.some((item) => item && item.filename === current)) {
    return current;
  }
  const firstFilename = String(list[0]?.filename || "").trim();
  if (firstFilename) {
    triageSelection.set(normalizedCaseId, firstFilename);
    return firstFilename;
  }
  triageSelection.delete(normalizedCaseId);
  return "";
}

function getSelectedTriageVideo(caseId = null) {
  const resolvedCaseId = String(caseId || state.activeCaseId || "").trim();
  if (!resolvedCaseId) {
    return null;
  }
  const videos = getCaseVideos(resolvedCaseId);
  if (!videos.length) {
    return null;
  }
  const selectedFilename = ensureSelectedTriageVideo(resolvedCaseId, videos);
  if (!selectedFilename) {
    return null;
  }
  return videos.find((item) => item && item.filename === selectedFilename) || null;
}

function triageIntensityColor(intensity, kind = "activity") {
  const value = Math.max(0, Math.min(1, Number(intensity) || 0));
  if (kind === "audio") {
    const hue = 210 - (value * 55);
    const sat = 72;
    const light = 84 - (value * 38);
    return `hsl(${hue} ${sat}% ${light}%)`;
  }
  const hue = 130 - (value * 118);
  const sat = 72;
  const light = 80 - (value * 35);
  return `hsl(${hue} ${sat}% ${light}%)`;
}

function updateTriageTimelinePlayheads(forcedTimestampSeconds = null) {
  if (!triageDetail) {
    return;
  }
  const layers = triageDetail.querySelectorAll(".timeline-playhead-layer");
  if (!layers.length) {
    return;
  }

  const activeCaseId = String(state.activeCaseId || "").trim();
  const selectedVideo = getSelectedTriageVideo(activeCaseId);
  const selectedFilename = String(selectedVideo?.filename || "").trim();
  const playerCaseId = String(triagePlayer?.dataset.caseId || "").trim();
  const playerFilename = String(triagePlayer?.dataset.filename || "").trim();
  const isSameVideo =
    Boolean(activeCaseId)
    && Boolean(selectedFilename)
    && selectedFilename === playerFilename
    && playerCaseId === activeCaseId;

  const fallbackTime = Number(triagePlayer?.currentTime || 0);
  const requestedTime = forcedTimestampSeconds === null
    ? fallbackTime
    : Number(forcedTimestampSeconds);
  const safeTime = Math.max(0, Number.isFinite(requestedTime) ? requestedTime : 0);

  layers.forEach((layer) => {
    const totalSeconds = Number(layer.dataset.totalSeconds || 0);
    const line = layer.querySelector(".timeline-playhead-line");
    const dot = layer.querySelector(".timeline-playhead-dot");
    const tooltip = layer.querySelector(".timeline-playhead-tooltip");
    const shouldShow = isSameVideo && Number.isFinite(totalSeconds) && totalSeconds > 0;
    layer.classList.toggle("visible", shouldShow);
    if (!shouldShow || !line || !dot || !tooltip) {
      return;
    }

    const progress = Math.max(0, Math.min(1, safeTime / totalSeconds));
    const width = Math.max(1, layer.clientWidth || layer.getBoundingClientRect().width || 1);
    const inset = 6;
    const usableWidth = Math.max(1, width - (inset * 2));
    const x = inset + (usableWidth * progress);
    line.style.left = `${x}px`;
    dot.style.left = `${x}px`;
    tooltip.style.left = `${x}px`;
    tooltip.textContent = formatTime(safeTime);
  });
}

function drawTriageTimeline(canvas, values, peaks, kind = "activity", options = {}) {
  if (!canvas) {
    return;
  }
  const safeValues = Array.isArray(values) ? values : [];
  const safeLineTimestamps = Array.isArray(options?.lineTimestamps) ? options.lineTimestamps : [];
  const safeTotalSeconds = Math.max(0, Number(options?.totalSeconds || 0));
  const width = 820;
  const height = 56;
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return;
  }

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#f3f7fb";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#d3dfe9";
  ctx.fillRect(0, height - 1, width, 1);

  if (!safeValues.length) {
    return;
  }

  for (let i = 0; i < safeValues.length; i += 1) {
    const intensity = Math.max(0, Math.min(1, Number(safeValues[i]) || 0));
    const x1 = Math.floor((i / safeValues.length) * width);
    const x2 = Math.floor(((i + 1) / safeValues.length) * width);
    const barWidth = Math.max(1, x2 - x1);
    const barHeight = Math.max(1, Math.round(intensity * (height - 6)));
    ctx.fillStyle = triageIntensityColor(intensity, kind);
    ctx.fillRect(x1, height - barHeight - 1, barWidth, barHeight);
  }

  if (!(safeTotalSeconds > 0) || !safeLineTimestamps.length) {
    return;
  }

  const seenX = new Set();
  for (const ts of safeLineTimestamps) {
    const numericTs = Number(ts);
    if (!Number.isFinite(numericTs) || numericTs < 0) {
      continue;
    }
    const ratio = Math.max(0, Math.min(1, numericTs / safeTotalSeconds));
    const x = Math.max(0, Math.min(width - 1, Math.round(ratio * (width - 1))));
    const key = String(x);
    if (seenX.has(key)) {
      continue;
    }
    seenX.add(key);
    ctx.strokeStyle = "rgba(34, 74, 106, 0.36)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x + 0.5, 0);
    ctx.lineTo(x + 0.5, height);
    ctx.stroke();
  }
}

function triageLocalPeakTimestamps(
  values,
  {
    bucketSeconds = 1,
    durationSeconds = 0,
    maxCount = 24,
    minGapSeconds = 1.2,
    minIntensity = 0.08,
    minProminence = 0.012,
  } = {},
) {
  const safeValues = Array.isArray(values) ? values : [];
  if (!safeValues.length) {
    return [];
  }
  const safeBucketSeconds = Math.max(0.001, Number(bucketSeconds || 1));
  const safeDurationSeconds = Math.max(0, Number(durationSeconds || 0));
  const minGapBuckets = Math.max(1, Math.round(minGapSeconds / safeBucketSeconds));

  const candidates = [];
  for (let i = 0; i < safeValues.length; i += 1) {
    const center = Math.max(0, Math.min(1, Number(safeValues[i]) || 0));
    if (center < minIntensity) {
      continue;
    }
    const left = i > 0 ? Math.max(0, Math.min(1, Number(safeValues[i - 1]) || 0)) : center;
    const right = i < (safeValues.length - 1)
      ? Math.max(0, Math.min(1, Number(safeValues[i + 1]) || 0))
      : center;
    const isLocalMax = center >= left && center >= right && (center > left || center > right);
    if (!isLocalMax) {
      continue;
    }
    const prominence = center - Math.max(left, right);
    if (prominence < minProminence && center < (minIntensity * 1.8)) {
      continue;
    }
    const score = center + (Math.max(0, prominence) * 0.65);
    candidates.push({ index: i, score });
  }

  if (!candidates.length) {
    return [];
  }

  candidates.sort((a, b) => b.score - a.score);
  const selected = [];
  const out = [];
  for (const item of candidates) {
    if (selected.some((idx) => Math.abs(idx - item.index) < minGapBuckets)) {
      continue;
    }
    selected.push(item.index);
    const rawTs = item.index * safeBucketSeconds;
    const ts = safeDurationSeconds > 0
      ? Math.min(safeDurationSeconds, rawTs)
      : rawTs;
    out.push(Math.max(0, ts));
    if (out.length >= maxCount) {
      break;
    }
  }
  return out.sort((a, b) => a - b);
}

function triagePeakTimestamps(
  peaks,
  {
    values = [],
    bucketSeconds = 1,
    durationSeconds = 0,
  } = {},
) {
  const timestamps = [];
  const seen = new Set();
  const addTimestamp = (value) => {
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric < 0) {
      return;
    }
    const rounded = Math.round(numeric * 1000) / 1000;
    const key = String(rounded);
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    timestamps.push(rounded);
  };

  if (Array.isArray(peaks)) {
    for (const peak of peaks) {
      addTimestamp(peak?.timestamp_seconds);
    }
  }

  const fallbackLocals = triageLocalPeakTimestamps(values, {
    bucketSeconds,
    durationSeconds,
    maxCount: 24,
    minGapSeconds: 1.2,
    minIntensity: 0.08,
    minProminence: 0.012,
  });
  for (const ts of fallbackLocals) {
    addTimestamp(ts);
  }
  return timestamps.sort((a, b) => a - b);
}

function isMediaPlayerPlaying(player) {
  return Boolean(
    player
    && !player.paused
    && !player.ended
    && Number(player.readyState || 0) >= 1,
  );
}

function playTriageAt(video, timestampSeconds, options = {}) {
  if (!video || !state.activeCaseId) {
    return;
  }
  const safeTimestamp = Math.max(0, Number(timestampSeconds) || 0);
  const shouldAutoPlay = options.autoPlay === true;
  const fallbackVideoUrl = `/media/cases/${encodeURIComponent(state.activeCaseId)}/videos/${encodeURIComponent(video.filename)}`;
  const videoUrl = String(video.video_url || fallbackVideoUrl);
  if (triagePlayer && triagePlayerMeta) {
    playInPlayer(
      triagePlayer,
      triagePlayerMeta,
      video.filename,
      videoUrl,
      safeTimestamp,
      { autoPlay: shouldAutoPlay },
    );
  }
  updateTriageTimelinePlayheads(safeTimestamp);
  playVideoAt(video.filename, videoUrl, safeTimestamp, { autoPlay: shouldAutoPlay });
}

function createTriageTimelineRow({
  title,
  values,
  peaks,
  kind,
  video,
  bucketSeconds,
  durationSeconds,
}) {
  const row = document.createElement("div");
  row.className = "timeline-row";
  const label = document.createElement("div");
  label.className = "timeline-label";
  const titleEl = document.createElement("span");
  titleEl.textContent = title;
  const detailEl = document.createElement("span");
  detailEl.className = "timeline-label-detail";
  const primaryPeak = Array.isArray(peaks) && peaks.length ? peaks[0] : null;
  detailEl.textContent = primaryPeak && Number.isFinite(Number(primaryPeak.timestamp_seconds))
    ? `Peak @ ${formatTime(Number(primaryPeak.timestamp_seconds))}`
    : "No peak detected";
  const safeValues = Array.isArray(values) ? values : [];
  const safeBucketSeconds = Math.max(0.001, Number(bucketSeconds || 1));
  const safeDurationSeconds = Math.max(0, Number(durationSeconds || 0));
  const totalSeconds = safeDurationSeconds > 0
    ? safeDurationSeconds
    : (safeValues.length * safeBucketSeconds);
  const peakTimestamps = triagePeakTimestamps(peaks, {
    values: safeValues,
    bucketSeconds: safeBucketSeconds,
    durationSeconds: safeDurationSeconds,
  });

  const rightMeta = document.createElement("div");
  rightMeta.className = "timeline-label-right";
  rightMeta.appendChild(detailEl);
  const nav = document.createElement("div");
  nav.className = "timeline-peak-nav";
  const prevBtn = document.createElement("button");
  prevBtn.type = "button";
  prevBtn.className = "timeline-peak-nav-btn";
  prevBtn.textContent = "<";
  prevBtn.title = "Previous high occurrence";
  prevBtn.setAttribute("aria-label", `Previous high ${title.toLowerCase()} occurrence`);
  const nextBtn = document.createElement("button");
  nextBtn.type = "button";
  nextBtn.className = "timeline-peak-nav-btn";
  nextBtn.textContent = ">";
  nextBtn.title = "Next high occurrence";
  nextBtn.setAttribute("aria-label", `Next high ${title.toLowerCase()} occurrence`);
  prevBtn.disabled = peakTimestamps.length === 0;
  nextBtn.disabled = peakTimestamps.length === 0;
  nav.appendChild(prevBtn);
  nav.appendChild(nextBtn);
  rightMeta.appendChild(nav);
  label.appendChild(titleEl);
  label.appendChild(rightMeta);

  const canvas = document.createElement("canvas");
  canvas.className = "timeline-canvas";
  canvas.style.touchAction = "none";
  drawTriageTimeline(canvas, values, peaks, kind, {
    lineTimestamps: peakTimestamps,
    totalSeconds,
  });
  const canvasWrap = document.createElement("div");
  canvasWrap.className = "timeline-canvas-wrap";
  const playheadLayer = document.createElement("div");
  playheadLayer.className = "timeline-playhead-layer";
  playheadLayer.dataset.totalSeconds = String(totalSeconds);
  const playheadLine = document.createElement("div");
  playheadLine.className = "timeline-playhead-line";
  const playheadDot = document.createElement("div");
  playheadDot.className = "timeline-playhead-dot";
  const playheadTooltip = document.createElement("div");
  playheadTooltip.className = "timeline-playhead-tooltip";
  playheadTooltip.textContent = "0:00";
  playheadLayer.appendChild(playheadLine);
  playheadLayer.appendChild(playheadDot);
  playheadLayer.appendChild(playheadTooltip);
  canvasWrap.appendChild(canvas);
  canvasWrap.appendChild(playheadLayer);
  let scrubbing = false;
  let lastSeekSeconds = -1;
  let scrubShouldAutoPlay = false;
  let lastRequestedPeakIndex = -1;

  const timestampFromClientX = (clientX) => {
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !(totalSeconds > 0)) {
      return null;
    }
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    return ratio * totalSeconds;
  };

  const jumpToClientX = (clientX, force = false, autoPlay = false) => {
    const timestampSeconds = timestampFromClientX(clientX);
    if (!Number.isFinite(timestampSeconds)) {
      return;
    }
    const clampedSeconds = Math.max(0, Math.min(totalSeconds, timestampSeconds));
    if (!force && lastSeekSeconds >= 0 && Math.abs(clampedSeconds - lastSeekSeconds) < 0.04) {
      return;
    }
    lastSeekSeconds = clampedSeconds;
    if (peakTimestamps.length) {
      let nearestIndex = 0;
      let nearestDelta = Number.POSITIVE_INFINITY;
      for (let i = 0; i < peakTimestamps.length; i += 1) {
        const delta = Math.abs(Number(peakTimestamps[i]) - clampedSeconds);
        if (delta < nearestDelta) {
          nearestDelta = delta;
          nearestIndex = i;
        }
      }
      lastRequestedPeakIndex = nearestIndex;
    } else {
      lastRequestedPeakIndex = -1;
    }
    playTriageAt(video, clampedSeconds, { autoPlay });
  };

  const getCurrentReferenceTime = () => {
    const activeCaseId = String(state.activeCaseId || "").trim();
    const currentCaseId = String(triagePlayer?.dataset.caseId || "").trim();
    const currentFilename = String(triagePlayer?.dataset.filename || "").trim();
    const rowFilename = String(video?.filename || "").trim();
    if (
      !activeCaseId
      || currentCaseId !== activeCaseId
      || !currentFilename
      || currentFilename !== rowFilename
    ) {
      return 0;
    }
    return Math.max(0, Number(triagePlayer?.currentTime || 0));
  };

  const seekToPeak = (direction) => {
    if (!peakTimestamps.length) {
      return;
    }
    const epsilon = 0.05;
    const now = getCurrentReferenceTime();
    let targetIndex = -1;
    if (direction < 0) {
      for (let i = peakTimestamps.length - 1; i >= 0; i -= 1) {
        if (peakTimestamps[i] < (now - epsilon)) {
          targetIndex = i;
          break;
        }
      }
    } else {
      for (let i = 0; i < peakTimestamps.length; i += 1) {
        if (peakTimestamps[i] > (now + epsilon)) {
          targetIndex = i;
          break;
        }
      }
    }
    if (targetIndex < 0 || targetIndex >= peakTimestamps.length) {
      return;
    }

    // If the player hasn't caught up from the previous jump yet, force a true step.
    const lastTargetStillCurrent = (
      lastRequestedPeakIndex >= 0
      && lastRequestedPeakIndex < peakTimestamps.length
      && Math.abs(now - Number(peakTimestamps[lastRequestedPeakIndex])) <= 0.45
    );
    if (lastTargetStillCurrent && targetIndex === lastRequestedPeakIndex) {
      const candidate = targetIndex + (direction < 0 ? -1 : 1);
      if (candidate >= 0 && candidate < peakTimestamps.length) {
        targetIndex = candidate;
      }
    }

    const target = Number(peakTimestamps[targetIndex]);
    if (!Number.isFinite(target)) {
      return;
    }
    const keepPlaying = isMediaPlayerPlaying(triagePlayer);
    lastRequestedPeakIndex = targetIndex;
    playTriageAt(video, target, { autoPlay: keepPlaying });
  };

  prevBtn.addEventListener("click", () => {
    seekToPeak(-1);
  });
  nextBtn.addEventListener("click", () => {
    seekToPeak(1);
  });

  if (typeof window !== "undefined" && "PointerEvent" in window) {
    const endScrub = (event) => {
      if (!scrubbing) {
        return;
      }
      scrubbing = false;
      if (
        event
        && Number.isFinite(Number(event.pointerId))
        && canvas.hasPointerCapture
        && canvas.hasPointerCapture(event.pointerId)
      ) {
        try {
          canvas.releasePointerCapture(event.pointerId);
        } catch {
          // no-op
        }
      }
    };

    canvas.addEventListener("pointerdown", (event) => {
      if (!(totalSeconds > 0)) {
        return;
      }
      scrubbing = true;
      lastSeekSeconds = -1;
      scrubShouldAutoPlay = isMediaPlayerPlaying(triagePlayer);
      if (canvas.setPointerCapture) {
        try {
          canvas.setPointerCapture(event.pointerId);
        } catch {
          // no-op
        }
      }
      jumpToClientX(event.clientX, true, scrubShouldAutoPlay);
      event.preventDefault();
    });

    canvas.addEventListener("pointermove", (event) => {
      if (!scrubbing) {
        return;
      }
      jumpToClientX(event.clientX, false, scrubShouldAutoPlay);
    });

    canvas.addEventListener("pointerup", endScrub);
    canvas.addEventListener("pointercancel", endScrub);
    canvas.addEventListener("lostpointercapture", () => {
      scrubbing = false;
    });
  } else {
    canvas.addEventListener("click", (event) => {
      if (!(totalSeconds > 0)) {
        return;
      }
      jumpToClientX(event.clientX, true, isMediaPlayerPlaying(triagePlayer));
    });
  }
  row.appendChild(label);
  row.appendChild(canvasWrap);
  return row;
}

function renderTriageList() {
  if (!triageList) {
    return;
  }
  triageList.innerHTML = "";
  if (!state.activeCaseId) {
    triageList.appendChild(createInsightEmptyElement("Select a case first."));
    return;
  }
  const videos = getCaseVideos(state.activeCaseId);
  if (!videos.length) {
    triageList.appendChild(createInsightEmptyElement("No videos available for triage."));
    return;
  }
  const selected = ensureSelectedTriageVideo(state.activeCaseId, videos);
  const sortedVideos = [...videos].sort((a, b) => String(a.filename).localeCompare(String(b.filename)));

  sortedVideos.forEach((video) => {
    const itemButton = document.createElement("button");
    itemButton.type = "button";
    itemButton.className = "triage-video-item";
    if (video.filename === selected) {
      itemButton.classList.add("active");
    }
    itemButton.addEventListener("click", () => {
      void selectTriageVideo(video.filename);
    });

    const thumbUrl = String(video.preview_thumbnail_url || "").trim();
    if (thumbUrl) {
      const image = document.createElement("img");
      image.className = "triage-video-thumb";
      image.loading = "lazy";
      image.src = thumbUrl;
      image.alt = `${video.filename} preview thumbnail`;
      itemButton.appendChild(image);
    } else {
      const placeholder = document.createElement("div");
      placeholder.className = "triage-video-thumb placeholder";
      placeholder.textContent = "No thumbnail";
      itemButton.appendChild(placeholder);
    }

    const meta = document.createElement("div");
    meta.className = "triage-video-meta";
    const title = document.createElement("div");
    title.className = "triage-video-title";
    title.textContent = video.filename;
    const triageKey = makeTriageKey(state.activeCaseId, video.filename);
    const cached = getTriagePayload(state.activeCaseId, video.filename);
    const loading = triageLoading.has(triageKey);
    const sub = document.createElement("div");
    sub.className = "triage-video-sub";
    if (cached) {
      const durationLabel = formatTime(Number(cached.duration_seconds || 0));
      sub.textContent = `Ready | ${durationLabel}`;
    } else if (loading) {
      sub.textContent = "Loading timeline...";
    } else {
      sub.textContent = "Timeline not loaded";
    }
    meta.appendChild(title);
    meta.appendChild(sub);
    itemButton.appendChild(meta);
    triageList.appendChild(itemButton);
  });
}

function renderTriageDetail() {
  if (!triageDetail) {
    return;
  }
  triageDetail.innerHTML = "";
  if (!state.activeCaseId) {
    triageDetail.appendChild(createInsightEmptyElement("Select a case first."));
    return;
  }
  const selectedVideo = getSelectedTriageVideo(state.activeCaseId);
  if (!selectedVideo) {
    triageDetail.appendChild(createInsightEmptyElement("Select a video from the left list."));
    return;
  }
  const triageKey = makeTriageKey(state.activeCaseId, selectedVideo.filename);
  const loading = triageLoading.has(triageKey);
  const error = triageErrors.get(triageKey);
  const cached = getTriagePayload(state.activeCaseId, selectedVideo.filename);

  const header = document.createElement("div");
  header.className = "triage-detail-head";
  const title = document.createElement("h3");
  title.className = "triage-detail-title";
  title.textContent = selectedVideo.filename;
  const sub = document.createElement("div");
  sub.className = "triage-detail-sub";
  if (cached) {
    sub.textContent = `Duration ${formatTime(Number(cached.duration_seconds || 0))} | Buckets ${Number(cached.bucket_count || 0)} | 1s`;
  } else if (loading) {
    sub.textContent = "Building timelines...";
  } else {
    sub.textContent = "Timeline not generated yet.";
  }
  header.appendChild(title);
  header.appendChild(sub);
  triageDetail.appendChild(header);

  const actions = document.createElement("div");
  actions.className = "triage-actions";
  const loadBtn = document.createElement("button");
  loadBtn.type = "button";
  loadBtn.className = "ghost";
  loadBtn.textContent = loading ? "Refreshing..." : (cached ? "Refresh Timelines" : "Generate Timelines");
  loadBtn.disabled = loading;
  loadBtn.addEventListener("click", () => {
    void loadTriageForVideo(state.activeCaseId, selectedVideo.filename, true);
  });
  actions.appendChild(loadBtn);
  triageDetail.appendChild(actions);

  if (!cached) {
    if (error) {
      const err = document.createElement("div");
      err.className = "triage-muted";
      err.textContent = `Failed: ${error}`;
      triageDetail.appendChild(err);
    } else if (!loading) {
      triageDetail.appendChild(createInsightEmptyElement("Generate timelines to view activity and audio intensity."));
    }
    return;
  }

  const activityValues = Array.isArray(cached?.activity_timeline?.values)
    ? cached.activity_timeline.values
    : [];
  const audioValues = Array.isArray(cached?.audio_timeline?.values)
    ? cached.audio_timeline.values
    : [];
  const activityPeaks = Array.isArray(cached?.peaks?.activity) ? cached.peaks.activity : [];
  const audioPeaks = Array.isArray(cached?.peaks?.audio) ? cached.peaks.audio : [];
  const bucketSeconds = Number(cached.bucket_seconds || 1);
  const durationSeconds = Number(cached.duration_seconds || 0);

  triageDetail.appendChild(
    createTriageTimelineRow({
      title: "Activity Intensity",
      values: activityValues,
      peaks: activityPeaks,
      kind: "activity",
      video: selectedVideo,
      bucketSeconds,
      durationSeconds,
    }),
  );

  triageDetail.appendChild(
    createTriageTimelineRow({
      title: "Audio Intensity",
      values: audioValues,
      peaks: audioPeaks,
      kind: "audio",
      video: selectedVideo,
      bucketSeconds,
      durationSeconds,
    }),
  );

  const audioInfo = String(cached?.audio_timeline?.status || "ok");
  if (audioInfo !== "ok") {
    const note = document.createElement("div");
    note.className = "triage-muted";
    note.textContent = `Audio timeline unavailable: ${String(cached?.audio_timeline?.message || "no audio stream")}`;
    triageDetail.appendChild(note);
  }
  if (!cached?.analysis_available?.face_people || !cached?.analysis_available?.vehicles) {
    const note = document.createElement("div");
    note.className = "triage-muted";
    note.textContent = "Tip: run Face & People / Vehicle analysis to improve activity timeline signal.";
    triageDetail.appendChild(note);
  }
  updateTriageTimelinePlayheads();
}

function renderTriagePanels() {
  renderTriageList();
  renderTriageDetail();
}

async function selectTriageVideo(filename) {
  if (!state.activeCaseId) {
    return;
  }
  const videos = getCaseVideos(state.activeCaseId);
  const target = String(filename || "").trim();
  const selectedVideo = videos.find((item) => item && item.filename === target);
  if (!selectedVideo) {
    return;
  }
  triageSelection.set(state.activeCaseId, target);
  const videoUrl = String(selectedVideo.video_url || "");
  if (videoUrl && triagePlayer && triagePlayerMeta) {
    playInPlayer(
      triagePlayer,
      triagePlayerMeta,
      selectedVideo.filename,
      videoUrl,
      0,
      { autoPlay: false },
    );
    // Keep the main player in sync so hidden/background audio from the
    // previously selected triage video is stopped immediately.
    playVideoAt(
      selectedVideo.filename,
      videoUrl,
      0,
      { autoPlay: false },
    );
    updateTriageTimelinePlayheads(0);
  }
  renderTriagePanels();
  await loadTriageForVideo(state.activeCaseId, target, false);
}

async function loadTriageForVideo(caseId, filename, force = false) {
  const normalizedCaseId = String(caseId || "").trim();
  const normalizedFilename = String(filename || "").trim();
  if (!normalizedCaseId || !normalizedFilename) {
    return null;
  }
  const key = makeTriageKey(normalizedCaseId, normalizedFilename);
  if (triageLoading.has(key)) {
    return getTriagePayload(normalizedCaseId, normalizedFilename);
  }
  if (!force) {
    const cached = getTriagePayload(normalizedCaseId, normalizedFilename);
    if (cached) {
      return cached;
    }
  }

  triageLoading.add(key);
  if (normalizedCaseId === state.activeCaseId) {
    renderTriagePanels();
  }
  try {
    const payload = await fetchJson("/triage_timeline", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        case_id: normalizedCaseId,
        filename: normalizedFilename,
        bucket_seconds: 1.0,
        force: Boolean(force),
      }),
    });
    setTriagePayload(normalizedCaseId, normalizedFilename, payload);
    triageErrors.delete(key);
    return payload;
  } catch (error) {
    triageErrors.set(key, formatError(error));
    return null;
  } finally {
    triageLoading.delete(key);
    if (normalizedCaseId === state.activeCaseId) {
      renderTriagePanels();
    }
  }
}

async function refreshTriageList(force = false) {
  if (!state.activeCaseId) {
    renderTriagePanels();
    setTriageStatus("", "");
    return;
  }
  const caseId = state.activeCaseId;
  const videos = getCaseVideos(caseId);
  const selected = ensureSelectedTriageVideo(caseId, videos);
  renderTriagePanels();
  if (!videos.length) {
    setTriageStatus("No videos to triage in this case.", "ok");
    return;
  }
  if (!selected) {
    setTriageStatus("Select a video to build timelines.", "ok");
    return;
  }
  const selectedVideo = videos.find((item) => item && item.filename === selected) || null;
  if (selectedVideo && triagePlayer && triagePlayerMeta) {
    const selectedUrl = String(selectedVideo.video_url || "");
    const currentFilename = String(triagePlayer.dataset.filename || "").trim();
    const hasSource = Boolean(String(triagePlayer.getAttribute("src") || "").trim());
    if (selectedUrl && (currentFilename !== selectedVideo.filename || !hasSource)) {
      playInPlayer(
        triagePlayer,
        triagePlayerMeta,
        selectedVideo.filename,
        selectedUrl,
        0,
        { autoPlay: false },
      );
      // Also reset/sync the shared main player to avoid stale background audio.
      playVideoAt(
        selectedVideo.filename,
        selectedUrl,
        0,
        { autoPlay: false },
      );
      updateTriageTimelinePlayheads(0);
    }
  }
  const refreshToken = ++triageRefreshToken;
  setTriageStatus(`Building triage timelines for ${selected}...`, "working");
  const payload = await loadTriageForVideo(caseId, selected, force);
  if (refreshToken !== triageRefreshToken || caseId !== state.activeCaseId) {
    return;
  }
  if (!payload) {
    setTriageStatus(`Failed to build timelines for ${selected}.`, "error");
    return;
  }
  setTriageStatus(`Triage ready for ${selected}.`, "ok");
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
    // Stop old audio immediately before switching sources.
    player.pause();
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
  renderTriagePanels();
  if (resolvedCaseId === state.activeCaseId) {
    renderAnalysisSelectionLists();
    await refreshAnalysisWalls();
    if (state.activeMainTab === "triage") {
      await refreshTriageList(false);
    }
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
  stopBackgroundIndexPolling();
  state.activeCaseId = nextCaseId;
  setWorkspaceView("analysis");
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
    const indexStatus = await syncBackgroundIndexStatus(nextCaseId);
    const backgroundRunning = isBackgroundIndexRunning(indexStatus);
    if (state.activeMainTab === "triage") {
      setTriageStatus(`Case ${nextCaseId}: triage timelines ready.`, "ok");
    }
    setAnalysisStatus("Face & People tab: select videos to run analysis.", "ok");
    setVehicleStatus("Vehicle tab: select videos to run analysis.", "ok");
    if (!backgroundRunning) {
      setStatus(`Case ${nextCaseId} ready.`, "ok");
    }
  } catch (error) {
    if (switchVersion !== caseSwitchVersion || state.activeCaseId !== nextCaseId) {
      return;
    }
    setTriageStatus(`Case switch failed: ${formatError(error)}`, "error");
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
    const caseTriageCache = ensureCaseTriageCache(caseId);
    caseTriageCache?.delete(safeFilename);
    triageErrors.delete(makeTriageKey(caseId, safeFilename));
    restoreSearchForCase(caseId);
    clearCaseTriageCache(caseId);
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
    const deletingActiveCase = state.activeCaseId === targetCaseId;
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
    clearCaseTriageCache(targetCaseId);
    backgroundIndexTerminalSeen.delete(targetCaseId);
    markCaseStateChanged();
    renderCaseList();

    if (!state.cases.length) {
      state.activeCaseId = null;
      stopBackgroundIndexPolling();
      hideTaskProgressUi();
      clearResults();
      renderVideoList([]);
      resetPlayerForCase(null);
      resetAuxPlayers(null);
      setCaseUrl(null);
      syncWorkspaceVisibility();
      setTriageStatus("", "");
      setAnalysisStatus("", "");
      setStatus(`Deleted case ${targetCaseId}. No cases remaining.`, "ok");
      return;
    }

    if (deletingActiveCase) {
      backToCaseRepository();
      setStatus(`Deleted case ${targetCaseId}. Select another case from repository.`, "ok");
      return;
    }

    syncWorkspaceVisibility();
    setStatus(`Deleted case ${targetCaseId}.`, "ok");
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

  const selectedSourceIndices = getSelectedPendingUploadSourceIndices(files);
  const selectedForIndexCount = selectedSourceIndices.size;

  try {
    uploadFlowActive = true;
    stopBackgroundIndexPolling();
    const caseId = ensureActiveCaseId();
    const engineLabel = getLoadedEmbeddingEngineLabel();
    const totalUploadBytes = files.reduce((sum, file) => sum + Number(file.size || 0), 0);
    const uploadStartedAt = Date.now();
    setStatus(
      `Transferring videos to ${caseId} (engine: ${engineLabel}) | semantic index selected: ${selectedForIndexCount}/${files.length}.`,
      "working",
    );
    setTaskProgressUi(
      "Transferring files to server",
      0,
      `${files.length} file(s) | ${formatBytes(totalUploadBytes)}`,
    );
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    const TRANSFER_STAGE_MAX = 70;
    const SERVER_PROCESSING_STAGE = 80;
    const SERVER_RECEIVED_STAGE = 90;
    const INDEX_QUEUE_STAGE = 95;

    const uploadResult = await postFormDataWithProgress(
      withCaseQuery("/upload", caseId),
      formData,
      (event) => {
        const elapsedSec = Math.max(0.001, (Date.now() - uploadStartedAt) / 1000);
        const estimatedTotal = event.lengthComputable && event.total > 0
          ? event.total
          : totalUploadBytes;
        const totalBytesForDisplay = Math.max(0, Number(estimatedTotal || totalUploadBytes || event.loaded || 0));
        const loadedBytes = Math.min(Number(event.loaded || 0), totalBytesForDisplay || Number(event.loaded || 0));
        const fraction = estimatedTotal > 0 ? loadedBytes / estimatedTotal : 0;
        const transferFraction = Math.max(0, Math.min(1, fraction));
        const speedBytesPerSecond = loadedBytes / elapsedSec;
        const remainingBytes = Math.max(0, totalBytesForDisplay - loadedBytes);
        const etaSeconds = speedBytesPerSecond > 0 ? remainingBytes / speedBytesPerSecond : null;
        const uploadSent = totalBytesForDisplay > 0 && loadedBytes >= totalBytesForDisplay;
        const metaParts = [];
        if (uploadSent) {
          metaParts.push(`${formatBytes(totalBytesForDisplay)} sent from browser`);
          metaParts.push(
            "Browser upload finished; server is still receiving/writing/converting (files may not appear in /videos yet)",
          );
          setTaskProgressUi(
            "Server ingest + conversion in progress",
            SERVER_PROCESSING_STAGE,
            metaParts.join(" | "),
          );
          return;
        } else {
          metaParts.push(`${formatBytes(loadedBytes)} / ${formatBytes(totalBytesForDisplay)} transferred`);
          metaParts.push(`${formatBytes(speedBytesPerSecond)}/s`);
          metaParts.push(formatEtaLabel(etaSeconds));
        }
        const meta = metaParts.join(" | ");
        setTaskProgressUi(
          "Transferring files to server",
          clampPercent((transferFraction * TRANSFER_STAGE_MAX)),
          meta,
        );
      },
    );

    setTaskProgressUi(
      "Upload received by server",
      SERVER_RECEIVED_STAGE,
      "Server finished ingest/transcode. Preparing background indexing...",
    );

    const uploaded = uploadResult.uploaded || [];
    const errors = uploadResult.errors || [];
    const transcoded = uploadResult.transcoded || [];
    const selectedIndexTargets = resolveSelectedSemanticIndexTargets(
      uploadResult,
      selectedSourceIndices,
      files,
    );

    if (uploaded.length) {
      clearCaseTriageCache(caseId);
    }
    videoInput.value = "";
    clearPendingUploadItems();
    await refreshVideos(caseId);

    const allErrors = [...errors];
    let backgroundMessage = "No new videos queued for indexing.";
    if (uploaded.length > 0 && selectedIndexTargets.length > 0) {
      setTaskProgressUi(
        "Queueing semantic indexing",
        INDEX_QUEUE_STAGE,
        `Preparing ${selectedIndexTargets.length} selected uploaded video(s) for background indexing...`,
      );
      try {
        const startPayload = await fetchJson("/index/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            case_id: caseId,
            filenames: selectedIndexTargets,
            frame_interval_seconds: frameInterval,
            batch_size: 32,
            force: false,
          }),
        });
        const started = Boolean(startPayload?.started);
        if (started) {
          backgroundMessage = `Background semantic indexing started for ${selectedIndexTargets.length} selected video(s).`;
        } else {
          backgroundMessage = String(startPayload?.message || "Background indexing already running.");
        }
        startBackgroundIndexPolling(caseId);
      } catch (error) {
        allErrors.push(`index start: ${formatError(error)}`);
        backgroundMessage = "Upload finished, but background indexing failed to start.";
      }
    } else if (uploaded.length > 0) {
      backgroundMessage = "Upload finished. No videos were selected for semantic indexing.";
    }

    const summary = `Case ${caseId}: uploaded ${uploaded.length}, transcoded ${transcoded.length}, selected for semantic indexing ${selectedIndexTargets.length}, engine ${engineLabel}. ${backgroundMessage}`;
    const errorNote = allErrors.length ? ` Errors: ${allErrors.join(" | ")}` : "";
    setStatus(`${summary}${errorNote}`, allErrors.length ? "error" : "ok");
    const progressMeta = uploaded.length > 0
      ? backgroundMessage
      : "No new videos were uploaded. You can continue triage immediately.";
    completeTaskProgressUi(
      allErrors.length ? "Upload completed with warnings" : "Upload completed",
      progressMeta,
    );
    uploadFlowActive = false;
    await syncBackgroundIndexStatus(caseId);
  } catch (error) {
    setStatus(`Upload/index failed: ${formatError(error)}`, "error");
    setTaskProgressUi(
      "Upload/index failed",
      100,
      formatError(error),
    );
  } finally {
    uploadFlowActive = false;
  }
}

async function runExistingSemanticIndex() {
  let caseId;
  try {
    caseId = ensureActiveCaseId();
  } catch (error) {
    setStatus(formatError(error), "error");
    return;
  }

  const filenames = getSelectedExistingIndexFilenames();
  if (!filenames.length) {
    setStatus("Select one or more uploaded videos to index first.", "error");
    return;
  }

  const frameInterval = Number.parseFloat(intervalInput?.value || "1");
  const safeFrameInterval = Number.isFinite(frameInterval) && frameInterval > 0
    ? frameInterval
    : 1;

  const confirmed = window.confirm(
    `Run semantic indexing for ${filenames.length} selected uploaded video(s)?`,
  );
  if (!confirmed) {
    return;
  }

  try {
    stopBackgroundIndexPolling();
    setStatus(
      `Queueing semantic indexing for ${filenames.length} selected uploaded video(s)...`,
      "working",
    );
    setTaskProgressUi(
      "Queueing semantic indexing",
      95,
      `Preparing ${filenames.length} existing selected video(s) for background indexing...`,
    );

    const startPayload = await fetchJson("/index/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        case_id: caseId,
        filenames,
        frame_interval_seconds: safeFrameInterval,
        batch_size: 32,
        force: false,
      }),
    });

    const started = Boolean(startPayload?.started);
    if (started) {
      setStatus(
        `Background semantic indexing started for ${filenames.length} selected uploaded video(s).`,
        "working",
      );
    } else {
      const message = String(startPayload?.message || "Background indexing already running.");
      setStatus(message, "ok");
    }

    startBackgroundIndexPolling(caseId);
    await syncBackgroundIndexStatus(caseId);
  } catch (error) {
    setStatus(`Failed to start semantic indexing: ${formatError(error)}`, "error");
    setTaskProgressUi(
      "Queueing semantic indexing failed",
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
    const frameInterval = Number.parseFloat(intervalInput?.value || "1");
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
    setSemanticSearchMeta("Type a search query first.", "error");
    return;
  }

  const topK = normalizeTopK(topKInput?.value || "10", 10);
  topKInput.value = String(topK);

  try {
    const caseId = ensureActiveCaseId();
    setStatus(`Searching in ${caseId}...`, "working");
    setSemanticSearchMeta("Analyzing query intent...", "working");
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
    const fallbackUsed = Boolean(payload.fallback_used);
    const searchTypeLabel = intent || "unknown";
    const modeLabel = mode || "unknown";
    const fallbackLabel = fallbackUsed ? "yes" : "no";
    const engineMeta = engineLabel ? ` | Engine: ${engineLabel}` : "";
    setSemanticSearchMeta(
      `Search Type: ${searchTypeLabel} | Mode: ${modeLabel} | Fallback: ${fallbackLabel}${engineMeta}`,
      "ok",
    );
  } catch (error) {
    setStatus(`Search failed: ${formatError(error)}`, "error");
    setSemanticSearchMeta(`Search failed: ${formatError(error)}`, "error");
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
    state.caseVideos.set(String(newCaseId), []);
    markCaseStateChanged();
    renderCaseList();
    syncWorkspaceVisibility();
    setStatus(`Created case ${newCaseId}. Open it from Case Repository.`, "ok");
  } catch (error) {
    setTriageStatus(`Create case failed: ${formatError(error)}`, "error");
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
  workspaceBackBtn?.addEventListener("click", () => {
    backToCaseRepository();
  });
  workspaceAnalysisBtn?.addEventListener("click", () => {
    if (!state.activeCaseId) {
      setStatus("Select a case from Case Repository first.", "error");
      return;
    }
    setWorkspaceView("analysis");
  });
  workspaceReportBtn?.addEventListener("click", () => {
    if (!state.activeCaseId) {
      setStatus("Select a case from Case Repository first.", "error");
      return;
    }
    setWorkspaceView("report");
  });
  workspaceSettingsBtn?.addEventListener("click", () => {
    if (!state.activeCaseId) {
      setStatus("Select a case from Case Repository first.", "error");
      return;
    }
    setWorkspaceView("settings");
  });
  workspaceExitBtn?.addEventListener("click", () => {
    requestGracefulExit();
  });

  uploadBtn?.addEventListener("click", uploadAndIndex);
  videoInput?.addEventListener("change", () => {
    refreshPendingUploadItemsFromInput();
  });
  preUploadSelectAll?.addEventListener("change", () => {
    setAllPendingUploadSelection(Boolean(preUploadSelectAll.checked));
  });
  existingIndexSelectAll?.addEventListener("change", () => {
    setAllExistingIndexSelection(Boolean(existingIndexSelectAll.checked));
  });
  runExistingIndexBtn?.addEventListener("click", () => {
    runExistingSemanticIndex();
  });
  saveEmbeddingSettingsBtn?.addEventListener("click", () => {
    saveEmbeddingSettings();
  });
  runFacePeopleSelectedBtn?.addEventListener("click", () => {
    runSelectedAnalysisForCategory("face_people");
  });
  runVehiclesSelectedBtn?.addEventListener("click", () => {
    runSelectedAnalysisForCategory("vehicles");
  });
  mainTabTriageBtn?.addEventListener("click", async () => {
    setActiveMainTab("triage");
    await refreshTriageList(false);
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
      const activeCaseId = ensureActiveCaseId();
      await refreshVideos(activeCaseId);
      const indexStatus = await syncBackgroundIndexStatus(activeCaseId);
      if (!isBackgroundIndexRunning(indexStatus)) {
        setStatus("Video list refreshed.", "ok");
      }
    } catch (error) {
      setStatus(`Refresh failed: ${formatError(error)}`, "error");
    }
  });
  refreshTriageBtn?.addEventListener("click", async () => {
    try {
      await refreshTriageList(true);
    } catch (error) {
      setTriageStatus(`Triage refresh failed: ${formatError(error)}`, "error");
    }
  });
  triagePlayer?.addEventListener("timeupdate", () => {
    updateTriageTimelinePlayheads();
  });
  triagePlayer?.addEventListener("seeking", () => {
    updateTriageTimelinePlayheads();
  });
  triagePlayer?.addEventListener("seeked", () => {
    updateTriageTimelinePlayheads();
  });
  triagePlayer?.addEventListener("loadedmetadata", () => {
    updateTriageTimelinePlayheads();
  });
  window.addEventListener("resize", () => {
    updateTriageTimelinePlayheads();
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
  setActiveMainTab("triage");
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
      setTriageStatus("", "");
      setAnalysisStatus("", "");
      setVehicleStatus("", "");
      setStatus("No cases yet. Click + New Case to begin.", "ok");
      return;
    }

    state.activeCaseId = null;
    resetPlayerForCase(null);
    resetAuxPlayers(null);
    setCaseUrl(null);
    syncWorkspaceVisibility();
    await restorePlaybackFromUrl();
    if (state.activeCaseId) {
      await refreshTriageList(false);
      setStatus("Ready.", "ok");
    } else {
      setStatus("Select a case from Case Repository to open workspace tabs.", "ok");
    }
  } catch (error) {
    setTriageStatus(`Startup failed: ${formatError(error)}`, "error");
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
