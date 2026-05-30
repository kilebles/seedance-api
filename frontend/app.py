"""Streamlit UI — временный фронтенд для seedance-api.

Заменить на Next.js / SvelteKit когда понадобится нормальный UX.
"""
from __future__ import annotations

import base64
import io
import os
import time
import zipfile
from pathlib import Path

import httpx
import streamlit as st

API_BASE = "http://api:8000"
POLL_INTERVAL = 3  # seconds between status checks
OUTPUT_DIR = Path("/app/output")
YADISK_TOKEN = os.environ.get("YANDEX_DISK_TOKEN", "")
YADISK_API = "https://cloud-api.yandex.net/v1/disk/resources"


# ── helpers ──────────────────────────────────────────────────────────────────

# ── Yandex Disk helpers ───────────────────────────────────────────────────────

def _yadisk_headers() -> dict:
    return {"Authorization": f"OAuth {YADISK_TOKEN}"}


def _yadisk_create_folder(path: str) -> bool:
    r = httpx.put(YADISK_API, headers=_yadisk_headers(), params={"path": path}, timeout=30)
    return r.status_code in (201, 409)


def _yadisk_get_upload_url(remote_path: str) -> str | None:
    r = httpx.get(
        f"{YADISK_API}/upload",
        headers=_yadisk_headers(),
        params={"path": remote_path, "overwrite": "true"},
        timeout=30,
    )
    if r.status_code != 200:
        return None
    return r.json().get("href")


def _yadisk_rename(from_path: str, to_path: str) -> bool:
    r = httpx.post(
        f"{YADISK_API}/move",
        headers=_yadisk_headers(),
        params={"from": from_path, "path": to_path, "overwrite": "true"},
        timeout=30,
    )
    return r.status_code in (201, 202)


def _yadisk_upload_bytes(content: bytes, remote_path: str) -> tuple[bool, str]:
    """Upload bytes to Yandex Disk using fake .txt extension trick to bypass throttling."""
    suffix = Path(remote_path).suffix
    fake_remote = remote_path[: -len(suffix)] + ".txt" if suffix else remote_path + ".txt"
    upload_url = _yadisk_get_upload_url(fake_remote)
    if not upload_url:
        return False, "Failed to get upload URL"

    with httpx.Client(timeout=httpx.Timeout(3600.0, connect=60.0, read=3600.0, write=3600.0, pool=60.0)) as c:
        r = c.put(upload_url, content=content)

    if r.status_code not in (201, 202):
        return False, f"Upload failed: {r.status_code}"

    ok = _yadisk_rename(fake_remote, remote_path)
    if not ok:
        return False, "Rename failed"
    return True, "OK"


