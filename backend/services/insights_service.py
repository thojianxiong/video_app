from __future__ import annotations

import asyncio
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import HTTPException

from backend.analysis_store import AnalysisCropStore


class InsightsService:
    QUEUE_KIND_TRIAGE_TIMELINE = "triage_timeline"
    QUEUE_PRIORITY_TRIAGE_TIMELINE = 20

    def __init__(
        self,
        *,
        app: Any,
        resolve_case_id_or_default: Any,
        get_analysis_store_for_case: Any,
        hydrate_crop_item: Any,
        load_cached_video_triage_sync: Any,
        build_video_triage_sync: Any,
        get_vector_store_for_case: Any,
        get_temporal_store_for_case: Any,
        detect_semantic_intent: Any,
        apply_semantic_post_filters: Any,
        read_search_settings_sync: Any,
        derive_search_runtime_settings: Any,
        media_url_for_case_path: Any,
        embedding_engine_info: Any,
        float_from_env: Any,
        int_from_env: Any,
        semantic_object: str,
        semantic_action: str,
        semantic_scene: str,
    ) -> None:
        self.app = app
        self.resolve_case_id_or_default = resolve_case_id_or_default
        self.get_analysis_store_for_case = get_analysis_store_for_case
        self.hydrate_crop_item = hydrate_crop_item
        self.load_cached_video_triage_sync = load_cached_video_triage_sync
        self.build_video_triage_sync = build_video_triage_sync
        self.get_vector_store_for_case = get_vector_store_for_case
        self.get_temporal_store_for_case = get_temporal_store_for_case
        self.detect_semantic_intent = detect_semantic_intent
        self.apply_semantic_post_filters = apply_semantic_post_filters
        self.read_search_settings_sync = read_search_settings_sync
        self.derive_search_runtime_settings = derive_search_runtime_settings
        self.media_url_for_case_path = media_url_for_case_path
        self.embedding_engine_info = embedding_engine_info
        self.float_from_env = float_from_env
        self.int_from_env = int_from_env
        self.semantic_object = semantic_object
        self.semantic_action = semantic_action
        self.semantic_scene = semantic_scene

    def _video_delete_registry(self) -> tuple[Lock, set[str]]:
        state = self.app.state
        guard_lock = getattr(state, "deleting_video_keys_lock", None)
        if guard_lock is None or not hasattr(guard_lock, "acquire"):
            guard_lock = Lock()
            setattr(state, "deleting_video_keys_lock", guard_lock)

        deleting_keys = getattr(state, "deleting_video_keys", None)
        if not isinstance(deleting_keys, set):
            deleting_keys = set()
            setattr(state, "deleting_video_keys", deleting_keys)

        setattr(state, "deleting_videos_lock", guard_lock)
        setattr(state, "deleting_videos", deleting_keys)
        return guard_lock, deleting_keys

    def _is_video_delete_in_progress(self, case_id: str, filename: str) -> bool:
        normalized_case_id = str(case_id or "").strip()
        safe_filename = Path(str(filename or "")).name.strip().lower()
        if not normalized_case_id or not safe_filename:
            return False
        key = f"{normalized_case_id}::{safe_filename}"
        guard_lock, deleting_keys = self._video_delete_registry()
        with guard_lock:
            return key in deleting_keys

    async def analysis_gallery(
        self,
        *,
        case_id: str | None,
        category: str,
        query: str,
        top_k: int,
        limit: int,
    ) -> dict:
        try:
            selected_case_id = await asyncio.to_thread(
                self.resolve_case_id_or_default,
                case_id,
            )
            case_paths, crop_store = await asyncio.to_thread(
                self.get_analysis_store_for_case,
                selected_case_id,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        clean_query = query.strip()
        try:
            if clean_query:
                query_embedding = await asyncio.to_thread(
                    self.app.state.embedder.encode_text,
                    clean_query,
                )
                raw_items = await asyncio.to_thread(
                    crop_store.search,
                    category=category,
                    query_embedding=query_embedding,
                    top_k=top_k,
                )
            else:
                raw_items = await asyncio.to_thread(
                    crop_store.list_items,
                    category=category,
                    limit=limit,
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        faces: list[dict] = []
        people: list[dict] = []
        vehicles: list[dict] = []
        for item in raw_items:
            hydrated = self.hydrate_crop_item(case_paths, item)
            kind = str(hydrated.get("kind") or "").lower()
            if category == AnalysisCropStore.FACE_PEOPLE:
                if kind == "face":
                    faces.append(hydrated)
                else:
                    people.append(hydrated)
            else:
                vehicles.append(hydrated)

        return {
            "case_id": case_paths.case_id,
            "category": category,
            "query": clean_query,
            "faces": faces,
            "people": people,
            "vehicles": vehicles,
            "count": len(raw_items),
        }

    async def triage_timeline(
        self,
        *,
        case_id: str | None,
        filename: str,
        bucket_seconds: float,
        force: bool,
    ) -> dict:
        try:
            selected_case_id = await asyncio.to_thread(
                self.resolve_case_id_or_default,
                case_id,
            )
            cached_payload = await asyncio.to_thread(
                self.load_cached_video_triage_sync,
                case_id=selected_case_id,
                filename=filename,
                bucket_seconds=bucket_seconds,
            )
            cache_status = str(cached_payload.get("cache_status") or "").strip().lower()
            if cache_status == "hit" or bool(cached_payload.get("cached", False)):
                return cached_payload

            queue_store = getattr(self.app.state, "index_queue_store", None)
            if queue_store is None:
                raise RuntimeError("Background queue is unavailable.")

            safe_filename = str(filename or "").strip()
            if not safe_filename:
                raise ValueError("filename is required")
            safe_filename = Path(safe_filename).name.strip()
            if self._is_video_delete_in_progress(selected_case_id, safe_filename):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"'{safe_filename}' is currently being deleted in case '{selected_case_id}'. "
                        "Wait for deletion to finish, then retry timeline build."
                    ),
                )

            queued_job = await asyncio.to_thread(
                queue_store.enqueue_or_get_active,
                case_id=selected_case_id,
                filenames=[safe_filename],
                frame_interval_seconds=float(bucket_seconds),
                batch_size=1,
                force=bool(force),
                job_kind=self.QUEUE_KIND_TRIAGE_TIMELINE,
                priority=self.QUEUE_PRIORITY_TRIAGE_TIMELINE,
                metadata={
                    "bucket_seconds": float(bucket_seconds),
                    "force": bool(force),
                },
            )
            if not isinstance(queued_job, dict):
                raise RuntimeError("Failed to enqueue triage timeline job.")

            queue_position = max(0, int(queued_job.get("queue_position", 0)))
            queue_job_id = int(queued_job.get("job_id", 0))
            queue_job_kind = str(queued_job.get("job_kind") or self.QUEUE_KIND_TRIAGE_TIMELINE)
            queue_priority = max(1, int(queued_job.get("priority", self.QUEUE_PRIORITY_TRIAGE_TIMELINE)))
            created = bool(queued_job.get("created", False))
            reason = str(queued_job.get("reason") or "")

            return {
                "case_id": selected_case_id,
                "filename": safe_filename,
                "bucket_seconds": float(bucket_seconds),
                "cache_status": "queued",
                "cached": False,
                "queued": True,
                "queue": {
                    "job_id": queue_job_id,
                    "job_kind": queue_job_kind,
                    "priority": queue_priority,
                    "status": str(queued_job.get("status") or "queued"),
                    "position_ahead": queue_position,
                    "created": created,
                    "reason": reason,
                },
                "message": (
                    "Triage timeline queued."
                    if created
                    else "Triage timeline already queued/running."
                ),
            }
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Video not found: {filename}")
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    async def triage_timeline_cached(
        self,
        *,
        case_id: str | None,
        filename: str,
        bucket_seconds: float,
    ) -> dict:
        try:
            selected_case_id = await asyncio.to_thread(
                self.resolve_case_id_or_default,
                case_id,
            )
            return await asyncio.to_thread(
                self.load_cached_video_triage_sync,
                case_id=selected_case_id,
                filename=filename,
                bucket_seconds=bucket_seconds,
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Video not found: {filename}")
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    async def search(
        self,
        *,
        case_id: str | None,
        query: str,
        top_k: int,
        min_score: float | None,
        diversity_seconds: float | None,
        oversample_factor: int | None,
    ) -> dict:
        clean_query = query.strip()
        if not clean_query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        saved_search_settings = await asyncio.to_thread(self.read_search_settings_sync)
        if not isinstance(saved_search_settings, dict):
            saved_search_settings = {}

        saved_threshold = float(saved_search_settings.get("score_threshold", 0.22))
        saved_result_limit = int(saved_search_settings.get("result_limit", 120))
        saved_dedupe_aggressiveness = float(saved_search_settings.get("dedupe_aggressiveness", 55.0))
        runtime_search_settings = await asyncio.to_thread(
            self.derive_search_runtime_settings,
            saved_dedupe_aggressiveness,
        )
        if not isinstance(runtime_search_settings, dict):
            runtime_search_settings = {}

        resolved_min_score = float(min_score) if min_score is not None else float(saved_threshold)
        resolved_top_k = int(top_k) if int(top_k) > 0 else int(saved_result_limit)
        resolved_top_k = max(1, min(500, resolved_top_k))
        resolved_diversity = (
            float(diversity_seconds)
            if diversity_seconds is not None
            else float(runtime_search_settings.get("diversity_seconds", 6.0))
        )
        resolved_near_duplicate = float(runtime_search_settings.get("near_duplicate_seconds", 2.0))
        resolved_per_video_cap = int(runtime_search_settings.get("per_video_cap", 6))
        resolved_oversample = (
            int(oversample_factor)
            if oversample_factor is not None
            else self.int_from_env("SEMANTIC_OVERSAMPLE_FACTOR", 10)
        )
        max_candidates = max(1, self.int_from_env("SEMANTIC_MAX_CANDIDATES", 2000))
        search_top_k = min(
            max(int(resolved_top_k), int(resolved_top_k) * max(1, resolved_oversample)),
            max_candidates,
        )

        def _resolve_intent_weights(intent: str, margin: float) -> tuple[float, float, str]:
            safe_intent = str(intent or self.semantic_object).strip().lower()
            safe_margin = float(margin)
            if safe_margin < 0.03:
                # Low-confidence intent: use balanced dual strategy.
                return 0.6, 0.4, "dual_balanced"
            if safe_intent == self.semantic_action:
                return 0.30, 0.70, "dual_action_weighted"
            if safe_intent == self.semantic_scene:
                return 0.55, 0.45, "dual_scene_weighted"
            return 0.75, 0.25, "dual_object_weighted"

        def _fusion_key(item: dict) -> tuple[str, int]:
            video_filename = str(item.get("video_filename") or "").strip()
            timestamp = max(0.0, float(item.get("timestamp_seconds") or 0.0))
            # 0.5s buckets merge nearby frame/time-window hits.
            bucket = int(round(timestamp * 2.0))
            return video_filename, bucket

        def _fuse_dual_results(
            frame_results: list[dict],
            temporal_results: list[dict],
            *,
            frame_weight: float,
            temporal_weight: float,
        ) -> list[dict]:
            buckets: dict[tuple[str, int], dict[str, Any]] = {}

            def _upsert(item: dict, source: str) -> None:
                key = _fusion_key(item)
                if not key[0]:
                    return
                score = float(item.get("similarity_score", -1.0))
                candidate = buckets.get(key)
                if candidate is None:
                    candidate = {
                        "video_filename": str(item.get("video_filename") or ""),
                        "timestamp_seconds": float(item.get("timestamp_seconds") or 0.0),
                        "thumbnail_path": str(item.get("thumbnail_path") or ""),
                        "start_seconds": item.get("start_seconds"),
                        "end_seconds": item.get("end_seconds"),
                        "frame_similarity_score": None,
                        "temporal_similarity_score": None,
                        "source_modes": [],
                    }
                    buckets[key] = candidate
                if source == "frame":
                    prev = candidate.get("frame_similarity_score")
                    if prev is None or score > float(prev):
                        candidate["frame_similarity_score"] = float(score)
                else:
                    prev = candidate.get("temporal_similarity_score")
                    if prev is None or score > float(prev):
                        candidate["temporal_similarity_score"] = float(score)
                    if candidate.get("start_seconds") is None and item.get("start_seconds") is not None:
                        candidate["start_seconds"] = float(item.get("start_seconds"))
                    if candidate.get("end_seconds") is None and item.get("end_seconds") is not None:
                        candidate["end_seconds"] = float(item.get("end_seconds"))
                if not candidate.get("thumbnail_path"):
                    candidate["thumbnail_path"] = str(item.get("thumbnail_path") or "")
                modes = candidate.setdefault("source_modes", [])
                if source not in modes:
                    modes.append(source)

            for frame_item in frame_results:
                _upsert(frame_item, "frame")
            for temporal_item in temporal_results:
                _upsert(temporal_item, "temporal")

            fused: list[dict] = []
            for candidate in buckets.values():
                frame_score = candidate.get("frame_similarity_score")
                temporal_score = candidate.get("temporal_similarity_score")
                numerator = 0.0
                denominator = 0.0
                if frame_score is not None:
                    numerator += float(frame_score) * float(frame_weight)
                    denominator += float(frame_weight)
                if temporal_score is not None:
                    numerator += float(temporal_score) * float(temporal_weight)
                    denominator += float(temporal_weight)
                if denominator <= 0:
                    continue
                candidate["similarity_score"] = float(numerator / denominator)
                fused.append(candidate)
            fused.sort(key=lambda item: float(item.get("similarity_score", -1.0)), reverse=True)
            return fused

        def _run_search(resolved_case_id: str) -> tuple[str, list[dict], dict[str, Any]]:
            case_paths, vector_store = self.get_vector_store_for_case(resolved_case_id)
            _, temporal_store = self.get_temporal_store_for_case(resolved_case_id)
            query_embedding = self.app.state.embedder.encode_text(clean_query)
            intent_payload = self.detect_semantic_intent(clean_query, query_embedding)
            intent = str(intent_payload.get("intent") or self.semantic_object)
            intent_margin = float(intent_payload.get("margin", 0.0))
            frame_weight, temporal_weight, mode = _resolve_intent_weights(intent, intent_margin)
            frame_results = vector_store.search(query_embedding, top_k=search_top_k)
            temporal_results = temporal_store.search(query_embedding, top_k=search_top_k)
            fallback_used = False

            fused_candidates = _fuse_dual_results(
                frame_results,
                temporal_results,
                frame_weight=frame_weight,
                temporal_weight=temporal_weight,
            )

            post_filtered = self.apply_semantic_post_filters(
                fused_candidates,
                top_k=resolved_top_k,
                min_score=resolved_min_score,
                diversity_seconds=resolved_diversity,
                near_duplicate_seconds=resolved_near_duplicate,
                per_video_cap=resolved_per_video_cap,
                return_stats=True,
            )
            if isinstance(post_filtered, tuple):
                filtered_results, filter_stats = post_filtered
            else:
                filtered_results = post_filtered
                filter_stats = {}

            if not filtered_results and fused_candidates:
                fallback_used = True
                post_filtered = self.apply_semantic_post_filters(
                    fused_candidates,
                    top_k=resolved_top_k,
                    min_score=-1.0,
                    diversity_seconds=max(0.0, resolved_diversity * 0.5),
                    near_duplicate_seconds=max(0.0, resolved_near_duplicate * 0.6),
                    per_video_cap=max(0, resolved_per_video_cap + 2),
                    return_stats=True,
                )
                if isinstance(post_filtered, tuple):
                    filtered_results, filter_stats = post_filtered
                else:
                    filtered_results = post_filtered
                    filter_stats = {}

            print(
                f"[semantic][{case_paths.case_id}] query={clean_query!r} "
                f"intent={intent} mode={mode} fallback={fallback_used} "
                f"top_k={resolved_top_k} searched={search_top_k} "
                f"frame_raw={len(frame_results)} temporal_raw={len(temporal_results)} "
                f"fused={len(fused_candidates)} filtered={len(filtered_results)} "
                f"min_score={resolved_min_score:.3f} diversity_seconds={resolved_diversity:.2f} "
                f"near_dup={resolved_near_duplicate:.2f} per_video_cap={resolved_per_video_cap}"
            )

            hydrated = []
            for item in filtered_results:
                payload = {
                    "video_filename": item["video_filename"],
                    "timestamp_seconds": item["timestamp_seconds"],
                    "similarity_score": item["similarity_score"],
                    "thumbnail_url": item["thumbnail_path"],
                    "video_url": self.media_url_for_case_path(
                        case_paths.videos_dir / item["video_filename"]
                    ),
                }
                if "start_seconds" in item:
                    payload["window_start_seconds"] = float(item.get("start_seconds", 0.0))
                if "end_seconds" in item:
                    payload["window_end_seconds"] = float(item.get("end_seconds", 0.0))
                source_modes = item.get("source_modes")
                if isinstance(source_modes, list):
                    payload["source_modes"] = [str(mode_name) for mode_name in source_modes if str(mode_name).strip()]
                if item.get("frame_similarity_score") is not None:
                    payload["frame_similarity_score"] = float(item.get("frame_similarity_score"))
                if item.get("temporal_similarity_score") is not None:
                    payload["temporal_similarity_score"] = float(item.get("temporal_similarity_score"))
                hydrated.append(payload)

            return case_paths.case_id, hydrated, {
                "intent": intent,
                "intent_scores": intent_payload.get("scores", {}),
                "intent_margin": intent_margin,
                "intent_reasons": intent_payload.get("reasons", []),
                "search_mode": mode,
                "fallback_used": fallback_used,
                "frame_weight": float(frame_weight),
                "temporal_weight": float(temporal_weight),
                "effective_min_score": float(resolved_min_score),
                "effective_diversity_seconds": float(resolved_diversity),
                "effective_near_duplicate_seconds": float(resolved_near_duplicate),
                "effective_per_video_cap": int(resolved_per_video_cap),
                "raw_frame_count": int(len(frame_results)),
                "raw_temporal_count": int(len(temporal_results)),
                "fused_count": int(len(fused_candidates)),
                "filter_stats": filter_stats if isinstance(filter_stats, dict) else {},
            }

        try:
            selected_case_id = await asyncio.to_thread(
                self.resolve_case_id_or_default,
                case_id,
            )
            resolved_case_id, results, search_meta = await asyncio.to_thread(
                _run_search,
                selected_case_id,
            )
            return {
                "case_id": resolved_case_id,
                "query": clean_query,
                "results": results,
                "count": len(results),
                "intent": search_meta.get("intent"),
                "search_mode": search_meta.get("search_mode"),
                "fallback_used": bool(search_meta.get("fallback_used")),
                "intent_scores": search_meta.get("intent_scores", {}),
                "intent_margin": float(search_meta.get("intent_margin", 0.0)),
                "intent_reasons": search_meta.get("intent_reasons", []),
                "embedding_engine": self.embedding_engine_info(),
                "search_settings": {
                    "top_k": int(resolved_top_k),
                    "min_score": float(search_meta.get("effective_min_score", resolved_min_score)),
                    "diversity_seconds": float(
                        search_meta.get("effective_diversity_seconds", resolved_diversity)
                    ),
                    "near_duplicate_seconds": float(
                        search_meta.get("effective_near_duplicate_seconds", resolved_near_duplicate)
                    ),
                    "per_video_cap": int(
                        search_meta.get("effective_per_video_cap", resolved_per_video_cap)
                    ),
                    "dedupe_aggressiveness": float(saved_dedupe_aggressiveness),
                    "oversample_factor": int(resolved_oversample),
                    "candidates_searched": int(search_top_k),
                    "intent_auto": True,
                },
                "search_strategy": {
                    "intent": search_meta.get("intent"),
                    "mode": search_meta.get("search_mode"),
                    "fallback_used": bool(search_meta.get("fallback_used")),
                    "weights": {
                        "frame": float(search_meta.get("frame_weight", 0.0)),
                        "temporal": float(search_meta.get("temporal_weight", 0.0)),
                    },
                    "candidate_counts": {
                        "frame_raw": int(search_meta.get("raw_frame_count", 0)),
                        "temporal_raw": int(search_meta.get("raw_temporal_count", 0)),
                        "fused": int(search_meta.get("fused_count", 0)),
                        "final": int(len(results)),
                    },
                    "filter_stats": (
                        search_meta.get("filter_stats")
                        if isinstance(search_meta.get("filter_stats"), dict)
                        else {}
                    ),
                },
            }
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
