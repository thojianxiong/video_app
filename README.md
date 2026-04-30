# Local-First Video Semantic Search

Offline-capable video semantic search app using FastAPI, OpenCV, OpenCLIP, and FAISS.

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
    case_001/
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

## API Endpoints

- `POST /cases`
- `GET /cases`
- `POST /upload?case_id=...`
- `POST /process_video` (body includes `case_id`)
- `POST /search` (body includes `case_id`)
- `GET /videos?case_id=...`

## Notes

- Each case has isolated storage in `cases/{case_id}/videos`, `cases/{case_id}/thumbnails`, and `cases/{case_id}/data`
- Optional model overrides:
  - `OPENCLIP_MODEL` (default: `ViT-B-32`)
  - `OPENCLIP_PRETRAINED` (default: `laion2b_s34b_b79k`)
  - `OPENCLIP_CACHE_DIR` (set this to a local cache path for offline model loading)