def _make_zip(mp4_files: list[Path]) -> bytes:
    """Pack mp4 files into a zip archive in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for f in mp4_files:
            zf.write(f, f.name)
    return buf.getvalue()


def _yadisk_list_dirs(path: str) -> list[str]:
    """List subdirectories at given Yandex Disk path."""
    r = httpx.get(
        YADISK_API,
        headers=_yadisk_headers(),
        params={"path": path, "fields": "_embedded.items.name,_embedded.items.type", "limit": 100},
        timeout=15,
    )
    if r.status_code != 200:
        return []
    items = r.json().get("_embedded", {}).get("items", [])
    return sorted(i["name"] for i in items if i.get("type") == "dir")


def _list_output_dirs() -> list[str]:
    """Recursively list leaf directories that contain .mp4 files."""
    if not OUTPUT_DIR.exists():
        return []
    dirs = []
    for p in sorted(OUTPUT_DIR.rglob("*.mp4")):
        rel = str(p.parent.relative_to(OUTPUT_DIR))
        if rel not in dirs:
            dirs.append(rel)
    return dirs


def _to_data_uri(file_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(file_bytes).decode()
    return f"data:{mime};base64,{b64}"


def _submit(prompt: str, image_bytes: bytes | None, image_mime: str | None,
            ratio: str, resolution: str, duration: int | None,
            generate_audio: bool, seed: int | None = None,
            upscale_resolution: str | None = None) -> dict:
    content: list[dict] = []

    if image_bytes:
        content.append({
            "type": "image_url",
            "image_url": {"url": _to_data_uri(image_bytes, image_mime)},
            "role": "first_frame",
        })

    content.append({"type": "text", "text": prompt})

    payload: dict = {
        "content": content,
        "ratio": ratio,
        "resolution": resolution,
        "generate_audio": generate_audio,
    }
    if duration:
        payload["duration"] = duration
    if seed is not None:
        payload["seed"] = seed
    if upscale_resolution:
        payload["upscale_resolution"] = upscale_resolution

    resp = httpx.post(f"{API_BASE}/generations/tasks", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _get_task(task_id: str) -> dict:
    resp = httpx.get(f"{API_BASE}/generations/tasks/{task_id}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def _list_tasks() -> list[dict]:
    resp = httpx.get(f"{API_BASE}/generations/tasks", timeout=10)
    resp.raise_for_status()
    return resp.json()


def _cancel_task(task_id: str) -> None:
    resp = httpx.delete(f"{API_BASE}/generations/tasks/{task_id}", timeout=10)
    resp.raise_for_status()


def _cancel_tasks_bulk(task_ids: list[str]) -> dict:
    resp = httpx.post(f"{API_BASE}/generations/tasks/cancel-bulk", json={"task_ids": task_ids}, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── UI ────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="HistoryDoc SeeDance", layout="wide")
st.title("HistoryDoc SeeDance")

tab_generate, tab_batch, tab_history, tab_yadisk = st.tabs(["Generate", "Batch", "History", "Yandex Disk"])

# ── Generate tab ──────────────────────────────────────────────────────────────
with tab_generate:
    upscale = st.checkbox("Upscale (Topaz)", value=False, key="g_upscale")
    upscale_res = st.selectbox(
        "Upscale resolution",
        ["1080p", "4k"],
        key="g_upscale_res",
    )

    with st.form("generate_form"):
        prompt = st.text_area("Prompt", height=100, placeholder="Опишите видео...")

        uploaded = st.file_uploader(
            "Первый кадр (необязательно)",
            type=["jpg", "jpeg", "png", "webp"],
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            ratio = st.selectbox(
                "Aspect ratio",
                ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"],
            )
        with col2:
            resolution = st.selectbox("Resolution", ["720p", "480p"])
        with col3:
            duration = st.selectbox(
                "Duration (s)",
                [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
                index=4,
                format_func=lambda x: f"{x}s",
            )

        generate_audio = st.checkbox("Generate audio", value=True)

        col_seed1, col_seed2 = st.columns([1, 2])
        with col_seed1:
            fixed_seed = st.checkbox("Fixed seed", value=False)
        with col_seed2:
            seed_value = st.number_input(
                "Seed", min_value=0, max_value=4294967295, value=0, step=1,
                disabled=not fixed_seed, label_visibility="collapsed",
            )

        submitted = st.form_submit_button("Generate", type="primary")

    if submitted:
        if not prompt.strip():
            st.error("Prompt is required.")
        else:
            image_bytes = uploaded.read() if uploaded else None
            image_mime = uploaded.type if uploaded else None
            dur = int(duration)
            seed = int(seed_value) if fixed_seed else None

            with st.spinner("Submitting task..."):
                try:
                    task = _submit(
                        prompt=prompt.strip(),
                        image_bytes=image_bytes,
                        image_mime=image_mime,
                        ratio=ratio,
                        resolution=resolution,
                        duration=dur,
                        generate_audio=generate_audio,
                        seed=seed,
                        upscale_resolution=upscale_res if upscale else None,
                    )
                except Exception as e:
                    st.error(f"Failed to submit: {e}")
                    st.stop()

            task_id = task["id"]
            st.success(f"Task created: `{task_id}`")

            status_box = st.empty()
            progress_bar = st.progress(0)

            statuses = {"queued": 10, "running": 50, "succeeded": 100, "failed": 100, "expired": 100}

            while True:
                try:
                    task = _get_task(task_id)
                except Exception as e:
                    status_box.error(f"Polling error: {e}")
                    break

                status = task.get("status", "queued")
                progress_bar.progress(statuses.get(status, 10))
                status_box.info(f"Status: **{status}**")

                if status == "succeeded":
                    video_url = task.get("video_url")
                    if video_url:
                        st.video(video_url)
                    last_frame = task.get("last_frame_url")
                    if last_frame:
                        st.image(last_frame, caption="Last frame")
                    st.json({
                        "duration": task.get("duration_actual"),
                        "resolution": task.get("resolution_actual"),
                        "ratio": task.get("ratio_actual"),
                        "seed": task.get("seed_actual"),
                        "tokens": task.get("total_tokens"),
                    })
                    break
                elif status in ("failed", "expired"):
                    st.error(f"Task {status}: {task.get('error_message') or task.get('error_code') or 'unknown error'}")
                    break

                time.sleep(POLL_INTERVAL)

# ── Batch tab ─────────────────────────────────────────────────────────────────
with tab_batch:
    st.markdown("Загрузите xlsx-файл с колонками: `number`, `prompt`.")

    b_upscale = st.checkbox("Upscale (Topaz)", value=False, key="b_upscale")
    b_upscale_res = st.selectbox(
        "Upscale resolution",
        ["1080p", "4k"],
        key="b_upscale_res",
    )

    with st.form("batch_form"):
        xlsx_file = st.file_uploader("xlsx-файл", type=["xlsx"])

        col1, col2, col3 = st.columns(3)
        with col1:
            b_ratio = st.selectbox("Aspect ratio", ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"], key="b_ratio")
        with col2:
            b_resolution = st.selectbox("Resolution", ["720p", "480p"], key="b_resolution")
        with col3:
            b_duration = st.selectbox(
                "Duration (s)",
                [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
                index=4,
                format_func=lambda x: f"{x}s",
                key="b_duration",
            )
        b_audio = st.checkbox("Generate audio", value=True, key="b_audio")

        batch_submitted = st.form_submit_button("Start batch", type="primary")

    if batch_submitted:
        if not xlsx_file:
            st.error("Please upload an xlsx file.")
        else:
            with st.spinner("Submitting batch..."):
                try:
                    batch_data: dict = {
                        "ratio": b_ratio,
                        "resolution": b_resolution,
                        "duration": str(b_duration),
                        "generate_audio": str(b_audio).lower(),
                    }
                    if b_upscale:
                        batch_data["upscale_resolution"] = b_upscale_res

                    resp = httpx.post(
                        f"{API_BASE}/generations/batch",
                        files={"file": (xlsx_file.name, xlsx_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                        data=batch_data,
                        timeout=60,
                    )
                    resp.raise_for_status()
                    tasks = resp.json()
                except Exception as e:
                    st.error(f"Failed to submit batch: {e}")
                    tasks = []

            if tasks:
                st.success(f"Батч отправлен: {len(tasks)} задач в очереди")
                st.session_state["batch_task_ids"] = [t["id"] for t in tasks]
                st.session_state["batch_names"] = {t["id"]: t.get("name", t["id"][:8]) for t in tasks}
                first_path = tasks[0].get("local_path", "")
                st.session_state["batch_output_dir"] = "/".join(first_path.split("/")[:-1]) if first_path else ""

    # Show batch progress if we have tasks
    if "batch_task_ids" in st.session_state:
        task_ids = st.session_state["batch_task_ids"]
        names = st.session_state["batch_names"]
        output_dir = st.session_state.get("batch_output_dir", "")

        col_r, col_p, col_res, col_c = st.columns(4)
        with col_r:
            if st.button("Refresh", key="batch_refresh"):
                st.rerun()
        with col_p:
            if st.button("Pause", key="batch_pause"):
                httpx.post(f"{API_BASE}/generations/batch/pause", params={"output_dir": output_dir}, timeout=10)
                st.rerun()
        with col_res:
            if st.button("Resume", key="batch_resume"):
                httpx.post(f"{API_BASE}/generations/batch/resume", params={"output_dir": output_dir}, timeout=10)
                st.rerun()
        with col_c:
            if st.button("Cancel", key="batch_cancel", type="primary"):
                httpx.post(f"{API_BASE}/generations/batch/cancel", params={"output_dir": output_dir}, timeout=10)
                st.rerun()

        STATUS_ICON = {"queued": "⏳", "running": "⚙️", "succeeded": "✅", "failed": "❌", "expired": "🕐", "paused": "⏸️"}

        rows = []
        all_done = True
        for tid in task_ids:
            try:
                t = _get_task(tid)
            except Exception:
                t = {"id": tid, "status": "?"}
            s = t.get("status", "?")
            if s not in ("succeeded", "failed", "expired", "paused"):
                all_done = False
            rows.append({
                "name": names.get(tid, tid[:8]),
                "status": f"{STATUS_ICON.get(s, '')} {s}",
                "local_path": t.get("local_path") or "—",
                "error": t.get("error_code") or t.get("error_message") or "",
            })

        st.dataframe(rows, use_container_width=True)

        done = sum(1 for r in rows if any(x in r["status"] for x in ("✅", "❌", "🕐")))
        st.progress(done / len(rows))
        st.caption(f"Готово: {done}/{len(rows)}")

        if all_done and done == len(rows):
            st.success("Батч завершён! Видео сохранены на сервере.")


# ── History tab ───────────────────────────────────────────────────────────────
with tab_history:
    col_refresh, col_sort, col_cancel_all = st.columns([1, 2, 2])
    with col_refresh:
        if st.button("Refresh", key="history_refresh"):
            st.rerun()
    with col_sort:
        sort_order = st.radio(
            "Sort by date",
            ["Newer first", "Older first"],
            horizontal=True,
            key="history_sort",
            label_visibility="collapsed",
        )

    try:
        tasks = _list_tasks()
    except Exception as e:
        st.error(f"Failed to load tasks: {e}")
        tasks = []

    # Sort
    if sort_order == "Older first":
        tasks = list(reversed(tasks))

    # Cancellable statuses
    CANCELLABLE = {"queued", "paused"}

    cancellable_tasks = [t for t in tasks if t.get("status") in CANCELLABLE]

    with col_cancel_all:
        if cancellable_tasks:
            if st.button(f"Cancel all queued/paused ({len(cancellable_tasks)})", type="primary", key="cancel_all"):
                ids = [t["id"] for t in cancellable_tasks]
                try:
                    result = _cancel_tasks_bulk(ids)
                    st.success(f"Cancelled {result['cancelled']}, skipped {result['skipped']}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Cancel failed: {e}")

    if not tasks:
        st.info("No tasks yet.")
    else:
        # Bulk selection state
        if "selected_task_ids" not in st.session_state:
            st.session_state["selected_task_ids"] = set()

        # Bulk cancel controls for selected
        selected = st.session_state["selected_task_ids"]
        if selected:
            sel_col1, sel_col2, sel_col3 = st.columns([2, 2, 4])
            with sel_col1:
                st.caption(f"Selected: {len(selected)}")
            with sel_col2:
                if st.button("Cancel selected", type="primary", key="cancel_selected"):
                    try:
                        result = _cancel_tasks_bulk(list(selected))
                        st.success(f"Cancelled {result['cancelled']}, skipped {result['skipped']}")
                        st.session_state["selected_task_ids"] = set()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Cancel failed: {e}")
            with sel_col3:
                if st.button("Clear selection", key="clear_selection"):
                    st.session_state["selected_task_ids"] = set()
                    st.rerun()

        STATUS_COLOR = {"succeeded": "green", "failed": "red", "running": "orange", "queued": "gray", "paused": "blue", "expired": "red", "cancelled": "gray"}

        for t in tasks:
            task_id = t["id"]
            task_status = t.get("status", "?")
            color = STATUS_COLOR.get(task_status, "gray")
            is_cancellable = task_status in CANCELLABLE
            is_selected = task_id in st.session_state["selected_task_ids"]

            header_col, checkbox_col = st.columns([10, 1])
            with header_col:
                with st.expander(f":{color}[{task_status.upper()}] `{task_id[:8]}...` — {t.get('created_at', '')[:19]}"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        items = t.get("content_items") or []
                        for item in items:
                            if item.get("type") == "text":
                                st.markdown(f"**Prompt:** {item['text']}")
                        st.markdown(f"**Model:** {t.get('model')}")
                        st.markdown(f"**Resolution:** {t.get('resolution_requested')} | **Ratio:** {t.get('ratio_requested')}")
                        if t.get("error_message"):
                            st.error(t["error_message"])
                        if is_cancellable:
                            if st.button("Cancel this task", key=f"cancel_{task_id}"):
                                try:
                                    _cancel_task(task_id)
                                    st.session_state["selected_task_ids"].discard(task_id)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Cancel failed: {e}")
                    with col_b:
                        if t.get("video_url"):
                            st.video(t["video_url"])
                        elif task_status == "succeeded":
                            st.warning("Video URL expired or unavailable.")
            with checkbox_col:
                if is_cancellable:
                    checked = st.checkbox(
                        "select",
                        value=is_selected,
                        key=f"chk_{task_id}",
                        label_visibility="collapsed",
                    )
                    if checked and task_id not in st.session_state["selected_task_ids"]:
                        st.session_state["selected_task_ids"].add(task_id)
                    elif not checked and task_id in st.session_state["selected_task_ids"]:
                        st.session_state["selected_task_ids"].discard(task_id)


# ── Yandex Disk tab ───────────────────────────────────────────────────────────
with tab_yadisk:
    st.markdown("Загрузите директорию с видео на Яндекс Диск.")

    if not YADISK_TOKEN:
        st.error("YANDEX_DISK_TOKEN не задан в .env")
    else:
        output_dirs = _list_output_dirs()
        if not output_dirs:
            st.info("Нет директорий с .mp4 файлами в output/")
        else:
            selected_dir = st.selectbox(
                "Директория в output/",
                output_dirs,
                help="Выберите директорию, файлы из которой загрузить на Яндекс Диск",
            )

            # Yandex Disk folder browser
            if "yd_path" not in st.session_state:
                st.session_state["yd_path"] = "disk:/"

            current_yd_path = st.session_state["yd_path"]
            st.caption(f"Текущая папка: `{current_yd_path}`")

            col_nav1, col_nav2 = st.columns([1, 4])
            with col_nav1:
                if st.button("⬆ Вверх", disabled=current_yd_path == "disk:/"):
                    parent = current_yd_path.rsplit("/", 1)[0]
                    st.session_state["yd_path"] = parent if parent != "disk:" else "disk:/"
                    st.rerun()

            subdirs = _yadisk_list_dirs(current_yd_path)
            if subdirs:
                chosen_subdir = st.selectbox("Папки на Яндекс Диске", ["— выбрать —"] + subdirs)
                col_open, col_select = st.columns(2)
                with col_open:
                    if st.button("Открыть", disabled=chosen_subdir == "— выбрать —"):
                        st.session_state["yd_path"] = f"{current_yd_path.rstrip('/')}/{chosen_subdir}"
                        st.rerun()
                with col_select:
                    if st.button("Выбрать эту папку", disabled=chosen_subdir == "— выбрать —"):
                        st.session_state["yd_dest"] = f"{current_yd_path.rstrip('/')}/{chosen_subdir}"
            else:
                st.info("Подпапок нет")

            new_folder = st.text_input("Или введите/создайте новую папку", placeholder="название папки")
            if st.button("Создать и выбрать", disabled=not new_folder.strip()):
                new_path = f"{current_yd_path.rstrip('/')}/{new_folder.strip()}"
                _yadisk_create_folder(new_path)
                st.session_state["yd_dest"] = new_path

            yadisk_dest = st.session_state.get("yd_dest", current_yd_path)
            st.success(f"Загрузить в: `{yadisk_dest}`")

            local_dir = OUTPUT_DIR / selected_dir
            mp4_files = sorted(local_dir.glob("*.mp4")) if local_dir.exists() else []
            st.caption(f"Файлов для загрузки: {len(mp4_files)}")

            if mp4_files:
                with st.expander("Список файлов"):
                    for f in mp4_files:
                        size_mb = f.stat().st_size / 1024 / 1024
                        st.text(f"{f.name}  ({size_mb:.1f} MB)")

            # folder name = last component of selected_dir (e.g. "SeeDance_rome_720p_to_4k")
            dir_label = Path(selected_dir).name or selected_dir.replace("/", "_")
            zip_name = dir_label + ".zip"
            remote_folder = f"{yadisk_dest}/{dir_label}"
            remote_zip = f"{remote_folder}/{zip_name}"
            st.caption(f"Путь на диске: `{remote_zip}`")

            if st.button("Загрузить на Яндекс Диск", type="primary", disabled=not mp4_files):
                status_text = st.empty()
                progress_bar = st.progress(0)

                status_text.info(f"Упаковываю {len(mp4_files)} файлов в архив...")
                zip_bytes = _make_zip(mp4_files)
                zip_mb = len(zip_bytes) / 1024 / 1024
                progress_bar.progress(0.1)

                status_text.info(f"Создаю папку {remote_folder}...")
                _yadisk_create_folder(remote_folder)
                progress_bar.progress(0.15)

                status_text.info(f"Загружаю {zip_name} ({zip_mb:.1f} MB)...")
                ok, msg = _yadisk_upload_bytes(zip_bytes, remote_zip)
                progress_bar.progress(1.0)

                if ok:
                    status_text.success(f"Загружено: {remote_zip} ({zip_mb:.1f} MB)")
                else:
                    status_text.error(f"Ошибка: {msg}")
