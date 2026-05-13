"""Streamlit UI — временный фронтенд для seedance-api.

Заменить на Next.js / SvelteKit когда понадобится нормальный UX.
"""
from __future__ import annotations

import base64
import time

import httpx
import streamlit as st

API_BASE = "http://api:8000"
POLL_INTERVAL = 3  # seconds between status checks


# ── helpers ──────────────────────────────────────────────────────────────────

def _to_data_uri(file_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(file_bytes).decode()
    return f"data:{mime};base64,{b64}"


def _submit(prompt: str, image_bytes: bytes | None, image_mime: str | None,
            ratio: str, resolution: str, duration: int | None,
            generate_audio: bool, seed: int | None = None) -> dict:
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


# ── UI ────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="HistoryDoc SeeDance", layout="wide")
st.title("HistoryDoc SeeDance")

tab_generate, tab_batch, tab_history = st.tabs(["Generate", "Batch", "History"])

# ── Generate tab ──────────────────────────────────────────────────────────────
with tab_generate:
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
                    resp = httpx.post(
                        f"{API_BASE}/generations/batch",
                        files={"file": (xlsx_file.name, xlsx_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                        data={
                            "ratio": b_ratio,
                            "resolution": b_resolution,
                            "duration": str(b_duration),
                            "generate_audio": str(b_audio).lower(),
                        },
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
    if st.button("Refresh"):
        st.rerun()

    try:
        tasks = _list_tasks()
    except Exception as e:
        st.error(f"Failed to load tasks: {e}")
        tasks = []

    if not tasks:
        st.info("No tasks yet.")
    else:
        for t in reversed(tasks):
            status = t.get("status", "?")
            color = {"succeeded": "green", "failed": "red", "running": "orange", "queued": "gray", "expired": "red"}.get(status, "gray")
            with st.expander(f":{color}[{status.upper()}] `{t['id'][:8]}...` — {t.get('created_at', '')[:19]}"):
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
                with col_b:
                    if t.get("video_url"):
                        st.video(t["video_url"])
                    elif status == "succeeded":
                        st.warning("Video URL expired or unavailable.")
