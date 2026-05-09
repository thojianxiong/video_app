let videoInput = null;
let intervalInput = null;
let uploadBtn = null;
let refreshBtn = null;
let refreshTriageBtn = null;
let uploadStatus = null;
let indexQueueSummaryBtn = null;
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
let taskProgressStopBtn = null;
let videoBulkActions = null;
let videoSelectAll = null;
let deleteSelectedVideosBtn = null;
let videoSelectionMeta = null;
let triageStatus = null;
let triageList = null;
let triageDetail = null;
let videoList = null;
let embeddingProfileSelect = null;
let embeddingDeviceSelect = null;
let saveEmbeddingSettingsBtn = null;
let embeddingSettingsMeta = null;
let analysisStatus = null;
let facePeopleQueueSummaryBtn = null;
let runFacePeopleSelectedBtn = null;
let runVehiclesSelectedBtn = null;
let vehicleQueueSummaryBtn = null;
let mainTabTriageBtn = null;
let mainTabSemanticBtn = null;
let mainTabFacePeopleBtn = null;
let mainTabVehiclesBtn = null;
let workspaceBackBtn = null;
let workspaceAnalysisBtn = null;
let workspaceReportBtn = null;
let workspaceQueueBtn = null;
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
let suspectProbeInput = null;
let suspectModeSelect = null;
let suspectSearchBtn = null;
let suspectStatus = null;
let suspectWall = null;
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
let queueTaskPopup = null;
let queueTaskPopupBackdrop = null;
let queueTaskPopupCloseBtn = null;
let queueTaskPopupTitle = null;
let queueTaskPopupMeta = null;
let queueTaskPopupFiles = null;
let queueTaskPopupRecovery = null;
let queueTaskPopupSelectAll = null;
let queueTaskPopupRestartBtn = null;
let queueTaskPopupCancelBtn = null;
let queueTaskPopupRemoveFilesBtn = null;
let queueTaskPopupDeleteBtn = null;
let queueTaskPopupSelectionMeta = null;
let queueTaskPopupRecoveryStatus = null;
let queryInput = null;
let scoreThresholdInput = null;
let scoreThresholdValue = null;
let searchBtn = null;
let semanticSearchMeta = null;
let searchThresholdSettingInput = null;
let searchDedupeAggressivenessInput = null;
let searchDedupeAggressivenessValue = null;
let searchResultLimitInput = null;
let saveSearchSettingsBtn = null;
let searchSettingsMeta = null;
let searchSettingsHint = null;
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
let workspaceQueuePage = null;
let reportQueueRefreshBtn = null;
let reportQueueStatus = null;
let reportQueueList = null;
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
  searchSettings: null,
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
const videoSelectionByCase = new Map();
let pendingUploadItems = [];
let triageRefreshToken = 0;
let indexStatusPollToken = 0;
let indexStatusPollCaseId = "";
const ANALYSIS_CATEGORIES = ["face_people", "vehicles"];
const analysisStatusPollStateByCategory = {
  face_people: { token: 0, caseId: "", jobId: 0 },
  vehicles: { token: 0, caseId: "", jobId: 0 },
};
let uploadFlowActive = false;
let stopBackgroundIndexInFlight = false;
let taskProgressStopCaseId = "";
const backgroundIndexTerminalSeen = new Map();
const backgroundIndexStatusByCase = new Map();
let reportQueuePollToken = 0;
let queueTaskPopupLoadToken = 0;
let queueTaskPopupRecoveryContext = null;
let queueTaskPopupCurrentItem = null;
const analysisQueueStatusByCase = {
  face_people: new Map(),
  vehicles: new Map(),
};
const SIDEBAR_MIN_WIDTH = 220;
const SIDEBAR_MAX_WIDTH = 560;
const RESUMABLE_UPLOAD_STATE_KEY = "visiox_resumable_upload_v1";
const DEFAULT_RESUMABLE_CHUNK_SIZE_BYTES = 8 * 1024 * 1024;
const RESUMABLE_UPLOAD_CHUNK_RETRIES = 3;
const RESUMABLE_UPLOAD_RETRY_DELAY_MS = 350;
const DUPLICATE_FINGERPRINT_SAMPLE_BYTES = 1024 * 1024;
const duplicateFingerprintPromiseCache = new WeakMap();

function bindDomElements() {
  videoInput = document.getElementById("videoInput");
  intervalInput = document.getElementById("intervalInput");
  uploadBtn = document.getElementById("uploadBtn");
  refreshBtn = document.getElementById("refreshBtn");
  refreshTriageBtn = document.getElementById("refreshTriageBtn");
  uploadStatus = document.getElementById("uploadStatus");
  indexQueueSummaryBtn = document.getElementById("indexQueueSummaryBtn");
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
  taskProgressStopBtn = document.getElementById("taskProgressStopBtn");
  videoBulkActions = document.getElementById("videoBulkActions");
  videoSelectAll = document.getElementById("videoSelectAll");
  deleteSelectedVideosBtn = document.getElementById("deleteSelectedVideosBtn");
  videoSelectionMeta = document.getElementById("videoSelectionMeta");
  triageStatus = document.getElementById("triageStatus");
  triageList = document.getElementById("triageList");
  triageDetail = document.getElementById("triageDetail");
  videoList = document.getElementById("videoList");
  embeddingProfileSelect = document.getElementById("embeddingProfileSelect");
  embeddingDeviceSelect = document.getElementById("embeddingDeviceSelect");
  saveEmbeddingSettingsBtn = document.getElementById("saveEmbeddingSettingsBtn");
  embeddingSettingsMeta = document.getElementById("embeddingSettingsMeta");
  analysisStatus = document.getElementById("analysisStatus");
  facePeopleQueueSummaryBtn = document.getElementById("facePeopleQueueSummaryBtn");
  runFacePeopleSelectedBtn = document.getElementById("runFacePeopleSelectedBtn");
  runVehiclesSelectedBtn = document.getElementById("runVehiclesSelectedBtn");
  vehicleQueueSummaryBtn = document.getElementById("vehicleQueueSummaryBtn");
  mainTabTriageBtn = document.getElementById("mainTabTriageBtn");
  mainTabSemanticBtn = document.getElementById("mainTabSemanticBtn");
  mainTabFacePeopleBtn = document.getElementById("mainTabFacePeopleBtn");
  mainTabVehiclesBtn = document.getElementById("mainTabVehiclesBtn");
  workspaceBackBtn = document.getElementById("workspaceBackBtn");
  workspaceAnalysisBtn = document.getElementById("workspaceAnalysisBtn");
  workspaceReportBtn = document.getElementById("workspaceReportBtn");
  workspaceQueueBtn = document.getElementById("workspaceQueueBtn");
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
  suspectProbeInput = document.getElementById("suspectProbeInput");
  suspectModeSelect = document.getElementById("suspectModeSelect");
  suspectSearchBtn = document.getElementById("suspectSearchBtn");
  suspectStatus = document.getElementById("suspectStatus");
  suspectWall = document.getElementById("suspectWall");
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
  queueTaskPopup = document.getElementById("queueTaskPopup");
  queueTaskPopupBackdrop = document.getElementById("queueTaskPopupBackdrop");
  queueTaskPopupCloseBtn = document.getElementById("queueTaskPopupCloseBtn");
  queueTaskPopupTitle = document.getElementById("queueTaskPopupTitle");
  queueTaskPopupMeta = document.getElementById("queueTaskPopupMeta");
  queueTaskPopupFiles = document.getElementById("queueTaskPopupFiles");
  queueTaskPopupRecovery = document.getElementById("queueTaskPopupRecovery");
  queueTaskPopupSelectAll = document.getElementById("queueTaskPopupSelectAll");
  queueTaskPopupRestartBtn = document.getElementById("queueTaskPopupRestartBtn");
  queueTaskPopupCancelBtn = document.getElementById("queueTaskPopupCancelBtn");
  queueTaskPopupRemoveFilesBtn = document.getElementById("queueTaskPopupRemoveFilesBtn");
  queueTaskPopupDeleteBtn = document.getElementById("queueTaskPopupDeleteBtn");
  queueTaskPopupSelectionMeta = document.getElementById("queueTaskPopupSelectionMeta");
  queueTaskPopupRecoveryStatus = document.getElementById("queueTaskPopupRecoveryStatus");
  queryInput = document.getElementById("queryInput");
  scoreThresholdInput = document.getElementById("scoreThresholdInput");
  scoreThresholdValue = document.getElementById("scoreThresholdValue");
  searchBtn = document.getElementById("searchBtn");
  semanticSearchMeta = document.getElementById("semanticSearchMeta");
  searchThresholdSettingInput = document.getElementById("searchThresholdSettingInput");
  searchDedupeAggressivenessInput = document.getElementById("searchDedupeAggressivenessInput");
  searchDedupeAggressivenessValue = document.getElementById("searchDedupeAggressivenessValue");
  searchResultLimitInput = document.getElementById("searchResultLimitInput");
  saveSearchSettingsBtn = document.getElementById("saveSearchSettingsBtn");
  searchSettingsMeta = document.getElementById("searchSettingsMeta");
  searchSettingsHint = document.getElementById("searchSettingsHint");
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
  workspaceQueuePage = document.getElementById("workspaceQueuePage");
  reportQueueRefreshBtn = document.getElementById("reportQueueRefreshBtn");
  reportQueueStatus = document.getElementById("reportQueueStatus");
  reportQueueList = document.getElementById("reportQueueList");
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

function setSuspectStatus(message, kind = "") {
  if (!suspectStatus) {
    return;
  }
  suspectStatus.textContent = message;
  suspectStatus.className = `status ${kind}`.trim();
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

function setSearchSettingsStatus(message, kind = "") {
  if (!searchSettingsMeta) {
    return;
  }
  searchSettingsMeta.textContent = String(message || "");
  searchSettingsMeta.className = `status ${kind}`.trim();
}

function setReportQueueStatus(message, kind = "") {
  if (!reportQueueStatus) {
    return;
  }
  reportQueueStatus.textContent = String(message || "");
  reportQueueStatus.className = `status ${kind}`.trim();
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

function isExactNotFoundError(error) {
  const message = String(formatError(error) || "").trim();
  return message === "[404] Not Found";
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

function normalizeDuplicateName(name) {
  return String(name || "").trim().toLowerCase();
}

function normalizeDuplicateFingerprint(fingerprint) {
  return String(fingerprint || "").trim().toLowerCase();
}

function getExistingUploadedFingerprintSet(caseId = null) {
  const activeCaseId = String(caseId || state.activeCaseId || "").trim();
  if (!activeCaseId) {
    return new Set();
  }
  const videos = getCaseVideos(activeCaseId);
  const existingFingerprints = new Set();

  videos.forEach((video) => {
    if (!video || typeof video !== "object") {
      return;
    }
    const contract = video.media_contract && typeof video.media_contract === "object"
      ? video.media_contract
      : null;
    const identity = contract && typeof contract.identity === "object"
      ? contract.identity
      : null;
    const normalizedFingerprint = normalizeDuplicateFingerprint(
      identity?.source_file_fingerprint_sha256 || "",
    );
    if (normalizedFingerprint) {
      existingFingerprints.add(normalizedFingerprint);
    }
  });

  return existingFingerprints;
}

function bytesToHex(bytes) {
  return Array.from(bytes || [])
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function concatUint8Arrays(arrays) {
  const list = Array.isArray(arrays) ? arrays : [];
  const totalBytes = list.reduce(
    (sum, entry) => sum + (entry instanceof Uint8Array ? entry.byteLength : 0),
    0,
  );
  const merged = new Uint8Array(totalBytes);
  let offset = 0;
  list.forEach((entry) => {
    if (!(entry instanceof Uint8Array) || !entry.byteLength) {
      return;
    }
    merged.set(entry, offset);
    offset += entry.byteLength;
  });
  return merged;
}

async function computeDuplicateFileFingerprint(file) {
  if (!(file instanceof Blob)) {
    return "";
  }
  if (
    typeof crypto === "undefined"
    || !crypto.subtle
    || typeof TextEncoder === "undefined"
  ) {
    return "";
  }

  const cachedPromise = duplicateFingerprintPromiseCache.get(file);
  if (cachedPromise) {
    return cachedPromise;
  }

  const fingerprintPromise = (async () => {
    try {
      const encoder = new TextEncoder();
      const fileSize = Math.max(0, Number(file.size || 0));
      const sampleSize = Math.max(4096, DUPLICATE_FINGERPRINT_SAMPLE_BYTES);
      const parts = [encoder.encode(`size:${fileSize};`)];

      const headEnd = Math.min(fileSize, sampleSize);
      const headBuffer = await file.slice(0, headEnd).arrayBuffer();
      if (headBuffer.byteLength > 0) {
        parts.push(encoder.encode("head:"));
        parts.push(new Uint8Array(headBuffer));
      }

      if (fileSize > sampleSize * 2) {
        const middleStart = Math.max(0, Math.floor(fileSize / 2) - Math.floor(sampleSize / 2));
        const middleEnd = Math.min(fileSize, middleStart + sampleSize);
        const middleBuffer = await file.slice(middleStart, middleEnd).arrayBuffer();
        if (middleBuffer.byteLength > 0) {
          parts.push(encoder.encode(";middle:"));
          parts.push(new Uint8Array(middleBuffer));
        }
      }

      if (fileSize > sampleSize) {
        const tailStart = Math.max(0, fileSize - sampleSize);
        const tailBuffer = await file.slice(tailStart, fileSize).arrayBuffer();
        if (tailBuffer.byteLength > 0) {
          parts.push(encoder.encode(";tail:"));
          parts.push(new Uint8Array(tailBuffer));
        }
      }

      const fingerprintBytes = concatUint8Arrays(parts);
      const digest = await crypto.subtle.digest("SHA-256", fingerprintBytes);
      return bytesToHex(new Uint8Array(digest));
    } catch (error) {
      console.warn(
        "Duplicate fingerprint computation failed:",
        String(file?.name || ""),
        error,
      );
      return "";
    }
  })();

  duplicateFingerprintPromiseCache.set(file, fingerprintPromise);
  return fingerprintPromise;
}

function getExistingUploadedNameSet(caseId = null) {
  const activeCaseId = String(caseId || state.activeCaseId || "").trim();
  if (!activeCaseId) {
    return new Set();
  }
  const videos = getCaseVideos(activeCaseId);
  const existingNames = new Set();

  videos.forEach((video) => {
    if (!video || typeof video !== "object") {
      return;
    }
    const contract = video.media_contract && typeof video.media_contract === "object"
      ? video.media_contract
      : null;
    const identity = contract && typeof contract.identity === "object"
      ? contract.identity
      : null;

    const sourceName = normalizeDuplicateName(identity?.source_filename || "");
    const storedName = normalizeDuplicateName(identity?.stored_filename || video.filename || "");
    const listedName = normalizeDuplicateName(video.filename || "");

    if (sourceName) {
      existingNames.add(sourceName);
    }
    if (storedName) {
      existingNames.add(storedName);
    }
    if (listedName) {
      existingNames.add(listedName);
    }
  });

  return existingNames;
}

function detectDuplicateUploadCandidates(files, caseId = null) {
  const existingNames = getExistingUploadedNameSet(caseId);
  if (!existingNames.size) {
    return [];
  }
  const list = Array.isArray(files) ? files : [];
  const duplicates = [];
  list.forEach((file, sourceIndex) => {
    const fileName = String(file?.name || "").trim();
    const normalized = normalizeDuplicateName(fileName);
    if (!fileName || !normalized) {
      return;
    }
    if (existingNames.has(normalized)) {
      duplicates.push({
        sourceIndex: Number(sourceIndex),
        name: fileName,
      });
    }
  });
  return duplicates;
}

async function detectDuplicateUploadCandidatesWithHash(files, caseId = null) {
  const existingNames = getExistingUploadedNameSet(caseId);
  const existingFingerprints = getExistingUploadedFingerprintSet(caseId);
  if (!existingNames.size && !existingFingerprints.size) {
    return [];
  }

  const list = Array.isArray(files) ? files : [];
  const duplicates = [];

  for (let sourceIndex = 0; sourceIndex < list.length; sourceIndex += 1) {
    const file = list[sourceIndex];
    const fileName = String(file?.name || "").trim();
    const normalizedName = normalizeDuplicateName(fileName);
    if (!fileName) {
      continue;
    }

    let matchType = "";
    if (existingFingerprints.size > 0) {
      const fingerprint = normalizeDuplicateFingerprint(
        await computeDuplicateFileFingerprint(file),
      );
      if (fingerprint && existingFingerprints.has(fingerprint)) {
        matchType = "fingerprint";
      }
    }

    if (!matchType && normalizedName && existingNames.has(normalizedName)) {
      matchType = "name";
    }

    if (matchType) {
      duplicates.push({
        sourceIndex: Number(sourceIndex),
        name: fileName,
        matchType,
      });
    }
  }

  return duplicates;
}

function reviewDuplicateUploadCandidates(duplicateCandidates, files) {
  const candidates = Array.isArray(duplicateCandidates) ? duplicateCandidates : [];
  const allFiles = Array.isArray(files) ? files : [];
  const skippedSourceIndices = new Set();
  if (!candidates.length || !allFiles.length) {
    return skippedSourceIndices;
  }

  for (let idx = 0; idx < candidates.length; idx += 1) {
    const candidate = candidates[idx];
    const sourceIndex = Number(candidate?.sourceIndex);
    if (!Number.isFinite(sourceIndex) || sourceIndex < 0 || sourceIndex >= allFiles.length) {
      continue;
    }
    const file = allFiles[sourceIndex];
    const fileName = String(file?.name || candidate?.name || "").trim() || `File #${sourceIndex + 1}`;
    const fileSizeLabel = formatBytes(Number(file?.size || 0));
    const duplicateReason = String(candidate?.matchType || "") === "fingerprint"
      ? "This file content already exists in this case (content hash match)."
      : "This filename already exists in this case.";
    const shouldUploadDuplicate = window.confirm(
      `Duplicate file ${idx + 1}/${candidates.length}:\n\n${fileName}\n${fileSizeLabel}\n\n${duplicateReason}\n\nPress OK to upload this duplicate anyway.\nPress Cancel to skip this file.`,
    );
    if (!shouldUploadDuplicate) {
      skippedSourceIndices.add(sourceIndex);
    }
  }

  return skippedSourceIndices;
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
    if (item.isDuplicateExisting) {
      status.classList.add("duplicate-existing");
      status.textContent = `${formatBytes(item.sizeBytes)} | already in this case`;
    } else {
      status.textContent = formatBytes(item.sizeBytes);
    }

    row.appendChild(label);
    row.appendChild(status);
    preUploadIndexList.appendChild(row);
  });

  syncPreUploadSelectAllControl();
}

function refreshPendingUploadItemsFromInput() {
  const files = Array.from(videoInput?.files || []);
  const duplicateSet = new Set(
    detectDuplicateUploadCandidates(files, state.activeCaseId).map(
      (item) => Number(item.sourceIndex),
    ),
  );
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
      isDuplicateExisting: duplicateSet.has(sourceIndex),
      selectedForIndex,
    };
  });
  renderPreUploadIndexSelection();
}

function clearPendingUploadItems() {
  pendingUploadItems = [];
  renderPreUploadIndexSelection();
}

function refreshPendingUploadDuplicateFlags(caseId = null) {
  const activeCaseId = String(caseId || state.activeCaseId || "").trim();
  if (!activeCaseId || !pendingUploadItems.length) {
    return;
  }
  const files = Array.from(videoInput?.files || []);
  if (!files.length) {
    return;
  }
  const duplicateSet = new Set(
    detectDuplicateUploadCandidates(files, activeCaseId).map((item) => Number(item.sourceIndex)),
  );
  pendingUploadItems.forEach((item) => {
    item.isDuplicateExisting = duplicateSet.has(Number(item.sourceIndex));
  });
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
  const contract = video && typeof video.media_contract === "object" ? video.media_contract : null;
  const lifecycle = contract && typeof contract.lifecycle === "object" ? contract.lifecycle : null;
  if (lifecycle && typeof lifecycle.semantic_index_ready === "boolean") {
    return lifecycle.semantic_index_ready;
  }
  const indexedFrames = Math.max(0, Number(video?.indexed_frames || 0));
  const indexedWindows = Math.max(0, Number(video?.indexed_windows || 0));
  return indexedFrames > 0 || indexedWindows > 0;
}

