# App Functionality Inventory (Runtime)

Scope: product-level capabilities in `backend/` + `frontend/` (not individual code functions).

Legend:
- Recommendation: `Keep`, `Improve`, `Fix now`, `Needs review`
- Priority: `P0` (immediate), `P1` (next), `P2` (later)

## 1) Case & Workspace Management
- [ ] **Functionality:** Create case | **Current behavior:** Creates UUID-backed case and updates repository list. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Stable core workflow entry.
- [ ] **Functionality:** List/open/switch case | **Current behavior:** Loads videos, restores case state, syncs queue/index status. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Core navigation behavior.
- [ ] **Functionality:** Rename case | **Current behavior:** Renames case metadata and refreshes list. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Low-risk.
- [ ] **Functionality:** Delete case (guarded) | **Current behavior:** Uses delete-in-progress guard and tries to quiesce running processes. | **Recommendation:** `Needs review` | **Priority:** `P1` | **Notes:** Destructive flow; keep lock/idempotency test coverage high.
- [ ] **Functionality:** Workspace navigation (Analysis/Report/Queue/Settings/Exit) | **Current behavior:** Sidebar routes views and toggles active sections. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Works as shell for all features.

## 2) Ingestion & Media Handling
- [ ] **Functionality:** Upload videos (batch) | **Current behavior:** Uploads selected files into active case. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Foundation for all downstream workflows.
- [ ] **Functionality:** Duplicate upload detection | **Current behavior:** Flags likely duplicates by name/fingerprint before upload. | **Recommendation:** `Improve` | **Priority:** `P1` | **Notes:** Good protection; tune UX messaging for bulk runs.
- [ ] **Functionality:** Resumable upload session | **Current behavior:** Start/status/chunk/complete flow for interrupted uploads. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Valuable reliability feature.
- [ ] **Functionality:** Video normalization (remux/transcode to playable MP4) | **Current behavior:** Remux first, fallback transcode when needed. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Critical compatibility path.
- [ ] **Functionality:** List videos in case | **Current behavior:** Shows per-video metadata/status in UI list. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Stable.
- [ ] **Functionality:** Delete single/multiple videos | **Current behavior:** Releases playback locks and removes media records. | **Recommendation:** `Needs review` | **Priority:** `P1` | **Notes:** Destructive operation; verify race paths under active playback.

## 3) Semantic Indexing
- [ ] **Functionality:** Pre-upload semantic index selection | **Current behavior:** Select which newly uploaded files are indexed. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Good control surface.
- [ ] **Functionality:** Index existing unindexed videos | **Current behavior:** Separate selector for already-uploaded files. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Supports deferred indexing workflows.
- [ ] **Functionality:** Background index queue start (`/index/start`) | **Current behavior:** Enqueues indexing by case/file list with progress tracking. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Core async job mechanism.
- [ ] **Functionality:** Index status polling (`/index/status`) | **Current behavior:** Polls progress, current file, queue state, and completion. | **Recommendation:** `Improve` | **Priority:** `P1` | **Notes:** Separate transport/state/view concerns further for maintainability.
- [ ] **Functionality:** Cancel case index jobs | **Current behavior:** Process control endpoint cancels queued/running case jobs. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Essential operational control.

## 4) Analysis Queue (Face/People + Vehicles)
- [ ] **Functionality:** Select files for Face & People analysis | **Current behavior:** Disables already processed/queued files; supports select-all. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Recent stability fixes in selection state.
- [ ] **Functionality:** Select files for Vehicle analysis | **Current behavior:** Same pattern as face/people with category-specific queueing. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Keep consistent with face/people UX.
- [ ] **Functionality:** Start analysis queue job (`/analysis/start`) | **Current behavior:** Enqueues category analysis and reports queue/job metadata. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Core async analysis workflow.
- [ ] **Functionality:** Analysis status polling (`/analysis/status`) | **Current behavior:** Polls queue/progress per analysis category. | **Recommendation:** `Improve` | **Priority:** `P1` | **Notes:** Refactor poll/update coupling to reduce UI race regressions.
- [ ] **Functionality:** Interrupted analysis recovery/cancel/remove-files | **Current behavior:** Queue popup supports stop/delete/run/remove selected files. | **Recommendation:** `Improve` | **Priority:** `P1` | **Notes:** High-value controls; keep adding explicit edge-case tests.
- [ ] **Functionality:** FACE-02 toggle (face identity embedding) | **Current behavior:** Optional mode in analysis settings for suspect-photo precision. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Useful for targeted investigations.

