# Local-First Video Semantic Search

Offline-capable video semantic search app using FastAPI, OpenCV, OpenCLIP, and FAISS.

Current UX workflow (top tabs):
1. `Semantic Search`: ingest videos (auto-convert to browser-safe MP4), base semantic indexing, semantic search, player
2. `Face & People`: select ingested videos to run analysis, search over detected crops, face wall + people wall, player
3. `Vehicle`: select ingested videos to run analysis, search over detected crops, vehicle wall, player

## Project Structure

```text
project/
  backend/
    main.py
    video_processing.py
    embeddings.py
    vector_store.py
  frontend/
    index.html
    script.js
    styles.css
  cases/
    cases.json
    8fbd20f2-04dd-4f02-bfb4-1f7fbb9b48c1/
      videos/
      thumbnails/
      data/
        faiss.index
        metadata.json
```

## Run Locally

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

This installs `imageio-ffmpeg` too, so AVI conversion works even if system `ffmpeg` is not installed.
It also installs `ultralytics` for stronger local detector support in step 2.

3. Start the app:

```powershell
python -m backend.main
```

The app runs at `http://127.0.0.1:8000` and opens in your browser automatically.

## Offline OpenCLIP Note

The app is fully local/offline at runtime, but OpenCLIP weights must be available on disk.

Use a local cache directory (recommended):

```powershell
$env:OPENCLIP_CACHE_DIR = ".\\data\\openclip_cache"
python -m backend.main
```

If the selected model weights are not already in that cache, download them once while online, then reuse the same cache offline.

## AVI Playback

When you upload a video, the backend attempts conversion to browser-compatible `.mp4` (H.264) and stores it in the selected case's `videos/` folder.
This keeps search/indexing local and makes playback reliable in HTML5 browsers.

ffmpeg resolution order:
1. `FFMPEG_PATH` environment variable
2. `ffmpeg` in system `PATH`
3. Bundled binary from `imageio-ffmpeg` (installed via `requirements.txt`)

## Optional Analysis (Step 2)

- Categories:
  - `Face & People` (Haar face detection + YOLO person detection)
  - `Vehicles` (YOLO vehicle classes from COCO)
- Analysis can run:
  - manually on selected ingested videos
- Analysis stores detected crops and CLIP embeddings locally for crop-search and wall views.
- Analysis is cached per video/interval and only re-runs when needed (or `force=true` is used).

### Offline YOLO Weights

For fully offline step-2 analysis, place YOLO weights locally and set:

```powershell
$env:YOLO_MODEL_PATH = ".\\models\\yolov8s.pt"
```

If unset, the app falls back to `models/yolov8s.pt` (if present) or `yolov8s.pt`.

## API Endpoints

- `POST /cases`
- `GET /cases`
- `POST /upload?case_id=...`
- `POST /process_video` (body includes `case_id`)
- `POST /analysis_gallery` (body includes `case_id`, category, optional query)
- `POST /search` (body includes `case_id`)
- `GET /videos?case_id=...`
- `GET /settings/embedding`
- `POST /settings/embedding`

## Notes

- Each case has isolated storage in `cases/{case_id}/videos`, `cases/{case_id}/thumbnails`, and `cases/{case_id}/data`
- Optional model overrides:
  - `OPENCLIP_MODEL` (default: `ViT-L-14`)
  - `OPENCLIP_PRETRAINED` (default: `openai`)
  - `OPENCLIP_DEVICE` (default: `auto`, allowed: `auto`, `cuda`, `cpu`)
  - `OPENCLIP_CACHE_DIR` (set this to a local cache path for offline model loading)
  - `YOLO_MODEL_PATH` (optional local model path for step-2 analysis)
  - `YOLO_CONFIDENCE` (default: `0.3`)
  - `YOLO_IOU` (default: `0.45`)
  - Semantic search tuning:
    - `SEMANTIC_MIN_SCORE` (default: `0.22`)
    - `SEMANTIC_DIVERSITY_SECONDS` (default: `6.0`)
    - `SEMANTIC_OVERSAMPLE_FACTOR` (default: `10`)
    - `SEMANTIC_MAX_CANDIDATES` (default: `2000`)
    - `SEMANTIC_WINDOW_SECONDS` (default: `8.0`, used for action/scene temporal windows)
    - `SEMANTIC_WINDOW_STRIDE_SECONDS` (default: `2.0`)

Changing `OPENCLIP_MODEL` or `OPENCLIP_PRETRAINED` requires re-indexing semantic embeddings for existing videos.
You can also change model/device from the in-app selector (Semantic Search tab -> Embedding Engine) and restart the app to apply.

Semantic search now auto-detects query intent in backend:
- `object` intent -> frame-level index
- `action` / `scene` intents -> temporal window index (with fallback to frame search if needed)