function getCaseVideoSelection(caseId) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    return null;
  }
  let selection = videoSelectionByCase.get(normalizedCaseId);
  if (!(selection instanceof Set)) {
    selection = new Set();
    videoSelectionByCase.set(normalizedCaseId, selection);
  }
  return selection;
}

function clearVideoSelection(caseId) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    return;
  }
  videoSelectionByCase.delete(normalizedCaseId);
}

function normalizeVideoFilenames(videos) {
  const list = Array.isArray(videos) ? videos : [];
  return list
    .map((item) => String(item?.filename || "").trim())
    .filter(Boolean);
}

function syncVideoSelectionControls(videos) {
  if (!videoBulkActions || !videoSelectAll || !deleteSelectedVideosBtn || !videoSelectionMeta) {
    return;
  }
  const activeCaseId = String(state.activeCaseId || "").trim();
  const filenames = normalizeVideoFilenames(videos);
  const hasVideos = filenames.length > 0;
  const filenameSet = new Set(filenames);
  const selection = getCaseVideoSelection(activeCaseId);

  let selectedCount = 0;
  if (selection instanceof Set) {
    for (const name of Array.from(selection)) {
      if (!filenameSet.has(name)) {
        selection.delete(name);
      }
    }
    selectedCount = selection.size;
  }

  videoBulkActions.hidden = !activeCaseId;
  videoSelectAll.disabled = !activeCaseId || !hasVideos;
  videoSelectAll.checked = hasVideos && selectedCount > 0 && selectedCount === filenames.length;
  videoSelectAll.indeterminate = hasVideos && selectedCount > 0 && selectedCount < filenames.length;
  deleteSelectedVideosBtn.disabled = !activeCaseId || selectedCount === 0;
  videoSelectionMeta.textContent = activeCaseId
    ? `${selectedCount} selected`
    : "No active case";
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

function getActiveQueuedOrRunningIndexFilenames(caseId) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    return new Set();
  }
  const statusPayload = backgroundIndexStatusByCase.get(normalizedCaseId);
  if (!isBackgroundIndexRunning(statusPayload)) {
    return new Set();
  }

  const queued = new Set();
  const filenames = Array.isArray(statusPayload?.filenames) ? statusPayload.filenames : [];
  filenames.forEach((item) => {
    const safeName = String(item || "").trim();
    if (safeName) {
      queued.add(safeName);
    }
  });
  const currentFilename = String(statusPayload?.current_filename || "").trim();
  if (currentFilename) {
    queued.add(currentFilename);
  }
  return queued;
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
  const queuedOrRunningFilenames = getActiveQueuedOrRunningIndexFilenames(activeCaseId);
  const selectableUnindexedVideos = unindexedVideos.filter((video) => (
    !queuedOrRunningFilenames.has(String(video?.filename || "").trim())
  ));

  if (!selectableUnindexedVideos.length) {
    const message = unindexedVideos.length && queuedOrRunningFilenames.size
      ? "All unindexed videos are already queued/running for semantic indexing."
      : "All uploaded videos are already semantically indexed.";
    existingIndexList.appendChild(
      createInsightEmptyElement(message),
    );
    if (runExistingIndexBtn) {
      runExistingIndexBtn.disabled = true;
    }
    syncExistingIndexSelectAllControl();
    return;
  }

  selectableUnindexedVideos.forEach((video) => {
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

function setTaskProgressStopCase(caseId) {
  if (!taskProgressStopBtn) {
    return;
  }
  const normalizedCaseId = String(caseId || "").trim();
  const canStop = Boolean(normalizedCaseId);
  taskProgressStopCaseId = canStop ? normalizedCaseId : "";
  taskProgressStopBtn.hidden = !canStop;
  taskProgressStopBtn.disabled = !canStop || stopBackgroundIndexInFlight;
}

function setTaskProgressUi(label, percent, meta, options = null) {
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

  const stopCaseId = options && typeof options === "object"
    ? String(options.stopCaseId || "").trim()
    : "";
  setTaskProgressStopCase(stopCaseId);
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
    setTaskProgressStopCase("");
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
  setTaskProgressStopCase("");
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
  updateIndexQueueSummaryButton(normalizedCaseId, statusPayload);
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
    setTaskProgressUi(
      "Semantic indexing (background)",
      progressPercent,
      meta,
      { stopCaseId: normalizedCaseId },
    );
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
    backgroundIndexStatusByCase.clear();
    if (indexQueueSummaryBtn) {
      indexQueueSummaryBtn.hidden = true;
    }
    return null;
  }

  const statusPayload = await readBackgroundIndexStatus(normalizedCaseId);
  if (!statusPayload) {
    backgroundIndexStatusByCase.delete(normalizedCaseId);
    if (state.activeCaseId === normalizedCaseId) {
      renderExistingIndexSelectionList(getCaseVideos(normalizedCaseId));
    }
    if (state.activeCaseId === normalizedCaseId) {
      hideTaskProgressUi();
      if (indexQueueSummaryBtn) {
        indexQueueSummaryBtn.hidden = true;
      }
    }
    return null;
  }

  backgroundIndexStatusByCase.set(normalizedCaseId, statusPayload);
  if (state.activeCaseId === normalizedCaseId) {
    renderExistingIndexSelectionList(getCaseVideos(normalizedCaseId));
  }

  renderBackgroundIndexStatus(normalizedCaseId, statusPayload);
  updateIndexQueueSummaryButton(normalizedCaseId, statusPayload);
  if (isBackgroundIndexRunning(statusPayload)) {
    startBackgroundIndexPolling(normalizedCaseId);
  } else if (indexStatusPollCaseId === normalizedCaseId) {
    stopBackgroundIndexPolling();
  }
  return statusPayload;
}

function hideQueueSummaryButtons() {
  if (indexQueueSummaryBtn) {
    indexQueueSummaryBtn.hidden = true;
  }
  if (facePeopleQueueSummaryBtn) {
    facePeopleQueueSummaryBtn.hidden = true;
  }
  if (vehicleQueueSummaryBtn) {
    vehicleQueueSummaryBtn.hidden = true;
  }
}

function analysisStatusCacheMap(category) {
  const normalizedCategory = normalizeAnalysisCategory(category);
  return analysisQueueStatusByCase[normalizedCategory];
}

function setAnalysisQueueStatusCache(category, caseId, payload) {
  const normalizedCaseId = String(caseId || "").trim();
  const cache = analysisStatusCacheMap(category);
  if (!cache || !normalizedCaseId) {
    return;
  }
  if (!payload || typeof payload !== "object") {
    cache.delete(normalizedCaseId);
    return;
  }
  cache.set(normalizedCaseId, payload);
}

function getAnalysisQueueStatusCache(category, caseId) {
  const normalizedCaseId = String(caseId || "").trim();
  const cache = analysisStatusCacheMap(category);
  if (!cache || !normalizedCaseId) {
    return null;
  }
  return cache.get(normalizedCaseId) || null;
}

function activeCaseFilenamesFromPayload(payload) {
  return Array.isArray(payload?.filenames)
    ? payload.filenames
        .map((item) => String(item || "").trim())
        .filter((item) => item.length > 0)
    : [];
}

function updateIndexQueueSummaryButton(caseId, statusPayload) {
  if (!indexQueueSummaryBtn) {
    return;
  }
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId || state.activeCaseId !== normalizedCaseId) {
    indexQueueSummaryBtn.hidden = true;
    return;
  }
  if (!statusPayload || typeof statusPayload !== "object") {
    indexQueueSummaryBtn.hidden = true;
    return;
  }
  const filenames = activeCaseFilenamesFromPayload(statusPayload);
  const running = isBackgroundIndexRunning(statusPayload);
  if (!running || !filenames.length) {
    indexQueueSummaryBtn.hidden = true;
    return;
  }
  const count = filenames.length;
  indexQueueSummaryBtn.textContent = `${count} file${count === 1 ? "" : "s"} queued for indexing`;
  indexQueueSummaryBtn.hidden = false;
}

function updateAnalysisQueueSummaryButton(category, caseId, statusPayload) {
  const normalizedCategory = normalizeAnalysisCategory(category);
  const button = normalizedCategory === "vehicles"
    ? vehicleQueueSummaryBtn
    : facePeopleQueueSummaryBtn;
  if (!button) {
    return;
  }
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId || state.activeCaseId !== normalizedCaseId) {
    button.hidden = true;
    return;
  }
  if (!statusPayload || typeof statusPayload !== "object") {
    button.hidden = true;
    return;
  }
  const queueJobId = Math.max(0, Number(statusPayload?.queue?.job_id || 0));
  const running = isAnalysisQueueRunning(statusPayload, queueJobId);
  const status = String(statusPayload?.status || statusPayload?.queue?.status || "").trim().toLowerCase();
  const interrupted = status === "interrupted";
  const filenames = activeCaseFilenamesFromPayload(statusPayload);
  if ((!running && !interrupted) || !filenames.length) {
    button.hidden = true;
    return;
  }
  const count = filenames.length;
  const label = analysisCategoryLabel(normalizedCategory);
  button.textContent = interrupted
    ? `${count} interrupted file${count === 1 ? "" : "s"} for ${label} analysis`
    : `${count} file${count === 1 ? "" : "s"} queued for ${label} analysis`;
  button.hidden = false;
}

function refreshQueueSummaryButtonsForActiveCase() {
  const caseId = String(state.activeCaseId || "").trim();
  if (!caseId) {
    hideQueueSummaryButtons();
    return;
  }
  const indexStatus = backgroundIndexStatusByCase.get(caseId) || null;
  updateIndexQueueSummaryButton(caseId, indexStatus);
  const faceStatus = getAnalysisQueueStatusCache("face_people", caseId);
  const vehicleStatus = getAnalysisQueueStatusCache("vehicles", caseId);
  updateAnalysisQueueSummaryButton("face_people", caseId, faceStatus);
  updateAnalysisQueueSummaryButton("vehicles", caseId, vehicleStatus);
}

function openIndexQueueSummaryPopup() {
  const caseId = String(state.activeCaseId || "").trim();
  if (!caseId) {
    setStatus("Select a case first.", "error");
    return;
  }
  const payload = backgroundIndexStatusByCase.get(caseId);
  if (!payload || typeof payload !== "object") {
    setStatus("No active semantic indexing queue for this case.", "error");
    return;
  }
  const filenames = activeCaseFilenamesFromPayload(payload);
  if (!filenames.length) {
    setStatus("No queued files found for semantic indexing.", "error");
    return;
  }
  openQueueTaskPopup({
    type: "background_index",
    case_id: caseId,
    status: String(payload.status || ""),
    queue_job_id: Number(payload?.queue?.job_id || payload?.queue_job_id || 0),
    job_kind: "semantic_index",
    current_filename: String(payload.current_filename || ""),
    current_video_processed_frames: Number(payload.current_video_processed_frames || 0),
    current_video_total_frames: Number(payload.current_video_total_frames || 0),
    current_video_progress_percent: Number(payload.current_video_progress_percent || 0),
    filenames,
    filenames_count: filenames.length,
    file_progress: Array.isArray(payload.file_progress) ? payload.file_progress : [],
  });
}

function openAnalysisQueueSummaryPopup(category) {
  const normalizedCategory = normalizeAnalysisCategory(category);
  const caseId = String(state.activeCaseId || "").trim();
  if (!caseId) {
    setStatus("Select a case first.", "error");
    return;
  }
  const payload = getAnalysisQueueStatusCache(normalizedCategory, caseId);
  if (!payload || typeof payload !== "object") {
    setCategoryAnalysisStatus(normalizedCategory, "No active analysis queue for this case.", "error");
    return;
  }
  const filenames = activeCaseFilenamesFromPayload(payload);
  if (!filenames.length) {
    setCategoryAnalysisStatus(normalizedCategory, "No queued files found for analysis.", "error");
    return;
  }
  const queue = payload.queue && typeof payload.queue === "object" ? payload.queue : {};
  const analysis = payload.analysis && typeof payload.analysis === "object" ? payload.analysis : {};
  const facePeopleFilenames = Array.isArray(payload.analysis_face_people_filenames)
    ? payload.analysis_face_people_filenames
    : [];
  const vehiclesFilenames = Array.isArray(payload.analysis_vehicles_filenames)
    ? payload.analysis_vehicles_filenames
    : [];
  openQueueTaskPopup({
    type: "queue_job",
    case_id: caseId,
    status: String(queue.status || payload.status || ""),
    queue_job_id: Number(queue.job_id || 0),
    job_kind: "analysis",
    queue_position: Number(queue.position_ahead || 0),
    priority: Number(queue.priority || 0),
    attempt_count: Number(queue.attempt_count || 0),
    filenames,
    filenames_count: filenames.length,
    metadata: {
      analysis_face_people: Boolean(analysis.face_people),
      analysis_vehicles: Boolean(analysis.vehicles),
      analysis_face_people_filenames: facePeopleFilenames,
      analysis_vehicles_filenames: vehiclesFilenames,
    },
    file_progress: Array.isArray(payload.file_progress) ? payload.file_progress : [],
    recovery_category: normalizedCategory,
    message: String(payload.message || ""),
  });
}

function normalizeAnalysisCategory(category) {
  return category === "vehicles" ? "vehicles" : "face_people";
}

function analysisCategoryLabel(category) {
  return normalizeAnalysisCategory(category) === "vehicles" ? "Vehicles" : "Face & People";
}

function setCategoryAnalysisStatus(category, message, kind = "") {
  if (normalizeAnalysisCategory(category) === "vehicles") {
    setVehicleStatus(message, kind);
  } else {
    setAnalysisStatus(message, kind);
  }
}

function pickFirstFiniteNumber(candidates, fallback = null) {
  if (!Array.isArray(candidates)) {
    return fallback;
  }
  for (const value of candidates) {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      return numeric;
    }
  }
  return fallback;
}

function getAnalysisQueueSnapshot(statusPayload, fallbackJobId = 0) {
  const payload = statusPayload && typeof statusPayload === "object" ? statusPayload : {};
  const queue = payload.queue && typeof payload.queue === "object" ? payload.queue : {};
  const statusCandidates = [queue.status, payload.status, payload.state];
  let status = "";
  statusCandidates.forEach((item) => {
    if (status) {
      return;
    }
    const normalized = String(item || "").trim().toLowerCase();
    if (normalized) {
      status = normalized;
    }
  });

  const jobIdCandidate = pickFirstFiniteNumber(
    [queue.job_id, payload.job_id, payload.queue_job_id, fallbackJobId],
    0,
  );
  const jobId = Number.isFinite(jobIdCandidate)
    ? Math.max(0, Math.floor(jobIdCandidate))
    : 0;

  const queueAheadCandidate = pickFirstFiniteNumber(
    [queue.position_ahead, queue.queue_position, payload.position_ahead, payload.queue_position],
    null,
  );
  const queueAhead = Number.isFinite(queueAheadCandidate)
    ? Math.max(0, Math.floor(queueAheadCandidate))
    : null;

  return { payload, queue, status, jobId, queueAhead };
}

function getAnalysisQueueProgress(statusPayload) {
  const payload = statusPayload && typeof statusPayload === "object" ? statusPayload : {};
  const progress = payload.progress && typeof payload.progress === "object" ? payload.progress : {};

  const completedCandidate = pickFirstFiniteNumber(
    [payload.completed, payload.processed, progress.completed, progress.processed, progress.done],
    null,
  );
  const totalCandidate = pickFirstFiniteNumber(
    [payload.total, progress.total, progress.count],
    null,
  );
  const percentCandidate = pickFirstFiniteNumber(
    [payload.progress_percent, payload.percent, progress.progress_percent, progress.percent],
    null,
  );

  const hasCompleted = completedCandidate !== null;
  const hasTotal = totalCandidate !== null;
  const completed = hasCompleted ? Math.max(0, Math.floor(Number(completedCandidate))) : 0;
  const total = hasTotal ? Math.max(0, Math.floor(Number(totalCandidate))) : 0;

  let percent = null;
  if (percentCandidate !== null) {
    percent = clampPercent(percentCandidate);
  } else if (hasTotal && total > 0) {
    percent = clampPercent((completed / total) * 100);
  }

  return {
    completed,
    total,
    percent: percent === null ? 0 : percent,
    hasCompleted,
    hasTotal,
    hasPercent: percent !== null,
    hasProgress: hasCompleted || hasTotal || percent !== null,
  };
}

function isAnalysisQueueRunning(statusPayload, fallbackJobId = 0) {
  const snapshot = getAnalysisQueueSnapshot(statusPayload, fallbackJobId);
  const progress = getAnalysisQueueProgress(snapshot.payload);
  const status = snapshot.status;

  if (Boolean(snapshot.payload.running) || Boolean(snapshot.payload.queued)) {
    return true;
  }
  if (
    status === "queued"
    || status === "running"
    || status === "pending"
    || status === "starting"
    || status === "cancelling"
    || status === "cancel_requested"
  ) {
    return true;
  }
  if (
    status === "completed"
    || status === "processed"
    || status === "success"
    || status === "succeeded"
    || status === "completed_with_errors"
    || status === "failed"
    || status === "error"
    || status === "cancelled"
    || status === "canceled"
    || status === "interrupted"
    || status === "aborted"
    || status === "idle"
    || status === "skipped"
    || status === "not_requested"
  ) {
    return false;
  }
  if (snapshot.queueAhead !== null && snapshot.queueAhead > 0) {
    return true;
  }
  if (progress.hasTotal && progress.total > 0 && progress.completed < progress.total) {
    return true;
  }
  return false;
}

function isAnalysisQueueErrorStatus(status) {
  return (
    status === "failed"
    || status === "error"
    || status === "cancelled"
    || status === "canceled"
    || status === "interrupted"
    || status === "aborted"
    || status === "completed_with_errors"
  );
}

function analysisQueueStatusVerb(status, running) {
  if (status === "queued" || status === "pending" || status === "starting") {
    return "queued";
  }
  if (status === "running") {
    return "running";
  }
  if (status === "cancelling" || status === "cancel_requested") {
    return "cancelling";
  }
  if (
    status === "completed"
    || status === "processed"
    || status === "success"
    || status === "succeeded"
  ) {
    return "completed";
  }
  if (status === "completed_with_errors") {
    return "completed with errors";
  }
  if (status === "failed" || status === "error") {
    return "failed";
  }
  if (status === "cancelled" || status === "canceled") {
    return "cancelled";
  }
  if (status === "interrupted" || status === "aborted") {
    return "interrupted";
  }
  if (status === "idle") {
    return running ? "running" : "completed";
  }
  return running ? "running" : "completed";
}

function analysisQueueStatusKind(statusPayload, fallbackJobId = 0) {
  const snapshot = getAnalysisQueueSnapshot(statusPayload, fallbackJobId);
  const running = isAnalysisQueueRunning(snapshot.payload, snapshot.jobId);
  if (running) {
    return "working";
  }
  if (isAnalysisQueueErrorStatus(snapshot.status)) {
    return "error";
  }
  const failedCount = Math.max(
    0,
    Number(
      pickFirstFiniteNumber(
        [snapshot.payload.failed, snapshot.payload.error_count, snapshot.payload.errors],
        0,
      ),
    ),
  );
  if (failedCount > 0) {
    return "error";
  }
  return "ok";
}

