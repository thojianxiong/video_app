from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile


class MediaService:
    def __init__(
        self,
        *,
        app: Any,
        video_extensions: set[str],
        convert_to_mp4: Any,
        generate_preview_thumbnail: Any,
        resolve_case_id_or_default: Any,
        get_case_paths_or_raise: Any,
        is_supported_video: Any,
        unique_video_path: Any,
        write_upload_file: Any,
        truncate_error: Any,
        preview_thumbnail_path: Any,
        media_url_for_case_path: Any,
        get_vector_store_for_case: Any,
        get_temporal_store_for_case: Any,
        delete_video_sync: Any,
        process_video_sync: Any,
        resolve_index_filenames: Any,
        find_running_index_case_id_locked: Any,
        new_index_job_record: Any,
        run_index_job_async: Any,
        index_job_snapshot: Any,
    ) -> None:
        self.app = app
        self.video_extensions = set(video_extensions)
        self.convert_to_mp4 = convert_to_mp4
        self.generate_preview_thumbnail = generate_preview_thumbnail
        self.resolve_case_id_or_default = resolve_case_id_or_default
        self.get_case_paths_or_raise = get_case_paths_or_raise
        self.is_supported_video = is_supported_video
        self.unique_video_path = unique_video_path
        self.write_upload_file = write_upload_file
        self.truncate_error = truncate_error
        self.preview_thumbnail_path = preview_thumbnail_path
        self.media_url_for_case_path = media_url_for_case_path
        self.get_vector_store_for_case = get_vector_store_for_case
        self.get_temporal_store_for_case = get_temporal_store_for_case
        self.delete_video_sync = delete_video_sync
        self.process_video_sync = process_video_sync
        self.resolve_index_filenames = resolve_index_filenames
        self.find_running_index_case_id_locked = find_running_index_case_id_locked
        self.new_index_job_record = new_index_job_record
        self.run_index_job_async = run_index_job_async
        self.index_job_snapshot = index_job_snapshot

    @staticmethod
    def _default_analysis_summary() -> dict:
        return {
            "processed_frames": 0,
            "face_people": {
                "processed": False,
                "face_count": 0,
                "people_count": 0,
                "hit_frames": 0,
                "first_hit_seconds": None,
            },
            "vehicles": {
                "processed": False,
                "vehicle_count": 0,
                "hit_frames": 0,
                "first_hit_seconds": None,
            },
        }

    async def upload(self, case_id: str | None, files: list[UploadFile]) -> dict:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        try:
            resolved_case_id = await asyncio.to_thread(self.resolve_case_id_or_default, case_id)
            case_paths = await asyncio.to_thread(self.get_case_paths_or_raise, resolved_case_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

        uploaded: list[str] = []
        errors: list[str] = []
        transcoded: list[dict[str, str]] = []
        uploaded_items: list[dict[str, str | int | bool]] = []

        for source_index, upload_file in enumerate(files):
            if not upload_file.filename:
                errors.append("Encountered a file without a name")
                continue

            if not self.is_supported_video(upload_file.filename):
                errors.append(
                    f"{upload_file.filename}: unsupported format (allowed: "
                    + ", ".join(sorted(self.video_extensions))
                    + ")"
                )
                await upload_file.close()
                continue

            source_extension = Path(upload_file.filename).suffix.lower() or ".mp4"
            temp_upload_path = case_paths.data_dir / f"upload_{uuid4().hex}{source_extension}"
            temp_converted_path = case_paths.data_dir / f"converted_{uuid4().hex}.mp4"
            converted_name, converted_path = self.unique_video_path(
                case_paths.videos_dir,
                upload_file.filename,
                forced_suffix=".mp4",
            )
            try:
                await asyncio.to_thread(self.write_upload_file, upload_file, temp_upload_path)

                print(
                    f"[upload][{case_paths.case_id}] convert input={upload_file.filename} "
                    f"output={converted_name}"
                )
                conversion_ok, conversion_error = await asyncio.to_thread(
                    self.convert_to_mp4,
                    temp_upload_path,
                    temp_converted_path,
                )

                if conversion_ok:
                    temp_upload_path.unlink(missing_ok=True)
                    await asyncio.to_thread(
                        shutil.move,
                        str(temp_converted_path),
                        str(converted_path),
                    )
                    uploaded.append(converted_name)
                    transcoded.append(
                        {
                            "source_filename": upload_file.filename,
                            "stored_filename": converted_name,
                        }
                    )
                    uploaded_items.append(
                        {
                            "source_index": int(source_index),
                            "source_filename": str(upload_file.filename),
                            "stored_filename": str(converted_name),
                            "converted": True,
                        }
                    )
                    preview_path = self.preview_thumbnail_path(case_paths, converted_name)
                    preview_ok = await asyncio.to_thread(
                        self.generate_preview_thumbnail,
                        converted_path,
                        preview_path,
                    )
                    if not preview_ok:
                        print(
                            f"[upload][{case_paths.case_id}] preview generation failed "
                            f"file={converted_name}"
                        )
                    print(
                        f"[upload][{case_paths.case_id}] convert success input={upload_file.filename} "
                        f"output={converted_name}"
                    )
                else:
                    temp_converted_path.unlink(missing_ok=True)
                    fallback_name, fallback_path = self.unique_video_path(
                        case_paths.videos_dir,
                        upload_file.filename,
                    )
                    await asyncio.to_thread(shutil.move, str(temp_upload_path), str(fallback_path))
                    uploaded.append(fallback_name)
                    uploaded_items.append(
                        {
                            "source_index": int(source_index),
                            "source_filename": str(upload_file.filename),
                            "stored_filename": str(fallback_name),
                            "converted": False,
                        }
                    )
                    preview_path = self.preview_thumbnail_path(case_paths, fallback_name)
                    preview_ok = await asyncio.to_thread(
                        self.generate_preview_thumbnail,
                        fallback_path,
                        preview_path,
                    )
                    if not preview_ok:
                        print(
                            f"[upload][{case_paths.case_id}] preview generation failed "
                            f"file={fallback_name}"
                        )
                    short_error = self.truncate_error(conversion_error)
                    errors.append(
                        f"{upload_file.filename}: mp4 conversion failed ({short_error})"
                    )
                    print(
                        f"[upload][{case_paths.case_id}] convert failure input={upload_file.filename} "
                        f"output={converted_name}"
                    )
                    if conversion_error:
                        print(f"[upload][{case_paths.case_id}] ffmpeg error: {conversion_error}")
            except Exception as exc:
                converted_path.unlink(missing_ok=True)
                temp_converted_path.unlink(missing_ok=True)
                temp_upload_path.unlink(missing_ok=True)
                errors.append(f"{upload_file.filename}: {exc}")
            finally:
                await upload_file.close()

        return {
            "case_id": case_paths.case_id,
            "uploaded": uploaded,
            "uploaded_items": uploaded_items,
            "errors": errors,
            "transcoded": transcoded,
        }

    async def list_videos(self, case_id: str | None) -> dict:
        try:
            resolved_case_id = await asyncio.to_thread(self.resolve_case_id_or_default, case_id)
            case_paths, vector_store = await asyncio.to_thread(
                self.get_vector_store_for_case,
                resolved_case_id,
            )
            _, temporal_store = await asyncio.to_thread(
                self.get_temporal_store_for_case,
                resolved_case_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

        indexed_counts = vector_store.indexed_counts_by_filename()
        indexed_window_counts = temporal_store.indexed_counts_by_filename()
        preview_thumbnails = vector_store.preview_thumbnails_by_filename()
        analysis_summary = vector_store.analysis_summary_by_filename()
        videos = []

        for file_path in sorted(case_paths.videos_dir.iterdir()):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self.video_extensions:
                continue

            file_stat = file_path.stat()
            preview_url = str(preview_thumbnails.get(file_path.name, "")).strip()
            if not preview_url:
                preview_path = self.preview_thumbnail_path(case_paths, file_path.name)
                if not preview_path.exists():
                    try:
                        await asyncio.to_thread(
                            self.generate_preview_thumbnail,
                            file_path,
                            preview_path,
                        )
                    except Exception:
                        pass
                if preview_path.exists():
                    preview_url = self.media_url_for_case_path(preview_path)

            videos.append(
                {
                    "filename": file_path.name,
                    "size_bytes": file_stat.st_size,
                    "video_url": self.media_url_for_case_path(file_path),
                    "preview_thumbnail_url": preview_url,
                    "indexed_frames": indexed_counts.get(file_path.name, 0),
                    "indexed_windows": indexed_window_counts.get(file_path.name, 0),
                    "analysis": analysis_summary.get(
                        file_path.name,
                        self._default_analysis_summary(),
                    ),
                }
            )

        return {"case_id": case_paths.case_id, "videos": videos}

    async def delete_video(self, case_id: str | None, filename: str | None) -> dict:
        if not filename or not str(filename).strip():
            raise HTTPException(status_code=400, detail="filename is required")

        try:
            resolved_case_id = await asyncio.to_thread(self.resolve_case_id_or_default, case_id)
            safe_filename = Path(str(filename or "")).name.strip()
            if not safe_filename:
                raise HTTPException(status_code=400, detail="filename is required")

            index_jobs: dict[str, dict] = self.app.state.index_jobs
            index_lock: Lock = self.app.state.index_jobs_lock
            with index_lock:
                existing_job = index_jobs.get(resolved_case_id)
                if isinstance(existing_job, dict):
                    existing_status = str(existing_job.get("status") or "")
                    if bool(existing_job.get("running")) or existing_status in {"queued", "running"}:
                        current_filename = str(existing_job.get("current_filename") or "").strip()
                        detail = (
                            "Cannot delete videos while background semantic indexing is running "
                            f"for case {resolved_case_id}."
                        )
                        if current_filename:
                            detail += f" Currently processing: {current_filename}."
                        detail += " Wait for indexing to complete, then retry."
                        raise HTTPException(status_code=409, detail=detail)

            return await asyncio.to_thread(self.delete_video_sync, resolved_case_id, safe_filename)
        except HTTPException:
            raise
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Video not found: {filename}")
        except PermissionError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    async def process_video(
        self,
        *,
        case_id: str | None,
        filename: str,
        frame_interval_seconds: float,
        batch_size: int,
        force: bool,
        analysis_face_people: bool,
        analysis_vehicles: bool,
        analysis_only: bool,
    ) -> dict:
        try:
            resolved_case_id = await asyncio.to_thread(
                self.resolve_case_id_or_default,
                case_id,
            )
            return await asyncio.to_thread(
                self.process_video_sync,
                case_id=resolved_case_id,
                filename=filename,
                frame_interval_seconds=frame_interval_seconds,
                batch_size=batch_size,
                force=force,
                analysis_face_people=analysis_face_people,
                analysis_vehicles=analysis_vehicles,
                analysis_only=analysis_only,
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"Video not found: {filename}",
            )
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    async def start_background_index(
        self,
        *,
        case_id: str | None,
        filenames: list[str] | None,
        frame_interval_seconds: float,
        batch_size: int,
        force: bool,
    ) -> dict:
        try:
            resolved_case_id = await asyncio.to_thread(
                self.resolve_case_id_or_default,
                case_id,
            )
            case_paths = await asyncio.to_thread(self.get_case_paths_or_raise, resolved_case_id)
            resolved_filenames = await asyncio.to_thread(
                self.resolve_index_filenames,
                case_paths,
                filenames,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Video not found: {exc}")
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        jobs: dict[str, dict] = self.app.state.index_jobs
        lock: Lock = self.app.state.index_jobs_lock

        with lock:
            running_case_id = self.find_running_index_case_id_locked(jobs)
            if running_case_id and running_case_id != resolved_case_id:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Background indexing already running for case "
                        f"{running_case_id}. Wait for it to finish first."
                    ),
                )

            existing = jobs.get(resolved_case_id)
            if isinstance(existing, dict):
                existing_status = str(existing.get("status") or "")
                if bool(existing.get("running")) or existing_status in {"queued", "running"}:
                    snapshot = self.index_job_snapshot(existing, case_id=resolved_case_id)
                    return {
                        "started": False,
                        "case_id": resolved_case_id,
                        "job": snapshot,
                        "message": "Background indexing already running for this case.",
                    }

            job = self.new_index_job_record(
                case_id=resolved_case_id,
                filenames=resolved_filenames,
                frame_interval_seconds=frame_interval_seconds,
                batch_size=batch_size,
                force=force,
            )
            jobs[resolved_case_id] = job

        task = asyncio.create_task(self.run_index_job_async(resolved_case_id))
        task.add_done_callback(lambda _task: None)

        with lock:
            tasks: dict[str, asyncio.Task] = self.app.state.index_tasks
            tasks[resolved_case_id] = task
            snapshot = self.index_job_snapshot(jobs.get(resolved_case_id), case_id=resolved_case_id)

        print(
            f"[index-start][{resolved_case_id}] files={len(resolved_filenames)} "
            f"frame_interval={frame_interval_seconds} batch_size={batch_size} force={force}"
        )

        return {
            "started": True,
            "case_id": resolved_case_id,
            "job": snapshot,
        }

    async def get_background_index_status(self, case_id: str | None) -> dict:
        selected_case_id = ""
        try:
            selected_case_id = await asyncio.to_thread(self.resolve_case_id_or_default, case_id)
            await asyncio.to_thread(self.get_case_paths_or_raise, selected_case_id)
        except ValueError as exc:
            if case_id and str(case_id).strip():
                raise HTTPException(status_code=400, detail=str(exc))
            return self.index_job_snapshot(None, case_id="")
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        jobs: dict[str, dict] = self.app.state.index_jobs
        lock: Lock = self.app.state.index_jobs_lock
        with lock:
            job = jobs.get(selected_case_id)
            return self.index_job_snapshot(job, case_id=selected_case_id)

