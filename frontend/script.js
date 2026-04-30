const videoInput = document.getElementById("videoInput");
const intervalInput = document.getElementById("intervalInput");
const uploadBtn = document.getElementById("uploadBtn");
const refreshBtn = document.getElementById("refreshBtn");
const uploadStatus = document.getElementById("uploadStatus");
const videoList = document.getElementById("videoList");
const queryInput = document.getElementById("queryInput");
const topKInput = document.getElementById("topKInput");
const searchBtn = document.getElementById("searchBtn");
const resultsGrid = document.getElementById("resultsGrid");
const videoPlayer = document.getElementById("videoPlayer");
const playerMeta = document.getElementById("playerMeta");

function setStatus(message, kind = "") {
  uploadStatus.textContent = message;
  uploadStatus.className = `status ${kind}`.trim();
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

function setPlaybackUrl(filename, timestampSeconds) {
  const url = new URL(window.location.href);
  url.searchParams.set("video", filename);
  url.searchParams.set("t", Number(timestampSeconds).toFixed(2));
  history.replaceState({}, "", url);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail || response.statusText || "Request failed";
    throw new Error(detail);
  }
  return payload;
}

function renderVideoList(videos) {
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

    row.appendChild(meta);
    row.appendChild(openBtn);
    videoList.appendChild(row);
  });
}

async function refreshVideos() {
  const payload = await fetchJson("/videos");
  renderVideoList(payload.videos || []);
}

function playVideoAt(filename, videoUrl, timestampSeconds) {
  const targetTime = Math.max(0, Number(timestampSeconds) || 0);
  const changedVideo = videoPlayer.dataset.filename !== filename;

  const seek = () => {
    const duration = Number.isFinite(videoPlayer.duration) ? videoPlayer.duration : null;
    const safeTime = duration && duration > 0 ? Math.min(targetTime, Math.max(0, duration - 0.05)) : targetTime;
    videoPlayer.currentTime = safeTime;
    videoPlayer.play().catch(() => {});
  };

  if (changedVideo) {
    videoPlayer.dataset.filename = filename;
    videoPlayer.src = videoUrl;
    videoPlayer.load();
    videoPlayer.addEventListener("loadedmetadata", seek, { once: true });
  } else if (videoPlayer.readyState >= 1) {
    seek();
  } else {
    videoPlayer.addEventListener("loadedmetadata", seek, { once: true });
  }

  playerMeta.textContent = `${filename} @ ${formatTime(targetTime)}`;
  setPlaybackUrl(filename, targetTime);
}

function renderResults(results) {
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
    setStatus("Uploading videos...", "working");
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));

    const uploadResult = await fetchJson("/upload", {
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
      setStatus(`Indexing ${filename} (${i + 1}/${uploaded.length})...`, "working");
      try {
        const processResult = await fetchJson("/process_video", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
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
        indexErrors.push(`${filename}: ${error.message}`);
      }
    }

    const allErrors = [...errors, ...indexErrors];
    const successNote = `Uploaded: ${uploaded.length} file(s), indexed: ${indexedCount}, skipped: ${skippedCount}, transcoded: ${transcoded.length}.`;
    const errorNote = allErrors.length ? ` Errors: ${allErrors.join(" | ")}` : "";
    setStatus(`${successNote}${errorNote}`, allErrors.length ? "error" : "ok");
    videoInput.value = "";
    await refreshVideos();
  } catch (error) {
    setStatus(`Upload/index failed: ${error.message}`, "error");
  }
}

async function runSearch() {
  const query = queryInput.value.trim();
  if (!query) {
    setStatus("Type a search query.", "error");
    return;
  }

  const topK = Math.max(1, Math.min(100, Number.parseInt(topKInput.value || "10", 10)));
  topKInput.value = String(topK);

  try {
    setStatus("Searching...", "working");
    const payload = await fetchJson("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: topK }),
    });
    renderResults(payload.results || []);
    setStatus(`Found ${payload.count || 0} result(s).`, "ok");
  } catch (error) {
    setStatus(`Search failed: ${error.message}`, "error");
  }
}

function restorePlaybackFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const filename = params.get("video");
  const t = Number.parseFloat(params.get("t") || "0");
  if (!filename) {
    return;
  }
  const videoUrl = `/media/videos/${encodeURIComponent(filename)}`;
  playVideoAt(filename, videoUrl, Number.isFinite(t) ? t : 0);
}

uploadBtn.addEventListener("click", uploadAndIndex);
refreshBtn.addEventListener("click", async () => {
  try {
    await refreshVideos();
    setStatus("Video list refreshed.", "ok");
  } catch (error) {
    setStatus(`Refresh failed: ${error.message}`, "error");
  }
});
searchBtn.addEventListener("click", runSearch);
queryInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    runSearch();
  }
});

window.addEventListener("DOMContentLoaded", async () => {
  renderResults([]);
  try {
    setStatus("Loading videos...", "working");
    await refreshVideos();
    setStatus("Ready.", "ok");
    restorePlaybackFromUrl();
  } catch (error) {
    setStatus(`Startup failed: ${error.message}`, "error");
  }
});