function formatAnalysisQueueStatusMessage(category, statusPayload, options = {}) {
  const normalizedCategory = normalizeAnalysisCategory(category);
  const fallbackJobId = Math.max(0, Number(options?.jobId || 0));
  const snapshot = getAnalysisQueueSnapshot(statusPayload, fallbackJobId);
  const running = isAnalysisQueueRunning(snapshot.payload, snapshot.jobId);
  const statusWord = analysisQueueStatusVerb(snapshot.status, running);
  const progress = getAnalysisQueueProgress(snapshot.payload);
  const currentFilename = String(snapshot.payload.current_filename || "").trim();
  const payloadMessage = String(snapshot.payload.message || "").trim();
  const parts = [`${analysisCategoryLabel(normalizedCategory)} analysis ${statusWord}.`];

  if (snapshot.jobId > 0) {
    parts.push(`Job #${snapshot.jobId}.`);
  }
  if (snapshot.queueAhead !== null) {
    parts.push(`Queue ahead: ${snapshot.queueAhead}.`);
  }
  if (progress.hasProgress) {
    const completedLabel = progress.hasCompleted ? String(progress.completed) : "?";
    const totalLabel = progress.hasTotal ? String(progress.total) : "?";
    const percentLabel = progress.hasPercent ? `${Math.round(progress.percent)}%` : "n/a";
    parts.push(`Progress: ${completedLabel}/${totalLabel} (${percentLabel}).`);
  }
  if (currentFilename) {
    parts.push(`Current: ${currentFilename}.`);
  }
  const analysisInfo = snapshot.payload.analysis && typeof snapshot.payload.analysis === "object"
    ? snapshot.payload.analysis
    : {};
  const analysisModes = analysisModesLabelFromFlags(
    Boolean(analysisInfo.face_people),
    Boolean(analysisInfo.vehicles),
  );
  if (analysisModes) {
    const sharedLabel = Boolean(analysisInfo.face_people) && Boolean(analysisInfo.vehicles)
      ? " (shared job)"
      : "";
    parts.push(`Modes: ${analysisModes}${sharedLabel}.`);
  }
  if (payloadMessage) {
    parts.push(payloadMessage);
  }

  return {
    message: parts.join(" "),
    kind: analysisQueueStatusKind(snapshot.payload, snapshot.jobId),
    running,
    jobId: snapshot.jobId,
  };
}

function parseHttpStatusCode(error) {
  const raw = formatError(error);
  const match = /^\[(\d{3})\]/.exec(raw);
  if (!match) {
    return 0;
  }
  return Number(match[1] || 0);
}

function buildAnalysisQueueStatusUrl(caseId, category, jobId = 0) {
  const normalizedCaseId = String(caseId || "").trim();
  const normalizedCategory = normalizeAnalysisCategory(category);
  const safeJobId = Math.max(0, Number(jobId || 0));
  const params = new URLSearchParams();
  params.set("case_id", normalizedCaseId);
  params.set("category", normalizedCategory);
  if (safeJobId > 0) {
    params.set("job_id", String(Math.floor(safeJobId)));
  }
  return `/analysis/status?${params.toString()}`;
}

function stopAnalysisStatusPolling(category = null) {
  if (!category) {
    ANALYSIS_CATEGORIES.forEach((item) => {
      stopAnalysisStatusPolling(item);
    });
    return;
  }
  const normalizedCategory = normalizeAnalysisCategory(category);
  const pollState = analysisStatusPollStateByCategory[normalizedCategory];
  if (!pollState) {
    return;
  }
  pollState.token += 1;
  pollState.caseId = "";
  pollState.jobId = 0;
}

function renderAnalysisQueueStatus(category, caseId, statusPayload, options = {}) {
  const normalizedCaseId = String(caseId || "").trim();
  const normalizedCategory = normalizeAnalysisCategory(category);
  if (!normalizedCaseId || state.activeCaseId !== normalizedCaseId) {
    return { message: "", kind: "", running: false, jobId: 0 };
  }

  setAnalysisQueueStatusCache(normalizedCategory, normalizedCaseId, statusPayload);
  updateAnalysisQueueSummaryButton(normalizedCategory, normalizedCaseId, statusPayload);

  const formatted = formatAnalysisQueueStatusMessage(normalizedCategory, statusPayload, {
    jobId: Math.max(0, Number(options?.jobId || 0)),
  });
  setCategoryAnalysisStatus(normalizedCategory, formatted.message, formatted.kind);
  return formatted;
}

async function readAnalysisQueueStatus(caseId, category, options = {}) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    return null;
  }
  const normalizedCategory = normalizeAnalysisCategory(category);
  const safeJobId = Math.max(0, Number(options?.jobId || 0));
  return fetchJson(buildAnalysisQueueStatusUrl(normalizedCaseId, normalizedCategory, safeJobId));
}

async function syncAnalysisQueueStatus(caseId, category, options = {}) {
  const normalizedCaseId = String(caseId || "").trim();
  const normalizedCategory = normalizeAnalysisCategory(category);
  if (!normalizedCaseId) {
    setAnalysisQueueStatusCache(normalizedCategory, "", null);
    updateAnalysisQueueSummaryButton(normalizedCategory, "", null);
    return null;
  }

  let statusPayload = null;
  try {
    statusPayload = await readAnalysisQueueStatus(normalizedCaseId, normalizedCategory, {
      jobId: Math.max(0, Number(options?.jobId || 0)),
    });
  } catch (error) {
    const statusCode = parseHttpStatusCode(error);
    if (statusCode === 404) {
      setCategoryAnalysisStatus(
        normalizedCategory,
        `${analysisCategoryLabel(normalizedCategory)} analysis status endpoint unavailable: ${formatError(error)}`,
        "error",
      );
    } else {
      setCategoryAnalysisStatus(
        normalizedCategory,
        `Failed to load ${analysisCategoryLabel(normalizedCategory)} analysis queue status: ${formatError(error)}`,
        "error",
      );
    }
    setAnalysisQueueStatusCache(normalizedCategory, normalizedCaseId, null);
    updateAnalysisQueueSummaryButton(normalizedCategory, normalizedCaseId, null);
    stopAnalysisStatusPolling(normalizedCategory);
    return null;
  }

  if (!statusPayload || typeof statusPayload !== "object") {
    setAnalysisQueueStatusCache(normalizedCategory, normalizedCaseId, null);
    updateAnalysisQueueSummaryButton(normalizedCategory, normalizedCaseId, null);
    stopAnalysisStatusPolling(normalizedCategory);
    return null;
  }

  const rendered = renderAnalysisQueueStatus(
    normalizedCategory,
    normalizedCaseId,
    statusPayload,
    { jobId: Math.max(0, Number(options?.jobId || 0)) },
  );

  if (rendered.running) {
    startAnalysisStatusPolling(normalizedCaseId, normalizedCategory, { jobId: rendered.jobId });
  } else {
    stopAnalysisStatusPolling(normalizedCategory);
  }
  return statusPayload;
}

function startAnalysisStatusPolling(caseId, category, options = {}) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    return;
  }
  const normalizedCategory = normalizeAnalysisCategory(category);
  const pollState = analysisStatusPollStateByCategory[normalizedCategory];
  if (!pollState) {
    return;
  }

  stopAnalysisStatusPolling(normalizedCategory);
  pollState.caseId = normalizedCaseId;
  pollState.jobId = Math.max(0, Number(options?.jobId || 0));
  const pollToken = ++pollState.token;
  let consecutiveFailures = 0;

  const poll = async () => {
    const latestState = analysisStatusPollStateByCategory[normalizedCategory];
    if (pollToken !== latestState.token || latestState.caseId !== normalizedCaseId) {
      return;
    }
    if (state.activeCaseId !== normalizedCaseId) {
      stopAnalysisStatusPolling(normalizedCategory);
      return;
    }

    let statusPayload = null;
    try {
      statusPayload = await readAnalysisQueueStatus(normalizedCaseId, normalizedCategory, {
        jobId: latestState.jobId,
      });
      consecutiveFailures = 0;
    } catch (error) {
      const statusCode = parseHttpStatusCode(error);
      if (statusCode === 404) {
        setCategoryAnalysisStatus(
          normalizedCategory,
          `${analysisCategoryLabel(normalizedCategory)} analysis status endpoint unavailable: ${formatError(error)}`,
          "error",
        );
        if (pollToken === latestState.token && latestState.caseId === normalizedCaseId) {
          stopAnalysisStatusPolling(normalizedCategory);
        }
        return;
      }
      consecutiveFailures += 1;
      if (consecutiveFailures >= 4) {
        setCategoryAnalysisStatus(
          normalizedCategory,
          `${analysisCategoryLabel(normalizedCategory)} analysis status polling failed: ${formatError(error)}`,
          "error",
        );
        if (pollToken === latestState.token && latestState.caseId === normalizedCaseId) {
          stopAnalysisStatusPolling(normalizedCategory);
        }
        return;
      }
      window.setTimeout(poll, 1800);
      return;
    }

    if (pollToken !== latestState.token || latestState.caseId !== normalizedCaseId) {
      return;
    }
    if (!statusPayload || typeof statusPayload !== "object") {
      window.setTimeout(poll, 1600);
      return;
    }

    const rendered = renderAnalysisQueueStatus(
      normalizedCategory,
      normalizedCaseId,
      statusPayload,
      { jobId: latestState.jobId },
    );
    if (rendered.jobId > 0) {
      latestState.jobId = rendered.jobId;
    }
    if (rendered.running) {
      window.setTimeout(poll, 1300);
      return;
    }

    if (state.activeCaseId === normalizedCaseId) {
      try {
        await refreshVideos(normalizedCaseId);
      } catch (error) {
        console.warn(`Refresh after analysis queue status failed: ${formatError(error)}`);
      }
    }
    if (pollToken === latestState.token && latestState.caseId === normalizedCaseId) {
      stopAnalysisStatusPolling(normalizedCategory);
    }
  };

  void poll();
}

async function stopBackgroundIndexFromProgress() {
  const targetCaseId = String(taskProgressStopCaseId || state.activeCaseId || "").trim();
  if (!targetCaseId) {
    setStatus("No active case selected for stopping indexing.", "error");
    return;
  }

  if (stopBackgroundIndexInFlight) {
    return;
  }

  const confirmed = window.confirm(
    `Stop semantic indexing for case ${targetCaseId}? Current in-flight video work may take a short while to settle.`,
  );
  if (!confirmed) {
    return;
  }

  try {
    stopBackgroundIndexInFlight = true;
    setTaskProgressStopCase(targetCaseId);
    setStatus(`Stopping semantic indexing for ${targetCaseId}...`, "working");
    const payload = await fetchJson("/processes/index/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ case_id: targetCaseId, force: false }),
    });
    const queueCancelled = Math.max(0, Number(payload?.queue_cancelled_count || 0));
    const requested = Boolean(payload?.cancel_requested);
    const message = requested
      ? `Stop requested for ${targetCaseId}. Queue entries cancelled: ${queueCancelled}. Current in-flight file will stop shortly.`
      : `No active semantic indexing found for ${targetCaseId}.`;
    setStatus(message, requested ? "ok" : "error");

    const latestStatus = await syncBackgroundIndexStatus(targetCaseId);
    if (!isBackgroundIndexRunning(latestStatus)) {
      hideTaskProgressUi();
    }

    if (state.activeCaseId === targetCaseId) {
      await refreshVideos(targetCaseId);
    }
  } catch (error) {
    setStatus(`Stop indexing failed: ${formatError(error)}`, "error");
  } finally {
    stopBackgroundIndexInFlight = false;
    setTaskProgressStopCase(taskProgressStopCaseId);
  }
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

function queueJobKindLabel(jobKind, processItem = null) {
  const kind = String(jobKind || "").trim().toLowerCase();
  if (kind === "semantic_index") {
    return "Semantic Index";
  }
  if (kind === "triage_timeline") {
    return "Triage Timeline";
  }
  if (kind === "analysis") {
    const metadata = processItem && typeof processItem.metadata === "object" ? processItem.metadata : {};
    const facePeople = Boolean(metadata.analysis_face_people);
    const vehicles = Boolean(metadata.analysis_vehicles);
    if (facePeople && vehicles) {
      return "Analysis (Face & People + Vehicles)";
    }
    if (facePeople) {
      return "Analysis (Face & People)";
    }
    if (vehicles) {
      return "Analysis (Vehicles)";
    }
    return "Analysis";
  }
  if (!kind) {
    return "Queue Job";
  }
  return kind;
}

function analysisModesLabelFromFlags(facePeople, vehicles) {
  const hasFacePeople = Boolean(facePeople);
  const hasVehicles = Boolean(vehicles);
  if (hasFacePeople && hasVehicles) {
    return "Face & People + Vehicles";
  }
  if (hasFacePeople) {
    return "Face & People";
  }
  if (hasVehicles) {
    return "Vehicles";
  }
  return "";
}

function queueTaskFilenames(item) {
  const fullList = Array.isArray(item?.filenames)
    ? item.filenames
        .map((value) => String(value || "").trim())
        .filter((value) => value.length > 0)
    : [];
  const fallbackPreview = Array.isArray(item?.filenames_preview)
    ? item.filenames_preview
        .map((value) => String(value || "").trim())
        .filter((value) => value.length > 0)
    : [];

  const source = fullList.length ? fullList : fallbackPreview;
  const deduped = [];
  const seen = new Set();
  source.forEach((name) => {
    if (!name || seen.has(name)) {
      return;
    }
    seen.add(name);
    deduped.push(name);
  });

  const currentFilename = String(item?.current_filename || "").trim();
  if (currentFilename && !seen.has(currentFilename)) {
    deduped.unshift(currentFilename);
  }
  return deduped;
}

function queueTaskStageNameFromItem(item) {
  const type = String(item?.type || "").trim().toLowerCase();
  if (type === "background_index") {
    return "base_index";
  }
  const kind = String(item?.job_kind || "").trim().toLowerCase();
  if (kind === "semantic_index") {
    return "base_index";
  }
  if (kind === "analysis") {
    return "analysis";
  }
  if (kind === "triage_timeline") {
    return "triage";
  }
  return "";
}

function queueTaskProgressFromStageStatus(status, fallbackPercent = 0) {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "completed" || normalized === "skipped") {
    return 100;
  }
  if (normalized === "failed" || normalized === "interrupted") {
    return 100;
  }
  if (normalized === "running") {
    const numeric = Number(fallbackPercent);
    if (Number.isFinite(numeric) && numeric > 0) {
      return clampPercent(numeric);
    }
    return 50;
  }
  return 0;
}

function normalizeStringList(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  const output = [];
  const seen = new Set();
  value.forEach((item) => {
    const safe = String(item || "").trim();
    if (!safe || seen.has(safe)) {
      return;
    }
    seen.add(safe);
    output.push(safe);
  });
  return output;
}

function queueTaskAnalysisModesForFilename(item, filename) {
  const metadata = item?.metadata && typeof item.metadata === "object" ? item.metadata : {};
  const facePeopleSet = new Set(normalizeStringList(metadata.analysis_face_people_filenames));
  const vehiclesSet = new Set(normalizeStringList(metadata.analysis_vehicles_filenames));
  const hasPerFileLists = facePeopleSet.size > 0 || vehiclesSet.size > 0;
  const hasFacePeople = Boolean(metadata.analysis_face_people);
  const hasVehicles = Boolean(metadata.analysis_vehicles);

  if (hasPerFileLists) {
    const includeFacePeople = facePeopleSet.has(filename);
    const includeVehicles = vehiclesSet.has(filename);
    const modes = [];
    if (includeFacePeople) {
      modes.push({ label: "Face & People", key: "face_people" });
    }
    if (includeVehicles) {
      modes.push({ label: "Vehicles", key: "vehicles" });
    }
    if (modes.length) {
      return modes;
    }
    // Unknown membership for this filename even though lists exist; keep one row.
    return [{ label: "Analysis", key: "analysis" }];
  }

  // No per-file mapping available; keep one row per file to avoid false duplication.
  if (hasFacePeople && hasVehicles) {
    return [{ label: "Face & People + Vehicles", key: "both" }];
  }
  if (hasFacePeople) {
    return [{ label: "Face & People", key: "face_people" }];
  }
  if (hasVehicles) {
    return [{ label: "Vehicles", key: "vehicles" }];
  }

  return [{ label: "", key: "" }];
}

function expandQueueRowsByAnalysisModes(item, rows) {
  const safeRows = Array.isArray(rows) ? rows : [];
  const jobKind = String(item?.job_kind || "").trim().toLowerCase();
  if (jobKind !== "analysis") {
    return safeRows;
  }

  const expanded = [];
  safeRows.forEach((row) => {
    if (!row || typeof row !== "object") {
      return;
    }
    const filename = String(row.filename || "").trim();
    if (!filename) {
      expanded.push(row);
      return;
    }
    const modes = queueTaskAnalysisModesForFilename(item, filename);
    modes.forEach((mode) => {
      expanded.push({
        ...row,
        analysisModeLabel: String(mode?.label || ""),
        analysisModeKey: String(mode?.key || ""),
      });
    });
  });
  return expanded;
}

function queueTaskStageStatusLabel(status) {
  const normalized = String(status || "").trim().toLowerCase();
  if (!normalized) {
    return "pending";
  }
  return normalized.replaceAll("_", " ");
}

function normalizeQueueTaskRecoveryCategory(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "vehicles") {
    return "vehicles";
  }
  if (normalized === "face_people") {
    return "face_people";
  }
  return "";
}

function isQueueTaskRecoveryAvailable(item) {
  const status = String(item?.status || "").trim().toLowerCase();
  if (status !== "interrupted") {
    return false;
  }
  const category = normalizeQueueTaskRecoveryCategory(item?.recovery_category);
  if (!category) {
    return false;
  }
  const filenames = queueTaskFilenames(item);
  return filenames.length > 0;
}

function isQueueTaskFileRemovalAvailable(item) {
  const type = String(item?.type || "").trim().toLowerCase();
  if (type !== "queue_job") {
    return false;
  }
  const status = String(item?.status || "").trim().toLowerCase();
  if (status !== "queued") {
    return false;
  }
  const jobId = queueTaskPopupResolveJobId(item);
  if (!jobId) {
    return false;
  }
  return queueTaskFilenames(item).length > 0;
}

function formatQueueTimestamp(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "n/a";
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    return raw;
  }
  return parsed.toLocaleString();
}

function queueTaskPopupConfigureActionButtons(options = {}) {
  if (queueTaskPopupRestartBtn) {
    queueTaskPopupRestartBtn.hidden = !Boolean(options.restart);
  }
  if (queueTaskPopupCancelBtn) {
    queueTaskPopupCancelBtn.hidden = !Boolean(options.cancel);
  }
  if (queueTaskPopupRemoveFilesBtn) {
    queueTaskPopupRemoveFilesBtn.hidden = !Boolean(options.removeFiles);
  }
}

function queueTaskPopupSetRecoveryStatus(message, kind = "") {
  if (!queueTaskPopupRecoveryStatus) {
    return;
  }
  queueTaskPopupRecoveryStatus.textContent = String(message || "");
  queueTaskPopupRecoveryStatus.className = `status ${kind}`.trim();
}

function queueTaskPopupResetRecovery() {
  queueTaskPopupRecoveryContext = null;
  queueTaskPopupCurrentItem = null;
  if (queueTaskPopupRecovery) {
    queueTaskPopupRecovery.setAttribute("hidden", "");
  }
  queueTaskPopupConfigureActionButtons({
    restart: false,
    cancel: false,
    removeFiles: false,
  });
  if (queueTaskPopupDeleteBtn) {
    queueTaskPopupDeleteBtn.setAttribute("hidden", "");
    queueTaskPopupDeleteBtn.textContent = "Delete Queue Item";
  }
  if (queueTaskPopupSelectAll) {
    queueTaskPopupSelectAll.checked = false;
    queueTaskPopupSelectAll.indeterminate = false;
  }
  if (queueTaskPopupSelectionMeta) {
    queueTaskPopupSelectionMeta.textContent = "0 selected";
  }
  queueTaskPopupSetRecoveryStatus("", "");
}

function queueTaskPopupResolveJobId(item) {
  const candidates = [
    item?.queue_job_id,
    item?.job_id,
    item?.queue?.job_id,
  ];
  for (const candidate of candidates) {
    const parsed = Number(candidate);
    if (Number.isFinite(parsed) && parsed > 0) {
      return Math.floor(parsed);
    }
  }
  return 0;
}

