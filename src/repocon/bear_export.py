"""Export repocon Markdown reports to Bear.app."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from repocon.analyzer import INDEX_NOTE_TITLE

BEAR_NOTE_DELAY_S = 0.3


def get_bear_tags() -> list[str]:
    import os

    raw = os.environ.get("REPOCON_BEAR_TAGS") or os.environ.get(
        "INFOMUX_BEAR_TAGS",
        "repocon,projects",
    )
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def create_bear_note(
    title: str,
    text: str,
    tags: list[str],
    *,
    open_note: bool = False,
) -> None:
    try:
        from infomux.bear import create_note

        create_note(title, text, tags, open_note=open_note)
        return
    except ImportError:
        pass

    _create_bear_note_local(title, text, tags, open_note=open_note)


def _create_bear_note_local(
    title: str,
    text: str,
    tags: list[str],
    *,
    open_note: bool = False,
) -> None:
    import subprocess
    import urllib.parse

    params = {
        "title": title,
        "text": text,
        "tags": ",".join(tags),
        "open_note": "yes" if open_note else "no",
    }
    url = "bear://x-callback-url/create?" + urllib.parse.urlencode(
        params,
        quote_via=urllib.parse.quote,
    )
    try:
        subprocess.run(["open", url], check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Failed to open Bear: {exc}") from exc
    except FileNotFoundError as exc:
        raise RuntimeError(
            "macOS 'open' command not found. Bear export requires macOS."
        ) from exc


def note_title_from_markdown(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return path.stem


def export_reports_to_bear(output_dir: Path, *, open_index: bool = True) -> int:
    if sys.platform != "darwin":
        raise RuntimeError("Bear export only works on macOS with Bear.app installed.")

    projects_dir = output_dir / "projects"
    index_path = output_dir / "index.md"
    if not projects_dir.is_dir():
        raise RuntimeError(f"No projects/ directory under {output_dir}")

    tags = get_bear_tags()
    notes_created = 0

    for brief_path in sorted(projects_dir.glob("*.md")):
        title = note_title_from_markdown(brief_path)
        body = brief_path.read_text(encoding="utf-8")
        create_bear_note(title, body, tags, open_note=False)
        notes_created += 1
        time.sleep(BEAR_NOTE_DELAY_S)

    if index_path.is_file():
        create_bear_note(
            INDEX_NOTE_TITLE,
            index_path.read_text(encoding="utf-8"),
            tags,
            open_note=open_index,
        )
        notes_created += 1

    return notes_created
