# VisioX (Local-First Video Investigation)

Offline-capable FastAPI + vanilla JS application for:
- case-based video ingestion
- triage timelines (activity + audio)
- semantic search
- optional Face/People and Vehicle analysis

Everything runs locally (no external inference API calls).

## Current Workflow

1. **Case Repository**
   - Create, rename, delete cases (case IDs are UUID-based).
   - Open a case to enter workspace.

2. **Workspace Utility Sidebar**
   - `Back` (to repository)
   - `Analysis` (main tabs)
   - `Report` (placeholder)
   - `Settings` (embedding engine settings)
   - `Exit` (shows running processes, asks confirmation, then graceful shutdown)

3. **Analysis Tabs**
   - `Video Triage`
     - Upload videos (auto conversion/remux for browser-compatible playback)
     - Choose which selected files should be semantically indexed **before upload**
     - Run semantic indexing for existing uploaded videos that are still unindexed
     - View triage timelines (activity + audio), scrub timeline, jump to peaks
   - `Semantic Search`
     - Natural-language search with intent-aware backend mode selection (`object` / `action` / `scene`)
     - Returns timestamped thumbnail hits and playback jump actions
   - `Face & People`
     - Run analysis on selected videos
     - Search over detected crops, face wall + people wall
   - `Vehicle`
     - Run analysis on selected videos
     - Search over detected crops, vehicle wall

## Project Structure

```text
project/
  backend/
    main.py                  # app wiring + shared helpers + lifespan startup
    routers/
      cases.py
      embedding_settings.py
      media.py
      insights.py
      process_control.py
    services/
      case_service.py
      embedding_settings_service.py
      media_service.py
      insights_service.py
      process_control_service.py
    schemas/
      cases.py
      embedding_settings.py
      media.py
      insights.py
      process_control.py
    video_processing.py
    triage.py
    embeddings.py
    vector_store.py
    temporal_store.py
    analysis.py
    analysis_store.py
  tests/
    services/
      test_case_service.py
      test_process_control_service.py
  frontend/
    index.html
    script.js
    styles.css
  cases/
    cases.json
    app_settings.json
    {case_id}/
      videos/
      thumbnails/
      data/
        faiss.index
        metadata.json
        temporal_faiss.index
        temporal_metadata.json
        face_people.index
        face_people_metadata.json
        vehicles.index
        vehicles_metadata.json
        triage_cache/
```

## Run Locally

1. Create and activate venv:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

2. Install deps:

```powershell
pip install -r requirements.txt
```

3. Start app:

```powershell
python -m backend.main
```

App serves on `http://127.0.0.1:8000` and opens browser automatically.

4. Optional: run lightweight unit tests:

```powershell
python -m unittest discover -s tests -v
```

## Offline Model Notes

- Runtime is local/offline, but model weights must exist on disk.
- OpenCLIP cache (recommended):

```powershell
$env:OPENCLIP_CACHE_DIR = ".\\cases\\model_cache\\openclip"
```

- Optional YOLO local weights:

```powershell
$env:YOLO_MODEL_PATH = ".\\models\\yolov8s.pt"
```

## Video Ingestion and Conversion

Supported inputs: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.m4v`, `.wmv`

On upload:
1. file is saved to temporary case data path
2. ffmpeg tries **remux** to MP4 with audio preserved
3. if remux fails, app falls back to high-quality transcode (`libx264` + `aac`)
4. only completed output is moved into `cases/{case_id}/videos`

ffmpeg resolution order:
1. `FFMPEG_PATH`
2. `ffmpeg` in system `PATH`
3. bundled binary from `imageio-ffmpeg`

## Semantic Indexing Behavior

- Semantic indexing is separate from upload completion.
- You can choose index targets:
  - pre-upload file checklist (`Select All` supported)
  - existing-unindexed video checklist (`Select All` supported)
- Background indexing endpoint:
  - `POST /index/start`
- Progress endpoint:
  - `GET /index/status?case_id=...`
  - includes current file, overall job progress, and per-file progress estimate

Current guardrail:
- only one background semantic indexing job runs at a time across cases.

## Triage Timelines

Endpoint: `POST /triage_timeline`

- Activity timeline combines motion + people detections + vehicle detections
- Audio timeline computes RMS intensity from extracted audio
- Timeline payload is cached per video/bucket in `data/triage_cache`

## API Endpoints

### Case Management
- `POST /cases`
- `GET /cases`
- `PATCH /cases/{case_id}`
- `DELETE /cases/{case_id}`

### Ingestion and Media
- `POST /upload?case_id=...`
- `GET /videos?case_id=...`
- `DELETE /videos?case_id=...&filename=...`

### Processing and Search
- `POST /process_video`
- `POST /index/start`
- `GET /index/status?case_id=...`
- `POST /triage_timeline`
- `POST /analysis_gallery`
- `POST /search`

### Settings and Process Control
- `GET /settings/embedding`
- `POST /settings/embedding`
- `GET /processes`
- `POST /shutdown`

## Config

### Embedding / Detector
- `OPENCLIP_MODEL` (default `ViT-L-14`)
- `OPENCLIP_PRETRAINED` (default `openai`)
- `OPENCLIP_DEVICE` (`auto|cuda|cpu`, default `auto`)
- `OPENCLIP_CACHE_DIR` (optional local model cache path)
- `YOLO_MODEL_PATH` (optional local model path)
- `YOLO_CONFIDENCE` (default `0.3`)
- `YOLO_IOU` (default `0.45`)

### Semantic Search
- `SEMANTIC_MIN_SCORE` (default `0.22`)
- `SEMANTIC_DIVERSITY_SECONDS` (default `6.0`)
- `SEMANTIC_OVERSAMPLE_FACTOR` (default `10`)
- `SEMANTIC_MAX_CANDIDATES` (default `2000`)
- `SEMANTIC_WINDOW_SECONDS` (default `8.0`)
- `SEMANTIC_WINDOW_STRIDE_SECONDS` (default `2.0`)

Changing OpenCLIP model/pretrained generally requires semantic re-indexing for existing cases.

## Scalability and Maintainability Review (Current Codebase)

Completed in the refactor phases so far:

1. **Router/service extraction**
   - Case, settings, media, insights, and process-control domains are split into dedicated routers/services.

2. **Shared request schemas**
   - API request models are centralized in `backend/schemas`, reducing payload-shape drift.

3. **Lifespan startup**
   - Startup moved from deprecated `on_event("startup")` to FastAPI lifespan.

Still recommended next:

1. **Durable background job storage**
   - Job state is currently in-memory.
   - Persist in SQLite (or similar) so status survives restart/crash.

2. **Queue-based workers for heavy processing**
   - Move long-running indexing/analysis to a worker queue model for retries/cancellation/isolation.

3. **Metadata schema versioning + migrations**
   - Version case metadata files and add migrations for backward compatibility.

4. **Expand automated tests**
   - Add endpoint integration tests and coverage for indexing/triage/search edge cases.

5. **Improve observability**
   - Structured logs + request/job correlation IDs + timing metrics.