function queueTaskPopupConfigureDelete(item) {
  if (!queueTaskPopupDeleteBtn) {
    return;
  }
  const type = String(item?.type || "").trim().toLowerCase();
  const jobId = queueTaskPopupResolveJobId(item);
  if (!jobId) {
    queueTaskPopupDeleteBtn.setAttribute("hidden", "");
    return;
  }
  if (!["queue_job", "background_index", "analysis_interrupted"].includes(type)) {
    queueTaskPopupDeleteBtn.setAttribute("hidden", "");
    return;
  }
  const status = String(item?.status || "").trim().toLowerCase();
  queueTaskPopupDeleteBtn.textContent = status === "running" ? "Stop/Remove Queue Item" : "Delete Queue Item";
  queueTaskPopupDeleteBtn.removeAttribute("hidden");
}

async function deleteQueueItemFromPopup() {
  const item = queueTaskPopupCurrentItem;
  const jobId = queueTaskPopupResolveJobId(item);
  if (!jobId) {
    setStatus("No queue job selected to delete.", "error");
    return;
  }

  const status = String(item?.status || "").trim().toLowerCase();
  const running = status === "running";
  const confirmed = window.confirm(
    running
      ? `Job #${jobId} is running. Stop and remove it from queue tracking?`
      : `Delete queue item #${jobId}?`,
  );
  if (!confirmed) {
    return;
  }

  try {
    const payload = await fetchJson("/processes/queue/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_ids: [jobId],
        cancel_running: true,
      }),
    });

    const removed = Math.max(0, Number(payload?.removed_count || 0));
    const cancelledRunning = Math.max(0, Number(payload?.cancelled_running_count || 0));
    const msg = running
      ? `Queue item #${jobId} stop requested (${cancelledRunning} running cancelled, ${removed} removed).`
      : `Queue item #${jobId} deleted (${removed} removed).`;
    setStatus(msg, "ok");

    const activeCaseId = String(state.activeCaseId || "").trim();
    if (activeCaseId) {
      await syncBackgroundIndexStatus(activeCaseId);
      await Promise.all([
        syncAnalysisQueueStatus(activeCaseId, "face_people"),
        syncAnalysisQueueStatus(activeCaseId, "vehicles"),
      ]);
    }
    if (state.workspaceView === "queue") {
      await refreshReportQueue({ silent: true });
    }
    closeQueueTaskPopup();
  } catch (error) {
    const errorText = formatError(error);
    setStatus(`Delete queue item failed: ${errorText}`, "error");
    queueTaskPopupSetRecoveryStatus(`Delete queue item failed: ${errorText}`, "error");
  }
}

function queueTaskPopupUpdateRecoverySelectionMeta() {
  if (!queueTaskPopupSelectionMeta || !queueTaskPopupSelectAll) {
    return;
  }
  const context = queueTaskPopupRecoveryContext;
  if (!context || !Array.isArray(context.filenames)) {
    queueTaskPopupSelectionMeta.textContent = "0 selected";
    queueTaskPopupSelectAll.checked = false;
    queueTaskPopupSelectAll.indeterminate = false;
    return;
  }
  const total = context.filenames.length;
  const selectedCount = context.selected instanceof Set ? context.selected.size : 0;
  queueTaskPopupSelectionMeta.textContent = `${selectedCount} selected`;
  queueTaskPopupSelectAll.checked = total > 0 && selectedCount === total;
  queueTaskPopupSelectAll.indeterminate = selectedCount > 0 && selectedCount < total;
}

function syncQueueTaskPopupCheckboxesForFilename(filename, checked) {
  const safeFilename = String(filename || "").trim();
  if (!safeFilename || !queueTaskPopupFiles) {
    return;
  }
  const checkboxes = Array.from(queueTaskPopupFiles.querySelectorAll("input.queue-task-file-select"));
  checkboxes.forEach((checkbox) => {
    if (String(checkbox.dataset.filename || "").trim() === safeFilename) {
      checkbox.checked = Boolean(checked);
    }
  });
}

function queueTaskPopupConfigureRecovery(item, rows) {
  queueTaskPopupRecoveryContext = null;
  if (queueTaskPopupRecovery) {
    queueTaskPopupRecovery.setAttribute("hidden", "");
  }
  queueTaskPopupConfigureActionButtons({
    restart: false,
    cancel: false,
    removeFiles: false,
  });
  queueTaskPopupSetRecoveryStatus("", "");
  if (!queueTaskPopupRecovery || !isQueueTaskRecoveryAvailable(item)) {
    return;
  }
  const category = normalizeQueueTaskRecoveryCategory(item?.recovery_category);
  if (!category) {
    return;
  }
  const uniqueFilenames = [];
  const seen = new Set();
  (Array.isArray(rows) ? rows : []).forEach((row) => {
    const safe = String(row?.filename || "").trim();
    if (!safe || seen.has(safe)) {
      return;
    }
    seen.add(safe);
    uniqueFilenames.push(safe);
  });
  if (!uniqueFilenames.length) {
    return;
  }

  queueTaskPopupRecoveryContext = {
    mode: "analysis_recovery",
    caseId: String(item?.case_id || "").trim(),
    category,
    jobId: Math.max(0, Number(item?.queue_job_id || 0)),
    filenames: uniqueFilenames,
    selected: new Set(uniqueFilenames),
  };
  queueTaskPopupConfigureActionButtons({
    restart: true,
    cancel: true,
    removeFiles: false,
  });
  queueTaskPopupRecovery.removeAttribute("hidden");
  queueTaskPopupUpdateRecoverySelectionMeta();
  queueTaskPopupSetRecoveryStatus(
    `Interrupted ${analysisCategoryLabel(category)} analysis: select files to restart or cancel.`,
    "working",
  );
}

function queueTaskPopupConfigureFileRemoval(item, rows) {
  queueTaskPopupRecoveryContext = null;
  if (queueTaskPopupRecovery) {
    queueTaskPopupRecovery.setAttribute("hidden", "");
  }
  queueTaskPopupConfigureActionButtons({
    restart: false,
    cancel: false,
    removeFiles: false,
  });
  queueTaskPopupSetRecoveryStatus("", "");
  if (!queueTaskPopupRecovery || !isQueueTaskFileRemovalAvailable(item)) {
    return;
  }

  const uniqueFilenames = [];
  const seen = new Set();
  (Array.isArray(rows) ? rows : []).forEach((row) => {
    const safe = String(row?.filename || "").trim();
    if (!safe || seen.has(safe)) {
      return;
    }
    seen.add(safe);
    uniqueFilenames.push(safe);
  });
  if (!uniqueFilenames.length) {
    return;
  }

  queueTaskPopupRecoveryContext = {
    mode: "remove_queue_files",
    caseId: String(item?.case_id || "").trim(),
    category: "",
    jobId: Math.max(0, Number(item?.queue_job_id || 0)),
    filenames: uniqueFilenames,
    selected: new Set(uniqueFilenames),
  };
  queueTaskPopupConfigureActionButtons({
    restart: false,
    cancel: false,
    removeFiles: true,
  });
  queueTaskPopupRecovery.removeAttribute("hidden");
  queueTaskPopupUpdateRecoverySelectionMeta();
  queueTaskPopupSetRecoveryStatus(
    "Select queued files to remove from this queue item.",
    "working",
  );
}

function queueTaskProgressRowsFromItem(item) {
  const rawRows = Array.isArray(item?.file_progress) ? item.file_progress : [];
  if (!rawRows.length) {
    return [];
  }

  const output = [];
  rawRows.forEach((rawRow) => {
    if (!rawRow || typeof rawRow !== "object") {
      return;
    }
    const filename = String(rawRow.filename || "").trim();
    if (!filename) {
      return;
    }
    const status = String(rawRow.status || "").trim().toLowerCase();
    const processedFrames = Math.max(0, Number(rawRow.processed_frames || 0));
    const estimatedTotalFrames = Math.max(0, Number(rawRow.estimated_total_frames || 0));
    let progressPercent = Number(rawRow.progress_percent);
    if (!Number.isFinite(progressPercent)) {
      if (estimatedTotalFrames > 0) {
        progressPercent = (processedFrames / estimatedTotalFrames) * 100;
      } else {
        progressPercent = queueTaskProgressFromStageStatus(status, 0);
      }
    }
    progressPercent = clampPercent(progressPercent);

    let meta = `${Math.round(progressPercent)}%`;
    if (processedFrames > 0 || estimatedTotalFrames > 0) {
      const totalLabel = estimatedTotalFrames > 0 ? String(estimatedTotalFrames) : "?";
      meta += ` | frames: ${processedFrames}/${totalLabel}`;
    }
    if (Boolean(rawRow.is_current)) {
      meta += " | active";
    }

    output.push({
      filename,
      status: queueTaskStageStatusLabel(status),
      progressPercent,
      meta,
      analysisModeLabel: "",
      analysisModeKey: "",
    });
  });

  return expandQueueRowsByAnalysisModes(item, output);
}

function buildPipelineSnapshotMap(pipelinePayload) {
  const snapshots = Array.isArray(pipelinePayload?.pipelines) ? pipelinePayload.pipelines : [];
  const byFilename = new Map();
  snapshots.forEach((snapshot) => {
    if (!snapshot || typeof snapshot !== "object") {
      return;
    }
    const filename = String(snapshot.filename || "").trim();
    if (!filename) {
      return;
    }
    byFilename.set(filename, snapshot);
  });
  return byFilename;
}

function buildQueueTaskProgressRows(item, pipelinePayload) {
  const directRows = queueTaskProgressRowsFromItem(item);
  if (directRows.length) {
    return directRows;
  }

  const filenames = queueTaskFilenames(item);
  const byFilename = buildPipelineSnapshotMap(pipelinePayload);
  const stageName = queueTaskStageNameFromItem(item);
  const fallbackStatus = String(item?.status || "").trim().toLowerCase();
  const currentFilename = String(item?.current_filename || "").trim();
  const currentPercent = Number(item?.current_video_progress_percent || 0);
  const currentProcessedFrames = Math.max(0, Number(item?.current_video_processed_frames || 0));
  const currentTotalFrames = Math.max(0, Number(item?.current_video_total_frames || 0));

  const rows = filenames.map((filename) => {
    const snapshot = byFilename.get(filename);
    const stage = (
      snapshot
      && snapshot.stages
      && typeof snapshot.stages === "object"
      && stageName
      && snapshot.stages[stageName]
      && typeof snapshot.stages[stageName] === "object"
    )
      ? snapshot.stages[stageName]
      : null;

    let status = stage ? String(stage.status || "").trim().toLowerCase() : "";
    if (!status) {
      status = fallbackStatus || "pending";
    }

    const isCurrent = currentFilename && filename === currentFilename;
    const details = stage && stage.details && typeof stage.details === "object" ? stage.details : {};
    let processedFrames = Math.max(0, Number(details.processed_frames || 0));
    let estimatedTotalFrames = Math.max(0, Number(details.estimated_total_frames || 0));
    if (isCurrent) {
      processedFrames = Math.max(processedFrames, currentProcessedFrames);
      estimatedTotalFrames = Math.max(estimatedTotalFrames, currentTotalFrames);
    }
    if (estimatedTotalFrames > 0 && estimatedTotalFrames < processedFrames) {
      estimatedTotalFrames = processedFrames;
    }

    let progressPercent = Number(details.progress_percent);
    if (estimatedTotalFrames > 0) {
      progressPercent = (processedFrames / estimatedTotalFrames) * 100;
    } else if (!Number.isFinite(progressPercent)) {
      progressPercent = queueTaskProgressFromStageStatus(status, isCurrent ? currentPercent : 0);
    }
    progressPercent = clampPercent(progressPercent);

    let meta = `${Math.round(progressPercent)}%`;
    if (isCurrent && Number.isFinite(currentPercent) && currentPercent > 0) {
      meta = `${Math.round(clampPercent(currentPercent))}%`;
    }
    if (processedFrames > 0 || estimatedTotalFrames > 0) {
      const totalLabel = estimatedTotalFrames > 0 ? String(estimatedTotalFrames) : "?";
      meta += ` | frames: ${processedFrames}/${totalLabel}`;
    }
    if (isCurrent) {
      meta += " | active";
    }
    return {
      filename,
      status: queueTaskStageStatusLabel(status),
      progressPercent,
      meta,
      analysisModeLabel: "",
      analysisModeKey: "",
    };
  });
  return expandQueueRowsByAnalysisModes(item, rows);
}

function renderQueueTaskProgressRows(rows, options = {}) {
  if (!queueTaskPopupFiles) {
    return;
  }
  queueTaskPopupFiles.innerHTML = "";

  const list = Array.isArray(rows) ? rows : [];
  if (!list.length) {
    const li = document.createElement("li");
    li.className = "queue-task-file-row";
    const text = document.createElement("div");
    text.className = "queue-task-file-name";
    text.textContent = options.emptyMessage || "No file list reported yet.";
    li.appendChild(text);
    queueTaskPopupFiles.appendChild(li);
    return;
  }

  list.forEach((rowData) => {
    const li = document.createElement("li");
    li.className = "queue-task-file-row";

    const head = document.createElement("div");
    head.className = "queue-task-file-head";

    const name = document.createElement("div");
    name.className = "queue-task-file-name";
    name.textContent = String(rowData.filename || "");

    const status = document.createElement("div");
    status.className = "queue-task-file-status";
    status.textContent = String(rowData.status || "pending");

    const right = document.createElement("div");
    right.className = "queue-task-file-right";
    if (rowData.analysisModeLabel) {
      const mode = document.createElement("div");
      mode.className = "queue-task-file-mode";
      mode.classList.add(`mode-${String(rowData.analysisModeKey || "shared")}`);
      mode.textContent = String(rowData.analysisModeLabel);
      right.appendChild(mode);
    }
    right.appendChild(status);

    const selectable = Boolean(options.selectable);
    if (selectable) {
      const left = document.createElement("div");
      left.className = "queue-task-file-left";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "queue-task-file-select";
      checkbox.dataset.filename = String(rowData.filename || "");
      const selectedSet = options.selected instanceof Set ? options.selected : new Set();
      checkbox.checked = selectedSet.has(String(rowData.filename || ""));
      checkbox.addEventListener("change", () => {
        if (typeof options.onToggle === "function") {
          options.onToggle(String(rowData.filename || ""), Boolean(checkbox.checked));
        }
      });
      left.appendChild(checkbox);
      left.appendChild(name);
      head.appendChild(left);
    } else {
      head.appendChild(name);
    }
    head.appendChild(right);

    const track = document.createElement("div");
    track.className = "queue-task-file-track";

    const bar = document.createElement("div");
    bar.className = "queue-task-file-bar";
    const safePercent = clampPercent(rowData.progressPercent || 0);
    bar.style.width = `${safePercent.toFixed(1)}%`;
    track.appendChild(bar);

    const meta = document.createElement("div");
    meta.className = "queue-task-file-meta";
    meta.textContent = String(rowData.meta || `${Math.round(safePercent)}%`);

    li.appendChild(head);
    li.appendChild(track);
    li.appendChild(meta);
    queueTaskPopupFiles.appendChild(li);
  });
}

async function loadQueueTaskProgressRows(item) {
  const directRows = queueTaskProgressRowsFromItem(item);
  if (directRows.length) {
    return directRows;
  }

  const caseId = String(item?.case_id || "").trim();
  const filenames = queueTaskFilenames(item);
  if (!caseId || !filenames.length) {
    return buildQueueTaskProgressRows(item, { pipelines: [] });
  }
  const pipelinePayload = await fetchJson(withCaseQuery("/pipeline/status", caseId));
  return buildQueueTaskProgressRows(item, pipelinePayload);
}

function closeQueueTaskPopup() {
  if (!queueTaskPopup) {
    return;
  }
  queueTaskPopupLoadToken += 1;
  queueTaskPopup.classList.remove("open");
  queueTaskPopup.setAttribute("hidden", "");
  queueTaskPopupResetRecovery();
}

function openQueueTaskPopup(item) {
  if (!queueTaskPopup || !queueTaskPopupTitle || !queueTaskPopupMeta || !queueTaskPopupFiles) {
    return;
  }

  const type = String(item?.type || "").trim();
  const status = String(item?.status || "").trim() || "unknown";
  const caseId = String(item?.case_id || "").trim() || "n/a";
  const recoveryEnabled = isQueueTaskRecoveryAvailable(item);
  const fileRemovalEnabled = isQueueTaskFileRemovalAvailable(item);
  queueTaskPopupResetRecovery();
  queueTaskPopupCurrentItem = item && typeof item === "object" ? { ...item } : null;
  queueTaskPopupConfigureDelete(queueTaskPopupCurrentItem);

  if (type === "background_index") {
    queueTaskPopupTitle.textContent = "Background Index Worker";
    const completed = Math.max(0, Number(item?.completed || 0));
    const total = Math.max(0, Number(item?.total || 0));
    const progressPercent = Number(item?.progress_percent || 0);
    const startedLabel = formatQueueTimestamp(item?.started_at || item?.enqueued_at || "");
    queueTaskPopupMeta.textContent =
      `case: ${caseId} | status: ${status} | progress: ${completed}/${total} (${Number.isFinite(progressPercent) ? progressPercent.toFixed(1) : "0.0"}%) | started: ${startedLabel}`;
  } else if (type === "analysis_interrupted") {
    const queueJobId = Math.max(0, Number(item?.queue_job_id || 0));
    const categoryLabel = analysisCategoryLabel(item?.recovery_category);
    queueTaskPopupTitle.textContent = queueJobId > 0
      ? `Interrupted ${categoryLabel} Analysis #${queueJobId}`
      : `Interrupted ${categoryLabel} Analysis`;
    const filesCount = Math.max(0, Number(item?.filenames_count || 0));
    const interruptedMessage = String(item?.message || "").trim();
    const addedLabel = formatQueueTimestamp(item?.enqueued_at || "");
    queueTaskPopupMeta.textContent =
      `case: ${caseId} | status: interrupted | files: ${filesCount} | added: ${addedLabel}${interruptedMessage ? ` | ${interruptedMessage}` : ""}`;
  } else {
    const queueJobId = Math.max(0, Number(item?.queue_job_id || 0));
    const jobKindLabel = queueJobKindLabel(item?.job_kind, item);
    queueTaskPopupTitle.textContent = queueJobId > 0 ? `${jobKindLabel} #${queueJobId}` : jobKindLabel;

    const queuePosition = Math.max(0, Number(item?.queue_position || 0));
    const priority = Math.max(0, Number(item?.priority || 0));
    const attempts = Math.max(0, Number(item?.attempt_count || 0));
    const filesCount = Math.max(0, Number(item?.filenames_count || 0));
    const metadata = item?.metadata && typeof item.metadata === "object" ? item.metadata : {};
    const analysisModes = analysisModesLabelFromFlags(
      Boolean(metadata.analysis_face_people),
      Boolean(metadata.analysis_vehicles),
    );
    const analysisModePart = analysisModes ? ` | modes: ${analysisModes}` : "";
    const addedLabel = formatQueueTimestamp(item?.enqueued_at || "");
    queueTaskPopupMeta.textContent =
      `case: ${caseId} | status: ${status} | queue ahead: ${queuePosition} | priority: ${priority} | files: ${filesCount} | attempts: ${attempts} | added: ${addedLabel}${analysisModePart}`;
  }

  const filenames = queueTaskFilenames(item);
  renderQueueTaskProgressRows(
    filenames.map((filename) => ({
      filename,
      status: "loading",
      progressPercent: 0,
      meta: "Loading per-file progress...",
    })),
    {
      emptyMessage: "No file list reported yet.",
      selectable: recoveryEnabled || fileRemovalEnabled,
      selected: queueTaskPopupRecoveryContext?.selected || new Set(),
      onToggle: (filename, checked) => {
        const context = queueTaskPopupRecoveryContext;
        if (!context || !(context.selected instanceof Set)) {
          return;
        }
        if (checked) {
          context.selected.add(filename);
        } else {
          context.selected.delete(filename);
        }
        syncQueueTaskPopupCheckboxesForFilename(filename, checked);
        queueTaskPopupUpdateRecoverySelectionMeta();
      },
    },
  );

  queueTaskPopup.removeAttribute("hidden");
  queueTaskPopup.classList.add("open");

  const loadToken = ++queueTaskPopupLoadToken;
  void loadQueueTaskProgressRows(item)
    .then((rows) => {
      if (
        loadToken !== queueTaskPopupLoadToken
        || !queueTaskPopup
        || queueTaskPopup.hasAttribute("hidden")
      ) {
        return;
      }
      if (recoveryEnabled) {
        queueTaskPopupConfigureRecovery(item, rows);
      } else if (fileRemovalEnabled) {
        queueTaskPopupConfigureFileRemoval(item, rows);
      }
      renderQueueTaskProgressRows(rows, {
        emptyMessage: "No file list reported yet.",
        selectable: recoveryEnabled || fileRemovalEnabled,
        selected: queueTaskPopupRecoveryContext?.selected || new Set(),
        onToggle: (filename, checked) => {
          const context = queueTaskPopupRecoveryContext;
          if (!context || !(context.selected instanceof Set)) {
            return;
          }
          if (checked) {
            context.selected.add(filename);
          } else {
            context.selected.delete(filename);
          }
          syncQueueTaskPopupCheckboxesForFilename(filename, checked);
          queueTaskPopupUpdateRecoverySelectionMeta();
        },
      });
    })
    .catch((error) => {
      if (
        loadToken !== queueTaskPopupLoadToken
        || !queueTaskPopup
        || queueTaskPopup.hasAttribute("hidden")
      ) {
        return;
      }
      if (recoveryEnabled) {
        queueTaskPopupConfigureRecovery(item, filenames.map((filename) => ({ filename })));
      } else if (fileRemovalEnabled) {
        queueTaskPopupConfigureFileRemoval(item, filenames.map((filename) => ({ filename })));
      }
      renderQueueTaskProgressRows([], {
        emptyMessage: `Unable to load per-file progress: ${formatError(error)}`,
        selectable: recoveryEnabled || fileRemovalEnabled,
        selected: queueTaskPopupRecoveryContext?.selected || new Set(),
        onToggle: (filename, checked) => {
          const context = queueTaskPopupRecoveryContext;
          if (!context || !(context.selected instanceof Set)) {
            return;
          }
          if (checked) {
            context.selected.add(filename);
          } else {
            context.selected.delete(filename);
          }
          syncQueueTaskPopupCheckboxesForFilename(filename, checked);
          queueTaskPopupUpdateRecoverySelectionMeta();
        },
      });
    });
}

