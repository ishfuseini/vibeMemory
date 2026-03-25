"""vibeMemory dashboard — NiceGUI app.

Calls memory.py functions directly via run.io_bound() to avoid blocking
the event loop. No REST API layer needed.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

import memory as mem
from nicegui import app, run, ui

DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD")

_STORAGE_SECRET = os.getenv("STORAGE_SECRET")
if not _STORAGE_SECRET:
    raise RuntimeError("STORAGE_SECRET environment variable must be set")

# ---------------------------------------------------------------------------
# Theme — inject brand CSS classes + Inter font into every page
# NiceGUI pre-bundles Tailwind; no CDN tailwind global is available.
# We generate utility classes from the theme values directly.
# ---------------------------------------------------------------------------

ui.add_head_html(
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500&display=swap" rel="stylesheet">',
    shared=True,
)
ui.add_head_html(
    """<style>
/* ── Font ───────────────────────────────────────────────── */
body, .nicegui-content { font-family: 'Inter', sans-serif; }

/* ── Brand colors ───────────────────────────────────────── */
:root {
  --color-brand-primary: rgb(147 51 234);
  --color-brand-50:  rgb(250 245 255);
  --color-brand-100: rgb(243 232 255);
  --color-brand-500: rgb(168 85 247);
  --color-brand-600: rgb(147 51 234);
  --color-brand-700: rgb(126 34 206);
  --color-default-font: rgb(23 23 23);
  --color-subtext-color: rgb(115 115 115);
  --color-neutral-border: rgb(229 229 229);
  --color-default-background: rgb(255 255 255);
}

/* ── Color utilities ─────────────────────────────────────── */
.text-brand-primary  { color: var(--color-brand-primary) !important; }
.text-default-font   { color: var(--color-default-font)  !important; }
.text-subtext-color  { color: var(--color-subtext-color) !important; }
.bg-brand-primary    { background-color: var(--color-brand-primary) !important; }
.bg-brand-50         { background-color: var(--color-brand-50)      !important; }
.border-neutral-border { border-color: var(--color-neutral-border)  !important; }

