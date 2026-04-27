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
  videos/
  thumbnails/
  data/
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

## API Endpoints

- `POST /upload`
- `POST /process_video`
- `POST /search`
- `GET /videos`

## Notes

- Videos are stored in `videos/`
- Thumbnails are stored in `thumbnails/`
- FAISS index and metadata are stored in `data/`
- Optional model overrides:
  - `OPENCLIP_MODEL` (default: `ViT-B-32`)
  - `OPENCLIP_PRETRAINED` (default: `laion2b_s34b_b79k`)
  - `OPENCLIP_CACHE_DIR` (set this to a local cache path for offline model loading)