async function listInterruptedAnalysisQueueItems(caseId) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    return [];
  }

  const output = [];
  for (const category of ANALYSIS_CATEGORIES) {
    const normalizedCategory = normalizeAnalysisCategory(category);
    let payload = null;
    try {
      payload = await readAnalysisQueueStatus(normalizedCaseId, normalizedCategory);
    } catch (error) {
      console.warn(
        `Interrupted analysis status lookup failed for ${normalizedCategory}: ${formatError(error)}`,
      );
      continue;
    }
    if (!payload || typeof payload !== "object") {
      continue;
    }

    const status = String(payload.status || payload?.queue?.status || "").trim().toLowerCase();
    const filenames = activeCaseFilenamesFromPayload(payload);
    if (status !== "interrupted" || !filenames.length) {
      continue;
    }
    const queue = payload.queue && typeof payload.queue === "object" ? payload.queue : {};
    const analysis = payload.analysis && typeof payload.analysis === "object" ? payload.analysis : {};
    const facePeopleFilenames = Array.isArray(payload.analysis_face_people_filenames)
      ? payload.analysis_face_people_filenames
      : [];
    const vehiclesFilenames = Array.isArray(payload.analysis_vehicles_filenames)
      ? payload.analysis_vehicles_filenames
      : [];
    output.push({
      type: "analysis_interrupted",
      case_id: normalizedCaseId,
      status: "interrupted",
      queue_job_id: Number(queue.job_id || 0),
      job_kind: "analysis",
      queue_position: Number(queue.position_ahead || 0),
      priority: Number(queue.priority || 0),
      attempt_count: Number(queue.attempt_count || 0),
      enqueued_at: String(queue.enqueued_at || ""),
      filenames,
      filenames_count: filenames.length,
      metadata: {
        analysis_face_people: Boolean(analysis.face_people),
        analysis_vehicles: Boolean(analysis.vehicles),
        analysis_face_people_filenames: facePeopleFilenames,
        analysis_vehicles_filenames: vehiclesFilenames,
      },
      file_progress: Array.isArray(payload.file_progress) ? payload.file_progress : [],
      recovery_category: normalizedCategory,
      message: String(payload.message || ""),
    });
  }
  return output;
}

function renderReportQueueList(processesPayload) {
  if (!reportQueueList) {
    return;
  }
  reportQueueList.innerHTML = "";

  const processItems = Array.isArray(processesPayload?.processes) ? processesPayload.processes : [];
  if (!processItems.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No active background tasks.";
    reportQueueList.appendChild(empty);
    return;
  }

  processItems.forEach((item) => {
    const row = document.createElement("div");
    row.className = "report-queue-item";
    row.classList.add("clickable");
    row.tabIndex = 0;
    row.setAttribute("role", "button");
    row.setAttribute("aria-label", "Open queue task details");

    const head = document.createElement("div");
    head.className = "report-queue-item-head";

    const title = document.createElement("div");
    title.className = "report-queue-title";

    const badge = document.createElement("span");
    badge.className = "report-queue-badge";

    const type = String(item?.type || "").trim();
    const caseId = String(item?.case_id || "").trim() || "n/a";
    const status = String(item?.status || "").trim() || "unknown";

    if (type === "background_index") {
      title.textContent = "Background Index Worker";
      badge.textContent = status;
      const completed = Math.max(0, Number(item?.completed || 0));
      const total = Math.max(0, Number(item?.total || 0));
      const progress = Number(item?.progress_percent || 0);
      const meta = document.createElement("div");
      meta.className = "report-queue-meta";
      const filename = String(item?.current_filename || "").trim();
      const filePart = filename ? ` | file: ${filename}` : "";
      meta.textContent =
        `case: ${caseId} | progress: ${completed}/${total} (${Number.isFinite(progress) ? progress.toFixed(1) : "0.0"}%)${filePart}`;
      row.appendChild(meta);
    } else if (type === "analysis_interrupted") {
      const queueJobId = Math.max(0, Number(item?.queue_job_id || 0));
      const categoryLabel = analysisCategoryLabel(item?.recovery_category);
      title.textContent = queueJobId > 0
        ? `Interrupted ${categoryLabel} Analysis #${queueJobId}`
        : `Interrupted ${categoryLabel} Analysis`;
      badge.textContent = "interrupted";
      const filesCount = Math.max(0, Number(item?.filenames_count || 0));
      const interruptedMessage = String(item?.message || "").trim();
      const meta = document.createElement("div");
      meta.className = "report-queue-meta";
      meta.textContent =
        `case: ${caseId} | files: ${filesCount}${interruptedMessage ? ` | ${interruptedMessage}` : ""}`;
      row.appendChild(meta);
    } else {
      const queueJobId = Math.max(0, Number(item?.queue_job_id || 0));
      const jobKind = queueJobKindLabel(item?.job_kind, item);
      title.textContent = queueJobId > 0 ? `${jobKind} #${queueJobId}` : jobKind;
      badge.textContent = status;
      const queuePosition = Math.max(0, Number(item?.queue_position || 0));
      const priority = Math.max(0, Number(item?.priority || 0));
      const attempts = Math.max(0, Number(item?.attempt_count || 0));
      const filesCount = Math.max(0, Number(item?.filenames_count || 0));
      const preview = Array.isArray(item?.filenames_preview)
        ? item.filenames_preview
            .map((value) => String(value || "").trim())
            .filter((value) => value.length > 0)
        : [];
      const previewSuffix = preview.length ? ` | sample: ${preview.join(", ")}` : "";
      const meta = document.createElement("div");
      meta.className = "report-queue-meta";
      const metadata = item?.metadata && typeof item.metadata === "object" ? item.metadata : {};
      const analysisModes = analysisModesLabelFromFlags(
        Boolean(metadata.analysis_face_people),
        Boolean(metadata.analysis_vehicles),
      );
      const analysisModePart = analysisModes ? ` | modes: ${analysisModes}` : "";
      meta.textContent =
        `case: ${caseId} | queue ahead: ${queuePosition} | priority: ${priority} | files: ${filesCount} | attempts: ${attempts}${analysisModePart}${previewSuffix}`;
      row.appendChild(meta);
    }

    head.appendChild(title);
    head.appendChild(badge);
    row.prepend(head);

    const openDetails = () => {
      openQueueTaskPopup(item);
    };
    row.addEventListener("click", openDetails);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openDetails();
      }
    });

    reportQueueList.appendChild(row);
  });
}

function dedupeReportQueueItems(processItems) {
  const items = Array.isArray(processItems) ? processItems : [];
  if (!items.length) {
    return [];
  }

  const semanticQueueCaseIds = new Set(
    items
      .filter((item) => {
        const type = String(item?.type || "").trim().toLowerCase();
        const kind = String(item?.job_kind || "").trim().toLowerCase();
        return type === "queue_job" && kind === "semantic_index";
      })
      .map((item) => String(item?.case_id || "").trim())
      .filter((caseId) => caseId.length > 0),
  );

  if (!semanticQueueCaseIds.size) {
    return items;
  }

  return items.filter((item) => {
    const type = String(item?.type || "").trim().toLowerCase();
    if (type !== "background_index") {
      return true;
    }
    const caseId = String(item?.case_id || "").trim();
    if (!caseId) {
      return true;
    }
    // A semantic queue job card already carries the same runtime progress context.
    return !semanticQueueCaseIds.has(caseId);
  });
}

async function refreshReportQueue(options = {}) {
  const silent = Boolean(options?.silent);
  if (!reportQueueList) {
    return;
  }

  if (!silent) {
    setReportQueueStatus("Loading queue status...", "working");
  }

  const payload = await fetchJson("/processes");
  const processItemsRaw = Array.isArray(payload?.processes) ? payload.processes : [];
  const processItems = dedupeReportQueueItems(processItemsRaw);
  let interruptedItems = [];
  const activeCaseId = String(state.activeCaseId || "").trim();
  if (activeCaseId) {
    interruptedItems = await listInterruptedAnalysisQueueItems(activeCaseId);
  }
  const mergedItems = [...processItems, ...interruptedItems];
  const count = mergedItems.length;
  renderReportQueueList({
    ...payload,
    count,
    processes: mergedItems,
  });
  setReportQueueStatus(
    count > 0 ? `${count} active/recovery background task(s).` : "No active background tasks.",
    "ok",
  );
}

function queueTaskPopupSelectedFilenames() {
  const context = queueTaskPopupRecoveryContext;
  if (!context || !(context.selected instanceof Set)) {
    return [];
  }
  return Array.from(context.selected)
    .map((item) => String(item || "").trim())
    .filter((item) => item.length > 0);
}

async function restartInterruptedAnalysisFromPopup() {
  const context = queueTaskPopupRecoveryContext;
  if (!context) {
    return;
  }
  const caseId = String(context.caseId || "").trim();
  const category = normalizeQueueTaskRecoveryCategory(context.category);
  const filenames = queueTaskPopupSelectedFilenames();
  if (!caseId || !category) {
    queueTaskPopupSetRecoveryStatus("Recovery context is invalid.", "error");
    return;
  }
  if (!filenames.length) {
    queueTaskPopupSetRecoveryStatus("Select one or more files first.", "error");
    return;
  }
  const label = analysisCategoryLabel(category);
  const confirmed = window.confirm(`Restart ${label} analysis for ${filenames.length} selected interrupted file(s)?`);
  if (!confirmed) {
    return;
  }

  const frameInterval = Number.parseFloat(intervalInput?.value || "1");
  const safeFrameInterval = Number.isFinite(frameInterval) && frameInterval > 0 ? frameInterval : 2;
  try {
    queueTaskPopupSetRecoveryStatus(`Queueing restart for ${filenames.length} file(s)...`, "working");
    const payload = await fetchJson("/analysis/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        case_id: caseId,
        filenames,
        frame_interval_seconds: safeFrameInterval,
        batch_size: 32,
        force: false,
        analysis_face_people: category === "face_people",
        analysis_vehicles: category === "vehicles",
      }),
    });
    const queueJobId = Math.max(0, Number(payload?.queue?.job_id || payload?.job_id || 0));
    await syncAnalysisQueueStatus(caseId, category, { jobId: queueJobId });
    if (state.workspaceView === "queue") {
      await refreshReportQueue({ silent: true });
    }
    queueTaskPopupSetRecoveryStatus("Restart queued successfully.", "ok");
    closeQueueTaskPopup();
  } catch (error) {
    queueTaskPopupSetRecoveryStatus(`Restart failed: ${formatError(error)}`, "error");
  }
}

async function cancelInterruptedAnalysisFromPopup() {
  const context = queueTaskPopupRecoveryContext;
  if (!context) {
    return;
  }
  const caseId = String(context.caseId || "").trim();
  const category = normalizeQueueTaskRecoveryCategory(context.category);
  const filenames = queueTaskPopupSelectedFilenames();
  if (!caseId || !category) {
    queueTaskPopupSetRecoveryStatus("Recovery context is invalid.", "error");
    return;
  }
  if (!filenames.length) {
    queueTaskPopupSetRecoveryStatus("Select one or more files first.", "error");
    return;
  }
  const label = analysisCategoryLabel(category);
  const confirmed = window.confirm(`Cancel interrupted ${label} analysis for ${filenames.length} selected file(s)?`);
  if (!confirmed) {
    return;
  }

  try {
    queueTaskPopupSetRecoveryStatus(`Cancelling ${filenames.length} interrupted file(s)...`, "working");
    const payload = await fetchJson("/analysis/interrupted/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        case_id: caseId,
        category,
        filenames,
      }),
    });
    const cancelledCount = Math.max(0, Number(payload?.cancelled_count || 0));
    const alreadyResolvedCount = Math.max(0, Number((payload?.not_interrupted_filenames || []).length));
    const mismatchCount = Math.max(0, Number((payload?.skipped_filenames || []).length));
    await syncAnalysisQueueStatus(caseId, category);
    if (state.workspaceView === "queue") {
      await refreshReportQueue({ silent: true });
    }
    if (cancelledCount <= 0) {
      queueTaskPopupSetRecoveryStatus(
        `No files were cancelled. Already resolved: ${alreadyResolvedCount}, category-mismatched: ${mismatchCount}.`,
        "ok",
      );
      return;
    }
    queueTaskPopupSetRecoveryStatus(
      `Cancelled ${cancelledCount} file(s). Already resolved: ${alreadyResolvedCount}, category-mismatched: ${mismatchCount}.`,
      "ok",
    );
    closeQueueTaskPopup();
  } catch (error) {
    const errorText = formatError(error);
    if (/\[404\]\s*Not Found/i.test(errorText)) {
      queueTaskPopupSetRecoveryStatus(
        "Cancel failed: backend route is missing. Restart backend to load latest routes, then retry.",
        "error",
      );
      return;
    }
    queueTaskPopupSetRecoveryStatus(`Cancel failed: ${errorText}`, "error");
  }
}

async function removeSelectedQueueFilesFromPopup() {
  const context = queueTaskPopupRecoveryContext;
  if (!context || String(context.mode || "") !== "remove_queue_files") {
    return;
  }
  const jobId = Math.max(0, Number(context.jobId || 0));
  const filenames = queueTaskPopupSelectedFilenames();
  if (!jobId) {
    queueTaskPopupSetRecoveryStatus("Queue job is missing from popup context.", "error");
    return;
  }
  if (!filenames.length) {
    queueTaskPopupSetRecoveryStatus("Select one or more files first.", "error");
    return;
  }

  const confirmed = window.confirm(`Remove ${filenames.length} selected file(s) from queue job #${jobId}?`);
  if (!confirmed) {
    return;
  }

  try {
    queueTaskPopupSetRecoveryStatus(`Removing ${filenames.length} file(s) from queue...`, "working");
    const payload = await fetchJson("/processes/queue/remove_files", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: jobId,
        filenames,
      }),
    });

    const removedCount = Math.max(0, Number(payload?.removed_count || 0));
    const remainingCount = Math.max(0, Number(payload?.remaining_count || 0));
    const deletedJob = Boolean(payload?.deleted_job);
    const notFoundCount = Math.max(0, Number((payload?.not_found_filenames || []).length));
    const caseId = String(payload?.case_id || context.caseId || "").trim();

    if (caseId) {
      await syncBackgroundIndexStatus(caseId);
      await Promise.all([
        syncAnalysisQueueStatus(caseId, "face_people"),
        syncAnalysisQueueStatus(caseId, "vehicles"),
      ]);
    }
    if (state.workspaceView === "queue") {
      await refreshReportQueue({ silent: true });
    }

    const summary = deletedJob
      ? `Removed ${removedCount} file(s). Queue job deleted.`
      : `Removed ${removedCount} file(s). ${remainingCount} file(s) remain in queue item.`;
    const extra = notFoundCount > 0 ? ` (${notFoundCount} selection(s) were no longer present.)` : "";
    queueTaskPopupSetRecoveryStatus(`${summary}${extra}`, "ok");
    setStatus(`${summary}${extra}`, "ok");
    closeQueueTaskPopup();
  } catch (error) {
    const errorText = formatError(error);
    queueTaskPopupSetRecoveryStatus(`Remove selected failed: ${errorText}`, "error");
    setStatus(`Remove selected failed: ${errorText}`, "error");
  }
}

function stopReportQueuePolling() {
  reportQueuePollToken += 1;
}

function startReportQueuePolling() {
  stopReportQueuePolling();
  const pollToken = ++reportQueuePollToken;

  const poll = async () => {
    if (pollToken !== reportQueuePollToken) {
      return;
    }
    if (state.workspaceView !== "queue") {
      return;
    }
    if (!state.activeCaseId) {
      return;
    }
    try {
      await refreshReportQueue({ silent: true });
    } catch (error) {
      setReportQueueStatus(`Queue refresh failed: ${formatError(error)}`, "error");
    }
    if (pollToken !== reportQueuePollToken) {
      return;
    }
    window.setTimeout(poll, 1500);
  };

  void poll();
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
  const queueActive = state.workspaceView === "queue" && Boolean(state.activeCaseId);
  workspace?.classList.toggle("show-settings", settingsActive);
  workspace?.classList.toggle("show-report", reportActive);
  workspace?.classList.toggle("show-queue", queueActive);
  if (workspaceSettingsPage) {
    workspaceSettingsPage.hidden = !settingsActive;
  }
  if (workspaceReportPage) {
    workspaceReportPage.hidden = !reportActive;
  }
  if (workspaceQueuePage) {
    workspaceQueuePage.hidden = !queueActive;
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
    const analysisActive = !settingsActive && !reportActive && !queueActive && Boolean(state.activeCaseId);
    workspaceAnalysisBtn.classList.toggle("active", analysisActive);
    workspaceAnalysisBtn.setAttribute("aria-pressed", analysisActive ? "true" : "false");
  }
  if (workspaceQueueBtn) {
    workspaceQueueBtn.classList.toggle("active", queueActive);
    workspaceQueueBtn.setAttribute("aria-pressed", queueActive ? "true" : "false");
  }
  if (!queueActive) {
    closeQueueTaskPopup();
  }

  if (queueActive) {
    startReportQueuePolling();
  } else {
    stopReportQueuePolling();
  }
}