/* ── Typography scale ────────────────────────────────────── */
.text-caption        { font-size: 12px; line-height: 16px; font-weight: 400; }
.text-caption-bold   { font-size: 12px; line-height: 16px; font-weight: 500; }
.text-body           { font-size: 14px; line-height: 20px; font-weight: 400; }
.text-body-bold      { font-size: 14px; line-height: 20px; font-weight: 500; }
.text-heading-3      { font-size: 16px; line-height: 20px; font-weight: 500; }
.text-heading-2      { font-size: 20px; line-height: 24px; font-weight: 500; }
.text-heading-1      { font-size: 30px; line-height: 36px; font-weight: 500; }
.text-monospace-body { font-size: 14px; line-height: 20px; font-family: monospace; }
</style>""",
    shared=True,
)

# ---------------------------------------------------------------------------
# Startup: initialise Qdrant + embedder once
# ---------------------------------------------------------------------------

async def _startup() -> None:
    import logging
    try:
        await run.io_bound(mem.init)
    except Exception as exc:
        logging.getLogger(__name__).error("Memory init failed: %s", exc)

app.on_startup(_startup)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bucket_scores(memories: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
    """Bin similarity scores into 10 equal-width buckets for the histogram."""
    bins = [0] * 10
    for m in memories:
        score = m.get("score")
        if score is not None:
            idx = min(int(score * 10), 9)
            bins[idx] += 1
    labels = [f"{i / 10:.1f}–{(i + 1) / 10:.1f}" for i in range(10)]
    return labels, bins


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        from datetime import datetime

        return datetime.fromisoformat(iso).strftime("%b %-d")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


@ui.page("/login")
def login_page() -> None:
    async def try_login() -> None:
        if not DASHBOARD_PASSWORD or pwd_input.value == DASHBOARD_PASSWORD:
            app.storage.user["authenticated"] = True
            ui.navigate.to("/")
        else:
            await asyncio.sleep(1)  # serialise brute-force attempts
            ui.notify("Wrong password", type="negative")

    ui.colors(primary="rgb(147 51 234)")
    with ui.card().classes("absolute-center"):
        ui.label("vibeMemory").classes("text-xl font-bold text-brand-primary mb-4")
        pwd_input = ui.input("Password", password=True, password_toggle_button=True)
        pwd_input.on("keydown.enter", try_login)
        ui.button("Sign in", on_click=try_login).props("color=primary unelevated")


@ui.page("/")
async def main() -> None:
    if DASHBOARD_PASSWORD and not app.storage.user.get("authenticated"):
        ui.navigate.to("/login")
        return

    # ── Per-session state ──────────────────────────────────────────────────
    state: dict[str, Any] = {
        "scope": "default",
        "mode": "browse",
        "memories": [],
        "loading": False,
        "status": "live",
    }

    # ── Forward declarations (filled in layout section below) ─────────────
    status_badge: ui.badge
    count_label: ui.label
    mode_label: ui.label
    scope_label: ui.label
    chart: ui.echart
    chart_card: ui.card
    cards_col: ui.column
    spinner: ui.spinner
    empty_label: ui.label
    search_input: ui.input
    scope_select: ui.select

    # ── Event handlers ─────────────────────────────────────────────────────

    async def _set_loading(on: bool) -> None:
        state["loading"] = on
        spinner.set_visibility(on)
        cards_col.set_visibility(not on)

    def _set_status(s: str) -> None:
        state["status"] = s
        if s == "error":
            status_badge.props("color=negative")
            status_badge.set_text("error")
        else:
            status_badge.props("color=positive")
            status_badge.set_text("live")

    def _update_stats() -> None:
        count = len(state["memories"])
        count_label.set_text(str(count))
        mode_label.set_text(state["mode"])
        scope_label.set_text(state["scope"])

    def _render_chart() -> None:
        if state["mode"] != "search" or not state["memories"]:
            chart_card.set_visibility(False)
            return
        labels, bins = _bucket_scores(state["memories"])
        chart.options["xAxis"]["data"] = labels
        chart.options["series"][0]["data"] = bins
        chart.update()
        chart_card.set_visibility(True)

    @ui.refreshable
    def render_cards() -> None:
        memories = state["memories"]
        empty_label.set_visibility(len(memories) == 0 and not state["loading"])
        for m in memories:
            with ui.card().classes("w-full"):
                with ui.row().classes("w-full items-start justify-between gap-3"):
                    ui.label(m.get("text", "")).classes("text-body text-default-font leading-relaxed flex-1")

                    async def on_delete(mid: str = m["id"]) -> None:
                        try:
                            await run.io_bound(mem.forget, mid)
                            state["memories"] = [x for x in state["memories"] if x["id"] != mid]
                            render_cards.refresh()
                            _update_stats()
                            _render_chart()
                            ui.notify("Memory deleted", type="positive")
                            # Refresh scope list — scope may have disappeared
                            new_scopes = await run.io_bound(mem.list_scopes) or ["default"]
                            scope_select.options = new_scopes
                        except Exception:
                            ui.notify("Delete failed", type="negative")

                    ui.button(icon="close", on_click=on_delete).props(
                        "flat dense color=negative size=sm"
                    )
                with ui.row().classes("gap-2 items-center flex-wrap mt-1"):
                    if state["mode"] == "search" and m.get("score") is not None:
                        ui.badge(f"{m['score']:.3f}").props("color=accent")
                    for tag in m.get("tags") or []:
                        ui.badge(tag).props("outline dense")
                    if m.get("source"):
                        ui.label(m["source"]).classes("text-monospace-body text-subtext-color font-mono")
                    ui.space()
                    if m.get("created_at"):
                        ui.label(_fmt_date(m["created_at"])).classes("text-caption text-subtext-color")

    async def browse_all() -> None:
        state["mode"] = "browse"
        await _set_loading(True)
        try:
            state["memories"] = await run.io_bound(
                mem.list_memories, scope=state["scope"], limit=50
            )
            _set_status("live")
        except Exception:
            _set_status("error")
        finally:
            render_cards.refresh()
            _update_stats()
            _render_chart()
            await _set_loading(False)

    async def do_search() -> None:
        query = search_input.value.strip()
        if not query:
            await browse_all()
            return
        state["mode"] = "search"
        await _set_loading(True)
        try:
            state["memories"] = await run.io_bound(
                mem.recall, query, scope=state["scope"], limit=10
            )
            _set_status("live")
        except Exception:
            _set_status("error")
        finally:
            render_cards.refresh()
            _update_stats()
            _render_chart()
            await _set_loading(False)

    async def on_scope_change(e: Any) -> None:
        state["scope"] = e.value
        search_input.value = ""
        await browse_all()

    # ── Layout ─────────────────────────────────────────────────────────────

    ui.colors(primary="rgb(147 51 234)")  # brand-600

    # Header
    with ui.header().classes("items-center gap-4 px-6 bg-white shadow-sm"):
        ui.label("vibeMemory").classes("text-xl font-bold text-brand-primary")
        ui.space()

        initial_scopes = await run.io_bound(mem.list_scopes) or ["default"]
        state["scope"] = initial_scopes[0]

        scope_select = (
            ui.select(initial_scopes, value=initial_scopes[0], on_change=on_scope_change)
            .classes("w-36")
            .props("dense outlined")
        )
        search_input = (
            ui.input(placeholder="Semantic search…")
            .classes("w-64")
            .props("dense outlined")
            .on("keydown.enter", do_search)
        )
        ui.button("Search", on_click=do_search).props("flat")
        ui.button("Browse All", on_click=browse_all).props("flat")

        ui.space()
        status_badge = ui.badge("live").props("color=positive rounded")

    # Main two-column layout
    with ui.row().classes("w-full max-w-6xl mx-auto px-6 py-8 gap-6 items-start"):

        # Left — memory cards (2/3)
        with ui.column().classes("flex-1 gap-3 min-w-0"):
            with ui.row().classes("items-center justify-between w-full"):
                ui.label("Memories").classes("text-heading-3 font-medium text-default-font")

            spinner = ui.spinner("dots", size="lg").classes("self-center py-8")
            spinner.set_visibility(False)

            empty_label = ui.label("No memories yet in this scope.").classes(
                "text-center text-subtext-color py-16 w-full text-body"
            )
            empty_label.set_visibility(False)

            cards_col = ui.column().classes("w-full gap-3")
            with cards_col:
                render_cards()

        # Right — sidebar (1/3)
        with ui.column().classes("w-64 gap-4 shrink-0"):

            # Score histogram
            chart_card = ui.card().classes("w-full")
            with chart_card:
                ui.label("Score Distribution").classes("text-heading-3 font-medium text-default-font mb-2")
                chart = ui.echart(
                    {
                        "tooltip": {"trigger": "axis"},
                        "grid": {"top": 8, "right": 8, "bottom": 40, "left": 32},
                        "xAxis": {
                            "type": "category",
                            "data": [],
                            "axisLabel": {"fontSize": 9, "rotate": 45},
                        },
                        "yAxis": {"type": "value", "minInterval": 1},
                        "series": [
                            {
                                "type": "bar",
                                "data": [],
                                "itemStyle": {"color": "rgb(147 51 234)"},
                                "barMaxWidth": 24,
                            }
                        ],
                    }
                ).classes("h-48 w-full")
            chart_card.set_visibility(False)

            # Stats
            with ui.card().classes("w-full"):
                ui.label("Stats").classes("text-heading-3 font-medium text-default-font mb-2")
                with ui.grid(columns=2).classes("w-full gap-y-1"):
                    ui.label("Scope").classes("text-body text-subtext-color")
                    scope_label = ui.label(state["scope"]).classes("text-body font-mono font-medium text-default-font truncate")
                    ui.label("Showing").classes("text-body text-subtext-color")
                    count_label = ui.label("0").classes("text-body font-medium text-default-font")
                    ui.label("Mode").classes("text-body text-subtext-color")
                    mode_label = ui.label("browse").classes("text-body font-medium text-default-font")

    # Initial load
    await browse_all()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        port=8080,
        title="vibeMemory",
        favicon="🧠",
        dark=False,
        storage_secret=_STORAGE_SECRET,
    )