## 5) Triage & Playback
- [ ] **Functionality:** Triage timeline generation (`/triage_timeline`) | **Current behavior:** Motion + detection + audio intensity timeline payloads. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Main analyst workflow.
- [ ] **Functionality:** Triage cached timeline fetch (`/triage_timeline_cached`) | **Current behavior:** Uses cached payloads to reduce recomputation. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Good performance behavior.
- [ ] **Functionality:** Timeline scrubbing and peak navigation | **Current behavior:** Jump to timestamp/peaks with player synchronization. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Primary triage interaction.
- [ ] **Functionality:** Cross-player sync between triage and semantic players | **Current behavior:** Keeps players synchronized when jumping sources/timestamps. | **Recommendation:** `Fix now` | **Priority:** `P0` | **Notes:** Historically caused paused-video/audio-running regressions; keep strict playback guards.
- [ ] **Functionality:** Playback safety on tab/view switches | **Current behavior:** Pauses inactive players and closes popup in non-analysis views. | **Recommendation:** `Keep` | **Priority:** `P1` | **Notes:** Retest regularly after playback changes.

## 6) Search & Insight Surfaces
- [ ] **Functionality:** Semantic search (`/search`) | **Current behavior:** Query -> ranked timestamp results with score threshold and limits. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Core retrieval capability.
- [ ] **Functionality:** Search strategy/meta output | **Current behavior:** Shows mode/intent/fallback and retrieval metadata in UI. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Helpful analyst transparency.
- [ ] **Functionality:** Face/People gallery search (`/analysis_gallery`) | **Current behavior:** Query detected face/person crops and render gallery walls. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Useful post-analysis review surface.
- [ ] **Functionality:** Vehicle gallery search (`/analysis_gallery`) | **Current behavior:** Query vehicle crops with media jump actions. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Works well with targeted runs.
- [ ] **Functionality:** Suspect photo search (`/suspect_photo_search`) | **Current behavior:** Probe-image search with mode selection and score controls. | **Recommendation:** `Improve` | **Priority:** `P1` | **Notes:** Maintain precision/recall tuning and fallback visibility.

## 7) Queue, Reporting, and Operations
- [ ] **Functionality:** Queue page live view (`/processes`) | **Current behavior:** Shows active queued/running tasks and completed/recent items. | **Recommendation:** `Improve` | **Priority:** `P1` | **Notes:** Continue tightening submission grouping and status clarity.
- [ ] **Functionality:** Queue item controls (run/stop/delete/remove files) | **Current behavior:** Actions available in queue details popup. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Critical for operator control.
- [ ] **Functionality:** Graceful app exit (`/shutdown`) | **Current behavior:** Confirms running tasks and performs controlled shutdown. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Good local-first safety feature.
- [ ] **Functionality:** Report page | **Current behavior:** Placeholder/in development. | **Recommendation:** `Needs review` | **Priority:** `P2` | **Notes:** Define reporting scope or hide until implemented.

## 8) Settings
- [ ] **Functionality:** Embedding settings (`/settings/embedding`) | **Current behavior:** Model/pretrained/device preferences with persisted app settings. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Stable and useful.
- [ ] **Functionality:** Search settings (`/settings/search`) | **Current behavior:** Default threshold/dedupe aggressiveness/result limit controls. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Good operator tunables.
- [ ] **Functionality:** Analysis settings (`/settings/analysis`) | **Current behavior:** Face identity enable/disable persisted setting. | **Recommendation:** `Keep` | **Priority:** `P2` | **Notes:** Low complexity.

## Change Shortlist (Functional, Ranked)
1. **P0:** Harden triage/semantic playback synchronization behavior (prevent hidden/stray audio under rapid seek/tab-switch).
2. **P1:** Refactor analysis queue polling/update path for clearer state ownership and fewer UI race regressions.
3. **P1:** Strengthen destructive-operation safeguards (case/video delete under active queue/playback contention).
4. **P1:** Improve queue/recent presentation consistency for grouped submissions and resumed/interrupted jobs.
5. **P2:** Define Report module scope and either implement MVP output or hide/feature-flag it.