function setWorkspaceView(viewKey) {
  if (viewKey === "settings") {
    state.workspaceView = "settings";
  } else if (viewKey === "queue") {
    state.workspaceView = "queue";
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

function buildResumableSourceKey(file) {
  const name = String(file?.name || "").trim();
  const size = Math.max(0, Number(file?.size || 0));
  const lastModified = Math.max(0, Number(file?.lastModified || 0));
  return `${name}::${size}::${lastModified}`;
}

function getSavedResumableUploadState() {
  try {
    const raw = window.localStorage.getItem(RESUMABLE_UPLOAD_STATE_KEY);
    if (!raw) {
      return null;
    }
    const payload = JSON.parse(raw);
    if (!payload || typeof payload !== "object") {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

function saveResumableUploadState(payload) {
  try {
    window.localStorage.setItem(
      RESUMABLE_UPLOAD_STATE_KEY,
      JSON.stringify(payload || {}),
    );
  } catch {
    // Ignore storage errors.
  }
}

function clearResumableUploadState() {
  try {
    window.localStorage.removeItem(RESUMABLE_UPLOAD_STATE_KEY);
  } catch {
    // Ignore storage errors.
  }
}

function normalizeSessionFiles(rawFiles) {
  const list = Array.isArray(rawFiles) ? rawFiles : [];
  const normalized = [];
  for (const item of list) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const fileId = String(item.file_id || "").trim();
    const sourceFilename = String(item.source_filename || "").trim();
    const sourceKey = String(item.source_key || "").trim();
    if (!fileId || !sourceFilename || !sourceKey) {
      continue;
    }
    normalized.push({
      file_id: fileId,
      source_filename: sourceFilename,
      source_key: sourceKey,
      source_size: Math.max(0, Number(item.source_size || 0)),
      source_index: Math.max(0, Number(item.source_index || 0)),
      total_chunks: Math.max(1, Number(item.total_chunks || 1)),
      received_chunks: Math.max(0, Number(item.received_chunks || 0)),
      received_bytes: Math.max(0, Number(item.received_bytes || 0)),
      status: String(item.status || ""),
    });
  }
  return normalized;
}

function doesResumeStateMatchFiles(resumeState, caseId, files) {
  if (!resumeState || typeof resumeState !== "object") {
    return false;
  }
  const resumeCaseId = String(resumeState.case_id || "").trim();
  if (!resumeCaseId || resumeCaseId !== String(caseId || "").trim()) {
    return false;
  }
  const resumeKeys = Array.isArray(resumeState.source_keys)
    ? resumeState.source_keys.map((item) => String(item || "").trim()).filter(Boolean).sort()
    : [];
  if (!resumeKeys.length || resumeKeys.length !== files.length) {
    return false;
  }
  const fileKeys = files.map((file) => buildResumableSourceKey(file)).sort();
  if (fileKeys.length !== resumeKeys.length) {
    return false;
  }
  for (let i = 0; i < fileKeys.length; i += 1) {
    if (fileKeys[i] !== resumeKeys[i]) {
      return false;
    }
  }
  return true;
}

async function resolveResumableUploadSession(caseId, files) {
  const normalizedCaseId = String(caseId || "").trim();
  if (!normalizedCaseId) {
    throw new Error("No active case available.");
  }
  const safeFiles = Array.isArray(files) ? files : [];
  if (!safeFiles.length) {
    throw new Error("No files selected.");
  }

  const resumeState = getSavedResumableUploadState();
  if (doesResumeStateMatchFiles(resumeState, normalizedCaseId, safeFiles)) {
    const resumeSessionId = String(resumeState.session_id || "").trim();
    if (resumeSessionId) {
      try {
        const statusPayload = await fetchJson(
          `/upload_session/status?session_id=${encodeURIComponent(resumeSessionId)}`,
        );
        const statusCaseId = String(statusPayload.case_id || "").trim();
        if (statusCaseId === normalizedCaseId) {
          const statusFiles = normalizeSessionFiles(statusPayload.files);
          if (statusFiles.length) {
            return {
              session: statusPayload,
              files: statusFiles,
              resumed: true,
            };
          }
        }
      } catch {
        clearResumableUploadState();
      }
    }
  }

  const startPayload = await fetchJson("/upload_session/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      case_id: normalizedCaseId,
      chunk_size_bytes: DEFAULT_RESUMABLE_CHUNK_SIZE_BYTES,
      files: safeFiles.map((file, sourceIndex) => ({
        source_index: sourceIndex,
        source_filename: String(file.name || ""),
        source_size: Math.max(0, Number(file.size || 0)),
        source_last_modified_ms: Math.max(0, Number(file.lastModified || 0)),
        source_key: buildResumableSourceKey(file),
      })),
    }),
  });

  const sessionId = String(startPayload.session_id || "").trim();
  if (!sessionId) {
    throw new Error("Invalid upload session response: missing session_id");
  }
  const sessionFiles = normalizeSessionFiles(startPayload.files);
  if (!sessionFiles.length) {
    throw new Error("Upload session created without file entries");
  }

  saveResumableUploadState({
    session_id: sessionId,
    case_id: normalizedCaseId,
    source_keys: safeFiles.map((file) => buildResumableSourceKey(file)),
    created_at: Date.now(),
  });

  return {
    session: startPayload,
    files: sessionFiles,
    resumed: false,
  };
}

async function postResumableChunkWithRetry({
  sessionId,
  fileId,
  chunkIndex,
  totalChunks,
  payload,
}) {
  const chunkBody = payload instanceof Blob ? payload : new Blob([payload || new Uint8Array(0)]);
  let lastError = null;
  for (let attempt = 1; attempt <= RESUMABLE_UPLOAD_CHUNK_RETRIES; attempt += 1) {
    try {
      const response = await fetch(
        `/upload_session/chunk?session_id=${encodeURIComponent(sessionId)}&file_id=${encodeURIComponent(fileId)}&chunk_index=${chunkIndex}&total_chunks=${totalChunks}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream" },
          body: chunkBody,
        },
      );
      const rawBody = await response.text();
      let parsed = null;
      if (rawBody) {
        try {
          parsed = JSON.parse(rawBody);
        } catch {
          parsed = null;
        }
      }
      if (!response.ok) {
        const detail = parsed && typeof parsed === "object"
          ? formatError(parsed.detail ?? parsed)
          : rawBody || response.statusText || "chunk upload failed";
        throw new Error(`[${response.status}] ${detail}`);
      }
      if (!parsed || typeof parsed !== "object") {
        throw new Error(`[${response.status}] Invalid JSON response`);
      }
      return parsed;
    } catch (error) {
      lastError = error;
      if (attempt < RESUMABLE_UPLOAD_CHUNK_RETRIES) {
        await sleep(RESUMABLE_UPLOAD_RETRY_DELAY_MS * attempt);
      }
    }
  }
  throw new Error(`Chunk upload failed after retries: ${formatError(lastError)}`);
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

function updateSearchDedupeAggressivenessUi(value) {
  const normalized = normalizeDedupeAggressiveness(value, 55);
  if (searchDedupeAggressivenessInput) {
    searchDedupeAggressivenessInput.value = String(Math.round(normalized));
  }
  if (searchDedupeAggressivenessValue) {
    searchDedupeAggressivenessValue.textContent = String(Math.round(normalized));
  }
}

function renderSearchSettings(payload) {
  const settingsPayload = payload && typeof payload === "object" ? payload : {};
  const savedRaw = settingsPayload.saved && typeof settingsPayload.saved === "object"
    ? settingsPayload.saved
    : {};
  const recommendedRaw = settingsPayload.recommended && typeof settingsPayload.recommended === "object"
    ? settingsPayload.recommended
    : {};
  const derivedRaw = settingsPayload.derived && typeof settingsPayload.derived === "object"
    ? settingsPayload.derived
    : {};

  const saved = {
    score_threshold: normalizeScoreThreshold(savedRaw.score_threshold, 0.22),
    dedupe_aggressiveness: normalizeDedupeAggressiveness(savedRaw.dedupe_aggressiveness, 55),
    result_limit: normalizeResultLimit(savedRaw.result_limit, 120),
  };
  const recommended = {
    score_threshold: normalizeScoreThreshold(recommendedRaw.score_threshold, 0.22),
    dedupe_aggressiveness: normalizeDedupeAggressiveness(recommendedRaw.dedupe_aggressiveness, 55),
    result_limit: normalizeResultLimit(recommendedRaw.result_limit, 120),
  };

  state.searchSettings = {
    saved,
    recommended,
    derived: derivedRaw,
  };

  if (searchThresholdSettingInput) {
    searchThresholdSettingInput.value = saved.score_threshold.toFixed(2);
  }
  if (searchResultLimitInput) {
    searchResultLimitInput.value = String(saved.result_limit);
  }
  updateSearchDedupeAggressivenessUi(saved.dedupe_aggressiveness);
  setThresholdUiValue(saved.score_threshold);

  if (searchSettingsHint) {
    searchSettingsHint.textContent = `Recommended: threshold ${recommended.score_threshold.toFixed(2)}, dedupe ${Math.round(recommended.dedupe_aggressiveness)}, result limit ${recommended.result_limit}.`;
  }

  const nearDup = Number(derivedRaw.near_duplicate_seconds);
  const perVideoCap = Number(derivedRaw.per_video_cap);
  const settingsSummary = [
    `Saved threshold ${saved.score_threshold.toFixed(2)}`,
    `dedupe ${Math.round(saved.dedupe_aggressiveness)}`,
    `limit ${saved.result_limit}`,
  ];
  if (Number.isFinite(nearDup) && nearDup > 0) {
    settingsSummary.push(`near-dup ${nearDup.toFixed(2)}s`);
  }
  if (Number.isFinite(perVideoCap) && perVideoCap > 0) {
    settingsSummary.push(`per-video cap ${Math.round(perVideoCap)}`);
  }
  setSearchSettingsStatus(settingsSummary.join(" | "), "ok");
}

async function loadSearchSettings() {
  if (!scoreThresholdInput) {
    return;
  }
  try {
    const payload = await fetchJson("/settings/search");
    renderSearchSettings(payload);
  } catch (error) {
    state.searchSettings = {
      saved: {
        score_threshold: 0.22,
        dedupe_aggressiveness: 55,
        result_limit: 120,
      },
      recommended: {
        score_threshold: 0.22,
        dedupe_aggressiveness: 55,
        result_limit: 120,
      },
      derived: {},
    };
    setThresholdUiValue(0.22);
    setSearchSettingsStatus(`Search settings unavailable: ${formatError(error)}`, "error");
  }
}

async function saveSearchSettings() {
  if (!searchThresholdSettingInput || !searchDedupeAggressivenessInput || !searchResultLimitInput) {
    return;
  }

  const scoreThreshold = normalizeScoreThreshold(searchThresholdSettingInput.value, 0.22);
  const dedupeAggressiveness = normalizeDedupeAggressiveness(searchDedupeAggressivenessInput.value, 55);
  const resultLimit = normalizeResultLimit(searchResultLimitInput.value, 120);

  try {
    setSearchSettingsStatus("Saving search settings...", "working");
    const payload = await fetchJson("/settings/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        score_threshold: scoreThreshold,
        dedupe_aggressiveness: dedupeAggressiveness,
        result_limit: resultLimit,
      }),
    });
    renderSearchSettings(payload);
    setSearchSettingsStatus("Search settings saved.", "ok");
  } catch (error) {
    setSearchSettingsStatus(`Search settings save failed: ${formatError(error)}`, "error");
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
    stopAnalysisStatusPolling();
    hideTaskProgressUi();
    hideQueueSummaryButtons();
  }
  if (appShell) {
    appShell.classList.toggle("repository-mode", !hasActiveCase);
    appShell.classList.toggle("workspace-mode", hasActiveCase);
  }
  if (!hasActiveCase && state.workspaceView !== "analysis") {
    state.workspaceView = "analysis";
  }
  applyWorkspaceView();
  if (hasActiveCase) {
    refreshQueueSummaryButtonsForActiveCase();
  }
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
    stopAnalysisStatusPolling();
    hideTaskProgressUi();
    setWorkspaceView("analysis");
    syncWorkspaceVisibility();
    return;
  }
  saveActiveCasePlaybackSnapshot();
  stopBackgroundIndexPolling();
  stopAnalysisStatusPolling();
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

function normalizeResultLimit(value, fallback = 120) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(10, Math.min(500, parsed));
}

function normalizeScoreThreshold(value, fallback = 0.22) {
  const parsed = Number.parseFloat(String(value ?? ""));
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(-1, Math.min(1, parsed));
}

function normalizeDedupeAggressiveness(value, fallback = 55) {
  const parsed = Number.parseFloat(String(value ?? ""));
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(0, Math.min(100, parsed));
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

function getSavedSearchSettings() {
  const payload = state.searchSettings && typeof state.searchSettings === "object"
    ? state.searchSettings
    : {};
  return payload.saved && typeof payload.saved === "object"
    ? payload.saved
    : {};
}

function defaultSearchThreshold() {
  const saved = getSavedSearchSettings();
  if (saved && saved.score_threshold !== undefined) {
    return normalizeScoreThreshold(saved.score_threshold, 0.22);
  }
  if (scoreThresholdInput) {
    const fromDefault = normalizeScoreThreshold(scoreThresholdInput.defaultValue, NaN);
    if (Number.isFinite(fromDefault)) {
      return fromDefault;
    }
    const fromAttr = normalizeScoreThreshold(scoreThresholdInput.getAttribute("value"), NaN);
    if (Number.isFinite(fromAttr)) {
      return fromAttr;
    }
  }
  return 0.22;
}

function defaultSearchResultLimit() {
  const saved = getSavedSearchSettings();
  if (saved && saved.result_limit !== undefined) {
    return normalizeResultLimit(saved.result_limit, 120);
  }
  return 120;
}

function formatThresholdValue(value) {
  const normalized = normalizeScoreThreshold(value, defaultSearchThreshold());
  return normalized.toFixed(2);
}

function setThresholdUiValue(value) {
  const normalized = normalizeScoreThreshold(value, defaultSearchThreshold());
  if (scoreThresholdInput) {
    scoreThresholdInput.value = normalized.toFixed(2);
  }
  if (scoreThresholdValue) {
    scoreThresholdValue.textContent = normalized.toFixed(2);
  }
}

function searchKey(query, threshold, resultLimit) {
  const thresholdKey = normalizeScoreThreshold(threshold, defaultSearchThreshold()).toFixed(2);
  const limitKey = normalizeResultLimit(resultLimit, defaultSearchResultLimit());
  return `${query}\u0000${thresholdKey}\u0000${limitKey}`;
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

function cacheSearchResults(caseId, query, threshold, resultLimit, results, count) {
  const caseCache = ensureCaseSearchCache(caseId);
  if (!caseCache) {
    return;
  }
  const normalizedQuery = String(query || "").trim();
  const normalizedThreshold = normalizeScoreThreshold(threshold, defaultSearchThreshold());
  const normalizedResultLimit = normalizeResultLimit(resultLimit, defaultSearchResultLimit());
  const key = searchKey(normalizedQuery, normalizedThreshold, normalizedResultLimit);
  const normalizedResults = Array.isArray(results) ? results : [];
  caseCache.entries.set(key, {
    query: normalizedQuery,
    threshold: normalizedThreshold,
    resultLimit: normalizedResultLimit,
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
  setThresholdUiValue(defaultSearchThreshold());
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
  setThresholdUiValue(cached.threshold);
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

function isPlayerTargetingVideo(player, caseId, filename) {
  if (!player) {
    return false;
  }
  const normalizedCaseId = String(caseId || "").trim();
  const normalizedFilename = String(filename || "").trim();
  if (!normalizedCaseId || !normalizedFilename) {
    return false;
  }
  return (
    String(player.dataset.caseId || "").trim() === normalizedCaseId
    && String(player.dataset.filename || "").trim() === normalizedFilename
  );
}

async function releaseVideoPlaybackLocks(caseId, filename) {
  const normalizedCaseId = String(caseId || "").trim();
  const normalizedFilename = String(filename || "").trim();
  if (!normalizedCaseId || !normalizedFilename) {
    return false;
  }

  let released = false;
  if (isPlayerTargetingVideo(videoPlayer, normalizedCaseId, normalizedFilename)) {
    resetPlayerForCase(normalizedCaseId);
    setCaseUrl(normalizedCaseId);
    released = true;
  }

  const auxMatched = [
    triagePlayer,
    facePeoplePlayer,
    vehiclePlayer,
    semanticPopupVideo,
  ].some((player) => isPlayerTargetingVideo(player, normalizedCaseId, normalizedFilename));

  if (auxMatched) {
    resetAuxPlayers(normalizedCaseId);
    released = true;
  }

  if (released) {
    await new Promise((resolve) => window.setTimeout(resolve, 180));
  }
  return released;
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
    caseButton.title = `${item.name} (${item.case_id})`;

    const caseId = document.createElement("span");
    caseId.className = "case-item-id";
    caseId.textContent = item.case_id;
    caseId.title = item.case_id;

    caseButton.appendChild(caseName);
    caseButton.appendChild(caseId);
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
  for (const cachedCaseId of videoSelectionByCase.keys()) {
    if (!validCaseIds.has(cachedCaseId)) {
      videoSelectionByCase.delete(cachedCaseId);
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
  for (const cachedCaseId of backgroundIndexStatusByCase.keys()) {
    if (!validCaseIds.has(cachedCaseId)) {
      backgroundIndexStatusByCase.delete(cachedCaseId);
    }
  }
  for (const category of ANALYSIS_CATEGORIES) {
    const cache = analysisStatusCacheMap(category);
    if (!(cache instanceof Map)) {
      continue;
    }
    for (const cachedCaseId of cache.keys()) {
      if (!validCaseIds.has(cachedCaseId)) {
        cache.delete(cachedCaseId);
      }
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
  const list = Array.isArray(videos) ? videos : [];
  const activeCaseId = String(state.activeCaseId || "").trim();
  const caseSelection = getCaseVideoSelection(activeCaseId);

  if (!videoList) {
    renderExistingIndexSelectionList(list);
    syncVideoSelectionControls(list);
    return;
  }
  videoList.innerHTML = "";
  if (!list.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No uploaded videos yet.";
    videoList.appendChild(empty);
    clearVideoSelection(activeCaseId);
    renderExistingIndexSelectionList(list);
    syncVideoSelectionControls(list);
    return;
  }

  const availableFilenames = new Set(normalizeVideoFilenames(list));
  if (caseSelection instanceof Set) {
    for (const filename of Array.from(caseSelection)) {
      if (!availableFilenames.has(filename)) {
        caseSelection.delete(filename);
      }
    }
  }

  list.forEach((video) => {
    const filename = String(video?.filename || "").trim();
    const isSelected = Boolean(caseSelection instanceof Set && caseSelection.has(filename));
    const row = document.createElement("div");
    row.className = "video-row";
    row.classList.toggle("selected", isSelected);

    const selectCell = document.createElement("div");
    selectCell.className = "video-select-cell";

    const selectInput = document.createElement("input");
    selectInput.type = "checkbox";
    selectInput.className = "video-select-checkbox";
    selectInput.dataset.filename = filename;
    selectInput.checked = isSelected;
    selectInput.title = `Select ${filename}`;
    selectInput.setAttribute("aria-label", `Select ${filename}`);
    selectInput.addEventListener("change", () => {
      const selection = getCaseVideoSelection(activeCaseId);
      if (!(selection instanceof Set)) {
        return;
      }
      if (selectInput.checked) {
        selection.add(filename);
      } else {
        selection.delete(filename);
      }
      row.classList.toggle("selected", selectInput.checked);
      syncVideoSelectionControls(list);
    });
    selectCell.appendChild(selectInput);

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
      playFromVideoList(video);
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

    row.appendChild(selectCell);
    row.appendChild(meta);
    row.appendChild(actions);
    videoList.appendChild(row);
  });
  renderExistingIndexSelectionList(list);
  syncVideoSelectionControls(list);
}

function playFromVideoList(video) {
  if (!video || !state.activeCaseId) {
    return;
  }
  const caseId = String(state.activeCaseId || "").trim();
  const filename = String(video.filename || "").trim();
  if (!caseId || !filename) {
    return;
  }

  const fallbackVideoUrl = `/media/cases/${encodeURIComponent(caseId)}/videos/${encodeURIComponent(filename)}`;
  const videoUrl = String(video.video_url || fallbackVideoUrl);

  // Video list belongs to triage workflow, so route playback to triage player.
  triageSelection.set(caseId, filename);
  renderTriagePanels();

  if (triagePlayer && triagePlayerMeta) {
    playInPlayer(
      triagePlayer,
      triagePlayerMeta,
      filename,
      videoUrl,
      0,
      { autoPlay: true },
    );
    updateTriageTimelinePlayheads(0);
  }

  // Keep semantic player synchronized but paused to avoid hidden background playback.
  playVideoAt(filename, videoUrl, 0, { autoPlay: false });

  void loadTriageForVideo(caseId, filename, false).then(() => {
    if (
      state.activeCaseId === caseId
      && String(triageSelection.get(caseId) || "").trim() === filename
    ) {
      renderTriagePanels();
    }
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

function isVideoTriageReady(video) {
  if (!video || typeof video !== "object") {
    return false;
  }

  const mediaContract = video.media_contract;
  if (mediaContract && typeof mediaContract === "object") {
    const lifecycle = mediaContract.lifecycle;
    if (lifecycle && typeof lifecycle === "object" && lifecycle.triage_ready === true) {
      return true;
    }
  }

  const pipeline = video.pipeline;
  if (!pipeline || typeof pipeline !== "object") {
    return false;
  }
  const stages = pipeline.stages;
  if (!stages || typeof stages !== "object") {
    return false;
  }
  const triageStage = stages.triage;
  if (!triageStage || typeof triageStage !== "object") {
    return false;
  }
  const status = String(triageStage.status || "").trim().toLowerCase();
  return status === "completed" || status === "skipped";
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
    const triageReady = isVideoTriageReady(video);
    const sub = document.createElement("div");
    sub.className = "triage-video-sub";
    if (cached) {
      const durationLabel = formatTime(Number(cached.duration_seconds || 0));
      sub.textContent = `Ready | ${durationLabel}`;
    } else if (loading) {
      sub.textContent = "Loading timeline...";
    } else if (triageReady) {
      sub.textContent = "Ready";
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
  const triageReady = isVideoTriageReady(selectedVideo);

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
  } else if (triageReady) {
    sub.textContent = "Ready (click Refresh Timelines to load now)";
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
    try {
      const persisted = await fetchJson("/triage_timeline_cached", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: normalizedCaseId,
          filename: normalizedFilename,
          bucket_seconds: 1.0,
          force: false,
        }),
      });
      const cacheStatus = String(persisted?.cache_status || "").toLowerCase();
      if (cacheStatus === "hit" || persisted?.cached === true) {
        setTriagePayload(normalizedCaseId, normalizedFilename, persisted);
        triageErrors.delete(key);
        if (normalizedCaseId === state.activeCaseId) {
          renderTriagePanels();
        }
        return persisted;
      }
    } catch (error) {
      const message = formatError(error);
      if (
        message.includes("[404]")
        || message.includes("[400]")
      ) {
        triageErrors.set(key, message);
        if (normalizedCaseId === state.activeCaseId) {
          renderTriagePanels();
        }
        return null;
      }
    }
  }

  triageLoading.add(key);
  if (normalizedCaseId === state.activeCaseId) {
    renderTriagePanels();
  }
  let deferLoadingClear = false;
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
    const cacheStatus = String(payload?.cache_status || "").toLowerCase();
    if (cacheStatus === "queued" || payload?.queued === true) {
      deferLoadingClear = true;
      triageErrors.delete(key);
      if (normalizedCaseId === state.activeCaseId) {
        renderTriagePanels();
      }
      void (async () => {
        const maxAttempts = 240;
        for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
          await new Promise((resolve) => {
            window.setTimeout(resolve, 1000);
          });
          try {
            const persisted = await fetchJson("/triage_timeline_cached", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                case_id: normalizedCaseId,
                filename: normalizedFilename,
                bucket_seconds: 1.0,
                force: false,
              }),
            });
            const persistedStatus = String(persisted?.cache_status || "").toLowerCase();
            if (persistedStatus === "hit" || persisted?.cached === true) {
              setTriagePayload(normalizedCaseId, normalizedFilename, persisted);
              triageErrors.delete(key);
              triageLoading.delete(key);
              if (normalizedCaseId === state.activeCaseId) {
                renderTriagePanels();
              }
              return;
            }
          } catch (error) {
            const message = formatError(error);
            if (message.includes("[404]") || message.includes("[400]")) {
              triageErrors.set(key, message);
              triageLoading.delete(key);
              if (normalizedCaseId === state.activeCaseId) {
                renderTriagePanels();
              }
              return;
            }
          }
        }
        triageLoading.delete(key);
        triageErrors.set(key, "Timed out waiting for timeline job. Try Refresh Timelines.");
        if (normalizedCaseId === state.activeCaseId) {
          renderTriagePanels();
        }
      })();
      return payload;
    }

    setTriagePayload(normalizedCaseId, normalizedFilename, payload);
    triageErrors.delete(key);
    return payload;
  } catch (error) {
    triageErrors.set(key, formatError(error));
    return null;
  } finally {
    if (!deferLoadingClear) {
      triageLoading.delete(key);
    }
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
  setTriageStatus(`Loading triage timelines for ${selected}...`, "working");
  const payload = await loadTriageForVideo(caseId, selected, force);
  if (refreshToken !== triageRefreshToken || caseId !== state.activeCaseId) {
    return;
  }
  if (!payload) {
    setTriageStatus(`Failed to build timelines for ${selected}.`, "error");
    return;
  }
  const cacheStatus = String(payload.cache_status || "").toLowerCase();
  if (cacheStatus === "queued" || payload.queued === true) {
    setTriageStatus(`Timeline queued for ${selected}. Waiting for worker...`, "working");
    return;
  }
  if (cacheStatus === "hit" || payload.cached === true) {
    setTriageStatus(`Triage loaded from saved cache for ${selected}.`, "ok");
  } else {
    setTriageStatus(`Triage ready for ${selected}.`, "ok");
  }
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
    renderWall(suspectWall, [], "Select a case first.", facePeoplePlayer, facePeoplePlayerMeta);
    renderWall(faceWall, [], "Select a case first.", facePeoplePlayer, facePeoplePlayerMeta);
    renderWall(peopleWall, [], "Select a case first.", facePeoplePlayer, facePeoplePlayerMeta);
    renderWall(vehicleWall, [], "Select a case first.", vehiclePlayer, vehiclePlayerMeta);
    setSuspectStatus("Select a case first.", "error");
    return;
  }
  await Promise.all([refreshFacePeopleWall(), refreshVehicleWall()]);
}

function resetSuspectSearchView() {
  renderWall(
    suspectWall,
    [],
    "Upload a probe image and click Search By Photo.",
    facePeoplePlayer,
    facePeoplePlayerMeta,
  );
  setSuspectStatus("Upload a probe image, then run suspect search.", "");
}

async function runSuspectPhotoSearch() {
  let caseId = "";
  try {
    caseId = ensureActiveCaseId();
  } catch (error) {
    setSuspectStatus(formatError(error), "error");
    return;
  }

  const probeFile = suspectProbeInput?.files?.[0];
  if (!probeFile) {
    setSuspectStatus("Select a probe image first.", "error");
    return;
  }

  const selectedMode = String(suspectModeSelect?.value || "auto").trim().toLowerCase() || "auto";
  try {
    setSuspectStatus("Running suspect photo search...", "working");
    const formData = new FormData();
    formData.append("case_id", caseId);
    formData.append("mode", selectedMode);
    formData.append("top_k", "180");
    formData.append("probe_image", probeFile);

    const payload = await fetchJson("/suspect_photo_search", {
      method: "POST",
      body: formData,
    });

    const results = Array.isArray(payload?.results) ? payload.results : [];
    renderWall(
      suspectWall,
      results,
      "No suspect sightings matched this probe image.",
      facePeoplePlayer,
      facePeoplePlayerMeta,
    );

    const modeUsed = String(payload?.mode_used || selectedMode || "auto");
    const faceDetected = Boolean(payload?.face_detected);
    const count = Math.max(0, Number(payload?.count || results.length || 0));
    const faceHint = faceDetected ? "face detected" : "no face detected";
    const engineUsed = String(payload?.engine_used || "clip");
    const fallbackUsed = Boolean(payload?.fallback_used);
    const fallbackHint = fallbackUsed ? " | fallback used" : "";
    setSuspectStatus(
      `Suspect search complete: ${count} sighting(s). Mode: ${modeUsed}. Engine: ${engineUsed}${fallbackHint}. (${faceHint})`,
      "ok",
    );
  } catch (error) {
    setSuspectStatus(`Suspect search failed: ${formatError(error)}`, "error");
  }
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

async function refreshVideos(caseId = null, expectedSwitchVersion = null, options = {}) {
  const resolvedCaseId = caseId || ensureActiveCaseId();
  if (!resolvedCaseId) {
    renderVideoList([]);
    return;
  }
  const skipFollowups = Boolean(options && options.skipFollowups);

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
  refreshPendingUploadDuplicateFlags(resolvedCaseId);
  renderTriagePanels();
  if (!skipFollowups && resolvedCaseId === state.activeCaseId) {
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
  stopAnalysisStatusPolling();
  state.activeCaseId = nextCaseId;
  setWorkspaceView("analysis");
  markCaseStateChanged();
  restoreSearchForCase(nextCaseId);
  resetPlayerForCase(nextCaseId);
  resetAuxPlayers(nextCaseId);
  resetSuspectSearchView();
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
    await Promise.all([
      syncAnalysisQueueStatus(nextCaseId, "face_people"),
      syncAnalysisQueueStatus(nextCaseId, "vehicles"),
    ]);
    const backgroundRunning = isBackgroundIndexRunning(indexStatus);
    if (state.activeMainTab === "triage") {
      setTriageStatus(`Case ${nextCaseId}: triage timelines ready.`, "ok");
    }
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

async function deleteVideoInternal(caseId, safeFilename, options = {}) {
  const normalizedCaseId = String(caseId || "").trim();
  const normalizedFilename = String(safeFilename || "").trim();
  const refreshAfter = options.refreshAfter !== false;
  if (!normalizedCaseId || !normalizedFilename) {
    return;
  }

  setStatus(`Preparing ${normalizedFilename} for delete...`, "working");
  await releaseVideoPlaybackLocks(normalizedCaseId, normalizedFilename);
  setStatus(`Deleting ${normalizedFilename} from ${normalizedCaseId}...`, "working");
  const url = `${withCaseQuery("/videos", normalizedCaseId)}&filename=${encodeURIComponent(normalizedFilename)}`;
  await fetchJson(url, { method: "DELETE" });

  const playback = playbackCache.get(normalizedCaseId);
  if (playback && playback.filename === normalizedFilename) {
    clearPlaybackCache(normalizedCaseId);
  }
  if (
    videoPlayer
    && videoPlayer.dataset.caseId === normalizedCaseId
    && videoPlayer.dataset.filename === normalizedFilename
  ) {
    resetPlayerForCase(normalizedCaseId);
    setCaseUrl(normalizedCaseId);
  }

  removeVideoFromSearchCache(normalizedCaseId, normalizedFilename);
  const caseTriageCache = ensureCaseTriageCache(normalizedCaseId);
  caseTriageCache?.delete(normalizedFilename);
  triageErrors.delete(makeTriageKey(normalizedCaseId, normalizedFilename));
  restoreSearchForCase(normalizedCaseId);
  clearCaseTriageCache(normalizedCaseId);

  const selection = getCaseVideoSelection(normalizedCaseId);
  if (selection instanceof Set) {
    selection.delete(normalizedFilename);
  }

  if (refreshAfter) {
    await refreshVideos(normalizedCaseId);
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
    await deleteVideoInternal(caseId, safeFilename, { refreshAfter: true });
    setStatus(`Deleted ${safeFilename} from ${caseId}.`, "ok");
  } catch (error) {
    setStatus(`Delete video failed: ${formatError(error)}`, "error");
  }
}

async function deleteSelectedVideos() {
  let caseId = "";
  try {
    caseId = ensureActiveCaseId();
  } catch (error) {
    setStatus(formatError(error), "error");
    return;
  }

  const videos = getCaseVideos(caseId);
  const selection = getCaseVideoSelection(caseId);
  if (!(selection instanceof Set) || !selection.size) {
    setStatus("Select one or more videos to delete.", "error");
    return;
  }

  const filenames = normalizeVideoFilenames(videos).filter((name) => selection.has(name));
  if (!filenames.length) {
    setStatus("No selected videos found in current list.", "error");
    return;
  }

  const confirmed = window.confirm(
    `Delete ${filenames.length} selected video(s) from ${caseId}? This removes videos, embeddings, and thumbnails for each selected item.`,
  );
  if (!confirmed) {
    return;
  }

  let deletedCount = 0;
  const failures = [];

  for (let index = 0; index < filenames.length; index += 1) {
    const name = filenames[index];
    try {
      setStatus(
        `Deleting selected videos (${index + 1}/${filenames.length}): ${name}...`,
        "working",
      );
      await deleteVideoInternal(caseId, name, { refreshAfter: false });
      deletedCount += 1;
    } catch (error) {
      failures.push(`${name}: ${formatError(error)}`);
    }
  }

  try {
    await refreshVideos(caseId);
  } catch (error) {
    failures.push(`refresh: ${formatError(error)}`);
  }

  if (failures.length) {
    setStatus(
      `Deleted ${deletedCount}/${filenames.length} selected videos. Errors: ${failures.join(" | ")}`,
      "error",
    );
    return;
  }
  setStatus(`Deleted ${deletedCount} selected videos from ${caseId}.`, "ok");
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
    videoSelectionByCase.delete(targetCaseId);
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
  const allFiles = Array.from(videoInput.files || []);
  if (!allFiles.length) {
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
    uploadFlowActive = true;
    stopBackgroundIndexPolling();
    const caseId = ensureActiveCaseId();
    const selectedSourceIndicesOriginal = getSelectedPendingUploadSourceIndices(allFiles);
    let files = allFiles;
    let selectedSourceIndices = new Set(selectedSourceIndicesOriginal);
    let duplicateSkippedCount = 0;

    setStatus("Checking selected files for duplicates...", "working");
    const duplicateCandidates = await detectDuplicateUploadCandidatesWithHash(allFiles, caseId);
    if (duplicateCandidates.length > 0) {
      const duplicateIndexSet = reviewDuplicateUploadCandidates(duplicateCandidates, allFiles);
      if (duplicateIndexSet.size > 0) {
        const filteredFiles = [];
        const filteredSelectedIndices = new Set();
        for (let originalIndex = 0; originalIndex < allFiles.length; originalIndex += 1) {
          if (duplicateIndexSet.has(originalIndex)) {
            duplicateSkippedCount += 1;
            continue;
          }
          const nextIndex = filteredFiles.length;
          filteredFiles.push(allFiles[originalIndex]);
          if (selectedSourceIndicesOriginal.has(originalIndex)) {
            filteredSelectedIndices.add(nextIndex);
          }
        }
        files = filteredFiles;
        selectedSourceIndices = filteredSelectedIndices;

        if (pendingUploadItems.length === allFiles.length) {
          pendingUploadItems.forEach((item) => {
            const itemIndex = Number(item.sourceIndex);
            if (duplicateIndexSet.has(itemIndex)) {
              item.selectedForIndex = false;
            }
          });
          renderPreUploadIndexSelection();
        }

        if (!files.length) {
          hideTaskProgressUi();
          setStatus(
            "All selected files are duplicates of videos already in this case. No upload started.",
            "ok",
          );
          return;
        }
      }
    }

    const selectedForIndexCount = selectedSourceIndices.size;
    const engineLabel = getLoadedEmbeddingEngineLabel();
    const totalUploadBytes = files.reduce((sum, file) => sum + Number(file.size || 0), 0);
    const uploadStartedAt = Date.now();
    setStatus(
      `Transferring videos to ${caseId} (engine: ${engineLabel}) | semantic index selected: ${selectedForIndexCount}/${files.length}.`,
      "working",
    );
    const STEP1_LABEL = "Step 1/2: Upload ingest to server";
    const STEP2_LABEL = "Step 2/2: Server convert/finalize";
    setTaskProgressUi(
      STEP1_LABEL,
      0,
      `${files.length} file(s) | ${formatBytes(totalUploadBytes)}`,
    );
    const INDEX_QUEUE_STAGE = 100;
    const uploadSession = await resolveResumableUploadSession(caseId, files);
    const sessionId = String(uploadSession?.session?.session_id || "").trim();
    if (!sessionId) {
      throw new Error("Upload session missing session_id");
    }
    const sessionFiles = Array.isArray(uploadSession?.files) ? uploadSession.files : [];
    const sessionFileByKey = new Map(
      sessionFiles.map((item) => [String(item.source_key || "").trim(), item]),
    );
    let sessionReceivedBytes = Math.max(
      0,
      Number(uploadSession?.session?.received_bytes || 0),
    );
    const sessionTotalBytes = Math.max(
      0,
      Number(uploadSession?.session?.total_bytes || totalUploadBytes),
    ) || totalUploadBytes;
    let transferredBytesForEta = sessionReceivedBytes;
    const resumedLabel = uploadSession?.resumed ? "resuming" : "starting";
    setStatus(
      `Transferring videos to ${caseId} (engine: ${engineLabel}) | semantic index selected: ${selectedForIndexCount}/${files.length} | ${resumedLabel} resumable upload.`,
      "working",
    );

    const updateTransferProgress = (receivedBytesOverride = null) => {
      const receivedBytes = receivedBytesOverride === null
        ? sessionReceivedBytes
        : Math.max(0, Number(receivedBytesOverride || 0));
      sessionReceivedBytes = receivedBytes;
      transferredBytesForEta = Math.max(transferredBytesForEta, receivedBytes);
      const elapsedSec = Math.max(0.001, (Date.now() - uploadStartedAt) / 1000);
      const transferFraction = sessionTotalBytes > 0
        ? Math.max(0, Math.min(1, receivedBytes / sessionTotalBytes))
        : 1;
      const speedBytesPerSecond = transferredBytesForEta / elapsedSec;
      const remainingBytes = Math.max(0, sessionTotalBytes - receivedBytes);
      const etaSeconds = speedBytesPerSecond > 0 ? remainingBytes / speedBytesPerSecond : null;
      const meta = [
        `${formatBytes(receivedBytes)} / ${formatBytes(sessionTotalBytes)} transferred`,
        `${formatBytes(speedBytesPerSecond)}/s`,
        formatEtaLabel(etaSeconds),
      ].join(" | ");
      setTaskProgressUi(
        STEP1_LABEL,
        clampPercent(transferFraction * 100),
        meta,
      );
    };

    updateTransferProgress(sessionReceivedBytes);
    for (let sourceIndex = 0; sourceIndex < files.length; sourceIndex += 1) {
      const file = files[sourceIndex];
      const sourceKey = buildResumableSourceKey(file);
      const sessionFile = sessionFileByKey.get(sourceKey);
      if (!sessionFile) {
        throw new Error(`Upload session file mapping missing for ${file.name}`);
      }
      const fileId = String(sessionFile.file_id || "").trim();
      const chunkSizeBytes = Math.max(
        1,
        Number(uploadSession?.session?.chunk_size_bytes || DEFAULT_RESUMABLE_CHUNK_SIZE_BYTES),
      );
      const totalChunks = Math.max(
        1,
        Number(sessionFile.total_chunks || Math.ceil((Number(file.size || 0) || 1) / chunkSizeBytes)),
      );
      let startChunk = Math.max(0, Number(sessionFile.received_chunks || 0));
      if (startChunk > totalChunks) {
        startChunk = totalChunks;
      }
      for (let chunkIndex = startChunk; chunkIndex < totalChunks; chunkIndex += 1) {
        const chunkStart = chunkIndex * chunkSizeBytes;
        const chunkEnd = Math.min(Number(file.size || 0), chunkStart + chunkSizeBytes);
        const chunkBlob = file.slice(chunkStart, chunkEnd);
        const chunkPayload = await postResumableChunkWithRetry({
          sessionId,
          fileId,
          chunkIndex,
          totalChunks,
          payload: chunkBlob,
        });
        const chunkSession = chunkPayload && typeof chunkPayload.session === "object"
          ? chunkPayload.session
          : null;
        if (chunkSession) {
          updateTransferProgress(Number(chunkSession.received_bytes || sessionReceivedBytes));
        } else {
          updateTransferProgress(sessionReceivedBytes + (chunkEnd - chunkStart));
        }
      }
    }

    setTaskProgressUi(
      "Step 1/2 complete: Upload ingest to server",
      100,
      "Browser transfer is complete. Starting server convert/finalize...",
    );
    setTaskProgressUi(
      STEP2_LABEL,
      0,
      `${files.length} file(s) queued for server convert/finalize`,
    );
    let finalizeWatcherActive = true;
    let lastFinalizedCount = -1;
    let lastCompletedCount = -1;
    let lastFailedCount = -1;
    let lastProcessingFileKey = "";
    let lastReadyCount = -1;
    let lastPendingCount = -1;
    const pollFinalizeProgress = async () => {
      while (finalizeWatcherActive) {
        try {
          const statusPayload = await fetchJson(
            `/upload_session/status?session_id=${encodeURIComponent(sessionId)}`,
          );
          const sessionFiles = Array.isArray(statusPayload?.files) ? statusPayload.files : [];
          const orderedSessionFiles = sessionFiles
            .filter((item) => item && typeof item === "object")
            .slice()
            .sort((a, b) => {
              const left = Math.max(0, Number(a.source_index || 0));
              const right = Math.max(0, Number(b.source_index || 0));
              return left - right;
            });
          const completedCount = sessionFiles.filter((item) => {
            if (!item || typeof item !== "object") {
              return false;
            }
            const status = String(item.status || "").toLowerCase();
            const storedName = String(item.uploaded_filename || "").trim();
            return status === "completed" && Boolean(storedName);
          }).length;
          const failedCount = sessionFiles.filter((item) => {
            if (!item || typeof item !== "object") {
              return false;
            }
            const status = String(item.status || "").toLowerCase();
            return status === "failed";
          }).length;
          const processingFile = orderedSessionFiles.find((item) => {
            const status = String(item?.status || "").toLowerCase();
            return status === "in_progress";
          }) || null;
          const processingProgress = processingFile
            ? Math.max(0, Math.min(100, Number(processingFile.finalize_progress_percent || 0)))
            : 0;
          const processingStage = processingFile
            ? String(processingFile.finalize_stage || "").trim()
            : "";
          const readyCount = sessionFiles.filter((item) => {
            const status = String(item?.status || "").toLowerCase();
            return status === "ready";
          }).length;
          const pendingCount = sessionFiles.filter((item) => {
            const status = String(item?.status || "").toLowerCase();
            return status === "pending" || status === "ready";
          }).length;
          const activeCount = sessionFiles.filter((item) => {
            const status = String(item?.status || "").toLowerCase();
            return status === "in_progress";
          }).length;
          const finalizedCount = completedCount + failedCount;
          const totalFinalizeFiles = Math.max(files.length, sessionFiles.length || files.length);
          const processingBoost = processingFile ? (processingProgress / 100) : 0;
          const finalizeFraction = totalFinalizeFiles > 0
            ? Math.max(0, Math.min(1, (finalizedCount + processingBoost) / totalFinalizeFiles))
            : 0;
          const processingFileKey = processingFile
            ? String(processingFile.file_id || processingFile.source_filename || "").trim()
            : "";
          if (
            completedCount !== lastCompletedCount
            || failedCount !== lastFailedCount
            || processingFileKey !== lastProcessingFileKey
            || readyCount !== lastReadyCount
            || pendingCount !== lastPendingCount
          ) {
            lastCompletedCount = completedCount;
            lastFailedCount = failedCount;
            lastProcessingFileKey = processingFileKey;
            lastReadyCount = readyCount;
            lastPendingCount = pendingCount;
            const detailParts = [
              `${completedCount}/${totalFinalizeFiles} finalized`,
            ];
            if (failedCount > 0) {
              detailParts.push(`${failedCount} failed`);
            }
            if (processingFile) {
              const processingName = String(
                processingFile.source_filename
                || processingFile.uploaded_filename
                || processingFile.file_id
                || "unknown file",
              ).trim();
              const processingOrdinalRaw = orderedSessionFiles.findIndex((item) => {
                if (!item || typeof item !== "object") {
                  return false;
                }
                const left = String(item.file_id || "").trim();
                const right = String(processingFile.file_id || "").trim();
                if (left && right) {
                  return left === right;
                }
                return String(item.source_filename || "").trim() === String(processingFile.source_filename || "").trim();
              });
              const processingOrdinal = processingOrdinalRaw >= 0
                ? processingOrdinalRaw + 1
                : Math.min(totalFinalizeFiles, finalizedCount + 1);
              detailParts.push(`processing ${processingOrdinal}/${totalFinalizeFiles}: ${processingName}`);
              detailParts.push(`file progress ${Math.round(processingProgress)}%`);
              if (processingStage) {
                detailParts.push(`stage: ${processingStage}`);
              }
            } else if (readyCount > 0) {
              detailParts.push(`${readyCount} waiting to finalize`);
            }
            if (activeCount > 0) {
              detailParts.push(`${activeCount} active`);
            }
            if (pendingCount > 0) {
              detailParts.push(`${pendingCount} pending`);
            }
            detailParts.push("videos appear as each file finalizes");
            setTaskProgressUi(
              STEP2_LABEL,
              clampPercent(finalizeFraction * 100),
              detailParts.join(" | "),
            );
          }
          if (finalizedCount > lastFinalizedCount) {
            lastFinalizedCount = finalizedCount;
            try {
              await refreshVideos(caseId, null, { skipFollowups: true });
            } catch {
              // Non-fatal during polling; final refresh still runs after completion.
            }
          }
          const sessionStatus = String(statusPayload?.status || "").toLowerCase();
          if (
            sessionStatus === "completed"
            || sessionStatus === "completed_with_errors"
            || sessionStatus === "failed"
            || sessionStatus === "cancelled"
          ) {
            break;
          }
        } catch {
          // Keep polling; completion response is the source of truth.
        }
        await sleep(900);
      }
    };

    const finalizeWatcherPromise = pollFinalizeProgress();
    let uploadResult;
    try {
      uploadResult = await fetchJson("/upload_session/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
    } finally {
      finalizeWatcherActive = false;
      try {
        await finalizeWatcherPromise;
      } catch {
        // no-op
      }
    }
    setTaskProgressUi(
      "Step 2/2 complete: Server convert/finalize",
      100,
      "Preparing background indexing...",
    );
    clearResumableUploadState();

    const uploaded = uploadResult.uploaded || [];
    const errors = uploadResult.errors || [];
    const transcoded = uploadResult.transcoded || [];
    const triageQueued = Array.isArray(uploadResult.triage_queued)
      ? uploadResult.triage_queued
      : [];
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

    const summary = `Case ${caseId}: uploaded ${uploaded.length}, transcoded ${transcoded.length}, triage auto-queued ${triageQueued.length}, selected for semantic indexing ${selectedIndexTargets.length}, engine ${engineLabel}. ${backgroundMessage}`;
    const duplicateNote = duplicateSkippedCount > 0
      ? ` Skipped duplicate uploads: ${duplicateSkippedCount}.`
      : "";
    const errorNote = allErrors.length ? ` Errors: ${allErrors.join(" | ")}` : "";
    setStatus(`${summary}${duplicateNote}${errorNote}`, allErrors.length ? "error" : "ok");
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
  const normalizedCategory = normalizeAnalysisCategory(category);
  const setCategoryStatus = (message, kind = "") => {
    setCategoryAnalysisStatus(normalizedCategory, message, kind);
  };
  const filenames = getSelectedInsightFilenames(normalizedCategory);
  if (!filenames.length) {
    const label = analysisCategoryLabel(normalizedCategory);
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

  const label = analysisCategoryLabel(normalizedCategory);
  const confirmed = window.confirm(`Run ${label} analysis for ${filenames.length} selected video(s)?`);
  if (!confirmed) {
    return;
  }

  const frameInterval = Number.parseFloat(intervalInput?.value || "1");
  const safeFrameInterval = Number.isFinite(frameInterval) && frameInterval > 0 ? frameInterval : 2;

  try {
    setCategoryStatus(
      `Queueing ${label} analysis for ${filenames.length} selected video(s)...`,
      "working",
    );
    const payload = await fetchJson("/analysis/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        case_id: caseId,
        filenames,
        frame_interval_seconds: safeFrameInterval,
        batch_size: 32,
        force: false,
        analysis_face_people: normalizedCategory === "face_people",
        analysis_vehicles: normalizedCategory === "vehicles",
      }),
    });
    const queue = payload && typeof payload.queue === "object" ? payload.queue : {};
    const queueAheadCandidate = pickFirstFiniteNumber(
      [queue.position_ahead, queue.queue_position, payload?.position_ahead],
      null,
    );
    const queueAhead = Number.isFinite(queueAheadCandidate)
      ? Math.max(0, Math.floor(Number(queueAheadCandidate)))
      : null;
    const queueIdCandidate = pickFirstFiniteNumber([queue.job_id, payload?.job_id], 0);
    const queueId = Number.isFinite(queueIdCandidate)
      ? Math.max(0, Math.floor(Number(queueIdCandidate)))
      : 0;
    const started = Boolean(payload?.started);
    const message = String(payload?.message || "");

    const summaryParts = [];
    if (message) {
      summaryParts.push(message);
    } else if (started) {
      summaryParts.push(`${label} analysis queued.`);
    } else {
      summaryParts.push(`${label} analysis queue updated.`);
    }
    if (queueAhead !== null) {
      summaryParts.push(`Queue ahead: ${queueAhead}.`);
    }
    if (queueId > 0) {
      summaryParts.push(`Job #${queueId}.`);
    }
    setCategoryStatus(summaryParts.join(" "), "working");
    startAnalysisStatusPolling(caseId, normalizedCategory, { jobId: queueId });
    await refreshVideos(caseId);
  } catch (error) {
    if (isExactNotFoundError(error)) {
      setCategoryStatus(
        "Queue endpoint missing on current backend build. Running direct analysis fallback...",
        "working",
      );
      let processedCount = 0;
      let skippedCount = 0;
      const failures = [];
      for (let index = 0; index < filenames.length; index += 1) {
        const filename = String(filenames[index] || "").trim();
        if (!filename) {
          continue;
        }
        setCategoryStatus(
          `Running ${label} analysis (${index + 1}/${filenames.length})...`,
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
          const analysisPayload = payload && typeof payload.analysis === "object" ? payload.analysis : {};
          const status = String(analysisPayload.status || payload?.status || "")
            .trim()
            .toLowerCase();
          if (status === "skipped" || status === "not_requested" || status === "analysis_only") {
            skippedCount += 1;
          } else {
            processedCount += 1;
          }
        } catch (innerError) {
          failures.push(`${filename}: ${formatError(innerError)}`);
        }
      }

      await refreshVideos(caseId);
      await refreshInsightWalls();

      const summary = `${label} analysis fallback completed: processed ${processedCount}, skipped ${skippedCount}, failed ${failures.length}.`;
      if (failures.length) {
        setCategoryStatus(`${summary} Errors: ${failures.join(" | ")}`, "error");
      } else {
        setCategoryStatus(summary, "ok");
      }
      return;
    }

    setCategoryStatus(`Run ${label} analysis failed: ${formatError(error)}`, "error");
  }
}

async function runSearch() {
  const query = queryInput?.value?.trim() || "";
  if (!query) {
    setStatus("Type a search query.", "error");
    setSemanticSearchMeta("Type a search query first.", "error");
    return;
  }

  const threshold = normalizeScoreThreshold(
    scoreThresholdInput?.value,
    defaultSearchThreshold(),
  );
  setThresholdUiValue(threshold);
  const resultLimit = defaultSearchResultLimit();

  try {
    const caseId = ensureActiveCaseId();
    setStatus(`Searching in ${caseId}...`, "working");
    setSemanticSearchMeta("Analyzing query intent...", "working");
    const payload = await fetchJson("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        case_id: caseId,
        query,
        top_k: resultLimit,
        min_score: threshold,
      }),
    });
    const results = Array.isArray(payload.results) ? payload.results : [];
    renderResults(results);
    cacheSearchResults(caseId, query, threshold, resultLimit, results, payload.count);
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
    metaParts.push(`threshold=${threshold.toFixed(2)}`);
    const metaSuffix = metaParts.length ? ` (${metaParts.join(", ")})` : "";
    setStatus(`Case ${caseId}: found ${payload.count || results.length} result(s).${metaSuffix}`, "ok");
    const strategy = payload.search_strategy && typeof payload.search_strategy === "object"
      ? payload.search_strategy
      : {};
    const weights = strategy.weights && typeof strategy.weights === "object"
      ? strategy.weights
      : {};
    const counts = strategy.candidate_counts && typeof strategy.candidate_counts === "object"
      ? strategy.candidate_counts
      : {};
    const filterStats = strategy.filter_stats && typeof strategy.filter_stats === "object"
      ? strategy.filter_stats
      : {};
    const fallbackUsed = Boolean(strategy.fallback_used ?? payload.fallback_used);
    const searchTypeLabel = intent || String(strategy.intent || "unknown");
    const modeLabel = mode || String(strategy.mode || "unknown");
    const fallbackLabel = fallbackUsed ? "yes" : "no";
    const frameWeight = Number(weights.frame);
    const temporalWeight = Number(weights.temporal);
    const weightLabel = Number.isFinite(frameWeight) && Number.isFinite(temporalWeight)
      ? ` | Weights F/T: ${(frameWeight * 100).toFixed(0)}/${(temporalWeight * 100).toFixed(0)}`
      : "";
    const countsLabel = [
      Number.isFinite(Number(counts.frame_raw)) ? `frame ${Number(counts.frame_raw)}` : "",
      Number.isFinite(Number(counts.temporal_raw)) ? `temporal ${Number(counts.temporal_raw)}` : "",
      Number.isFinite(Number(counts.fused)) ? `fused ${Number(counts.fused)}` : "",
      Number.isFinite(Number(counts.final)) ? `final ${Number(counts.final)}` : "",
    ].filter(Boolean).join(", ");
    const filterLabel = [
      Number.isFinite(Number(filterStats.near_duplicates_removed))
        ? `near-dup ${Number(filterStats.near_duplicates_removed)}`
        : "",
      Number.isFinite(Number(filterStats.diversity_suppressed))
        ? `diversity ${Number(filterStats.diversity_suppressed)}`
        : "",
      Number.isFinite(Number(filterStats.per_video_cap_suppressed))
        ? `cap ${Number(filterStats.per_video_cap_suppressed)}`
        : "",
    ].filter(Boolean).join(", ");
    const engineMeta = engineLabel ? ` | Engine: ${engineLabel}` : "";
    const strategyMeta = countsLabel ? ` | Candidates: ${countsLabel}` : "";
    const filterMeta = filterLabel ? ` | Filters: ${filterLabel}` : "";
    setSemanticSearchMeta(
      `Search Type: ${searchTypeLabel} | Mode: ${modeLabel} | Fallback: ${fallbackLabel}${weightLabel}${strategyMeta}${filterMeta}${engineMeta}`,
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
  taskProgressStopBtn?.addEventListener("click", () => {
    stopBackgroundIndexFromProgress();
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
  workspaceQueueBtn?.addEventListener("click", () => {
    if (!state.activeCaseId) {
      setStatus("Select a case from Case Repository first.", "error");
      return;
    }
    setWorkspaceView("queue");
  });
  reportQueueRefreshBtn?.addEventListener("click", async () => {
    try {
      await refreshReportQueue({ silent: false });
    } catch (error) {
      setReportQueueStatus(`Queue refresh failed: ${formatError(error)}`, "error");
    }
  });
  indexQueueSummaryBtn?.addEventListener("click", () => {
    openIndexQueueSummaryPopup();
  });
  facePeopleQueueSummaryBtn?.addEventListener("click", () => {
    openAnalysisQueueSummaryPopup("face_people");
  });
  vehicleQueueSummaryBtn?.addEventListener("click", () => {
    openAnalysisQueueSummaryPopup("vehicles");
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
  videoSelectAll?.addEventListener("change", () => {
    const activeCaseId = String(state.activeCaseId || "").trim();
    if (!activeCaseId) {
      syncVideoSelectionControls([]);
      return;
    }
    const selection = getCaseVideoSelection(activeCaseId);
    if (!(selection instanceof Set)) {
      syncVideoSelectionControls([]);
      return;
    }
    const videos = getCaseVideos(activeCaseId);
    const filenames = normalizeVideoFilenames(videos);
    selection.clear();
    if (Boolean(videoSelectAll.checked)) {
      filenames.forEach((name) => selection.add(name));
    }
    renderVideoList(videos);
  });
  deleteSelectedVideosBtn?.addEventListener("click", () => {
    deleteSelectedVideos();
  });
  runExistingIndexBtn?.addEventListener("click", () => {
    runExistingSemanticIndex();
  });
  saveEmbeddingSettingsBtn?.addEventListener("click", () => {
    saveEmbeddingSettings();
  });
  saveSearchSettingsBtn?.addEventListener("click", () => {
    saveSearchSettings();
  });
  scoreThresholdInput?.addEventListener("input", () => {
    if (scoreThresholdValue) {
      scoreThresholdValue.textContent = formatThresholdValue(scoreThresholdInput.value);
    }
  });
  searchDedupeAggressivenessInput?.addEventListener("input", () => {
    updateSearchDedupeAggressivenessUi(searchDedupeAggressivenessInput.value);
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
  window.addEventListener("beforeunload", (event) => {
    if (!uploadFlowActive) {
      return;
    }
    event.preventDefault();
    event.returnValue = "";
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
  suspectSearchBtn?.addEventListener("click", () => {
    void runSuspectPhotoSearch();
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
  queueTaskPopupCloseBtn?.addEventListener("click", () => {
    closeQueueTaskPopup();
  });
  queueTaskPopupBackdrop?.addEventListener("click", () => {
    closeQueueTaskPopup();
  });
  queueTaskPopupSelectAll?.addEventListener("change", () => {
    const context = queueTaskPopupRecoveryContext;
    if (!context || !(context.selected instanceof Set) || !Array.isArray(context.filenames)) {
      queueTaskPopupUpdateRecoverySelectionMeta();
      return;
    }
    context.selected.clear();
    if (Boolean(queueTaskPopupSelectAll.checked)) {
      context.filenames.forEach((name) => context.selected.add(name));
    }
    const checkboxes = queueTaskPopupFiles
      ? Array.from(queueTaskPopupFiles.querySelectorAll("input.queue-task-file-select"))
      : [];
    checkboxes.forEach((checkbox) => {
      const filename = String(checkbox.dataset.filename || "").trim();
      checkbox.checked = context.selected.has(filename);
    });
    queueTaskPopupUpdateRecoverySelectionMeta();
  });
  queueTaskPopupRestartBtn?.addEventListener("click", () => {
    void restartInterruptedAnalysisFromPopup();
  });
  queueTaskPopupCancelBtn?.addEventListener("click", () => {
    void cancelInterruptedAnalysisFromPopup();
  });
  queueTaskPopupRemoveFilesBtn?.addEventListener("click", () => {
    void removeSelectedQueueFilesFromPopup();
  });
  queueTaskPopupDeleteBtn?.addEventListener("click", () => {
    void deleteQueueItemFromPopup();
  });
  window.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") {
      return;
    }
    if (semanticPopup && !semanticPopup.hasAttribute("hidden")) {
      closeSemanticPopup();
      return;
    }
    if (queueTaskPopup && !queueTaskPopup.hasAttribute("hidden")) {
      closeQueueTaskPopup();
    }
  });

  if (scoreThresholdInput) {
    setThresholdUiValue(scoreThresholdInput.value);
  }
  if (searchDedupeAggressivenessInput) {
    updateSearchDedupeAggressivenessUi(searchDedupeAggressivenessInput.value);
  }

  renderMainTabs();
  renderAnalysisSelectionLists();
  setTaskProgressStopCase("");
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
  await loadSearchSettings();

  clearResults();
  resetSuspectSearchView();
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
      setSuspectStatus("", "");
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
    setSuspectStatus(`Startup failed: ${formatError(error)}`, "error");
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
