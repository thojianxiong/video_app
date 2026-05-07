from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException

from backend.analysis_store import AnalysisCropStore


class InsightsService:
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
        self.media_url_for_case_path = media_url_for_case_path
        self.embedding_engine_info = embedding_engine_info
        self.float_from_env = float_from_env
        self.int_from_env = int_from_env
        self.semantic_object = semantic_object
        self.semantic_action = semantic_action
        self.semantic_scene = semantic_scene

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
            return await asyncio.to_thread(
                self.build_video_triage_sync,
                case_id=selected_case_id,
                filename=filename,
                bucket_seconds=bucket_seconds,
                force=force,
            )
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

        resolved_min_score = (
            float(min_score)
            if min_score is not None
            else self.float_from_env("SEMANTIC_MIN_SCORE", 0.22)
        )
        resolved_diversity = (
            float(diversity_seconds)
            if diversity_seconds is not None
            else self.float_from_env("SEMANTIC_DIVERSITY_SECONDS", 6.0)
        )
        resolved_oversample = (
            int(oversample_factor)
            if oversample_factor is not None
            else self.int_from_env("SEMANTIC_OVERSAMPLE_FACTOR", 10)
        )
        max_candidates = max(1, self.int_from_env("SEMANTIC_MAX_CANDIDATES", 2000))
        search_top_k = min(
            max(int(top_k), int(top_k) * max(1, resolved_oversample)),
            max_candidates,
        )

        def _run_search(resolved_case_id: str) -> tuple[str, list[dict], dict[str, Any]]:
            case_paths, vector_store = self.get_vector_store_for_case(resolved_case_id)
            _, temporal_store = self.get_temporal_store_for_case(resolved_case_id)
            query_embedding = self.app.state.embedder.encode_text(clean_query)
            intent_payload = self.detect_semantic_intent(clean_query, query_embedding)
            intent = str(intent_payload.get("intent") or self.semantic_object)
            mode = "frame"
            fallback_used = False
            active_min_score = float(resolved_min_score)
            active_diversity = float(resolved_diversity)

            if intent == self.semantic_action:
                mode = "temporal"
                active_diversity = max(active_diversity, 8.0)
                active_min_score = max(-1.0, active_min_score - 0.03)
                raw_results = temporal_store.search(query_embedding, top_k=search_top_k)
                if not raw_results:
                    fallback_used = True
                    mode = "frame_fallback"
                    raw_results = vector_store.search(query_embedding, top_k=search_top_k)
            elif intent == self.semantic_scene:
                mode = "temporal"
                active_diversity = max(active_diversity, 10.0)
                active_min_score = max(-1.0, active_min_score - 0.02)
                raw_results = temporal_store.search(query_embedding, top_k=search_top_k)
                if not raw_results:
                    fallback_used = True
                    mode = "frame_fallback"
                    raw_results = vector_store.search(query_embedding, top_k=search_top_k)
            else:
                raw_results = vector_store.search(query_embedding, top_k=search_top_k)

            filtered_results = self.apply_semantic_post_filters(
                raw_results,
                top_k=top_k,
                min_score=active_min_score,
                diversity_seconds=active_diversity,
            )

            if not filtered_results and mode == "temporal":
                fallback_used = True
                mode = "frame_fallback"
                raw_results = vector_store.search(query_embedding, top_k=search_top_k)
                filtered_results = self.apply_semantic_post_filters(
                    raw_results,
                    top_k=top_k,
                    min_score=resolved_min_score,
                    diversity_seconds=resolved_diversity,
                )

            print(
                f"[semantic][{case_paths.case_id}] query={clean_query!r} "
                f"intent={intent} mode={mode} fallback={fallback_used} "
                f"top_k={top_k} searched={search_top_k} "
                f"raw={len(raw_results)} filtered={len(filtered_results)} "
                f"min_score={active_min_score:.3f} diversity_seconds={active_diversity:.2f}"
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
                hydrated.append(payload)

            return case_paths.case_id, hydrated, {
                "intent": intent,
                "intent_scores": intent_payload.get("scores", {}),
                "intent_margin": float(intent_payload.get("margin", 0.0)),
                "intent_reasons": intent_payload.get("reasons", []),
                "search_mode": mode,
                "fallback_used": fallback_used,
                "effective_min_score": float(active_min_score),
                "effective_diversity_seconds": float(active_diversity),
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
                    "top_k": int(top_k),
                    "min_score": float(search_meta.get("effective_min_score", resolved_min_score)),
                    "diversity_seconds": float(
                        search_meta.get("effective_diversity_seconds", resolved_diversity)
                    ),
                    "oversample_factor": int(resolved_oversample),
                    "candidates_searched": int(search_top_k),
                    "intent_auto": True,
                },
            }
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
