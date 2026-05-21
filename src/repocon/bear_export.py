"""Export repocon Markdown reports to Bear.app."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from repocon.analyzer import INDEX_NOTE_TITLE

BEAR_NOTE_DELAY_S = 0.3
BEAR_REGISTRY_NAME = ".repocon-bear.json"
BearExportMode = Literal["upsert", "create", "update"]


@dataclass
class BearExportResult:
    created: int = 0
    updated: int = 0

    @property
    def total(self) -> int:
        return self.created + self.updated


def get_bear_tags() -> list[str]:
    import os

    raw = os.environ.get("REPOCON_BEAR_TAGS") or os.environ.get(
        "INFOMUX_BEAR_TAGS",
        "repocon,projects",
    )
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def _bear_backend():
    try:
        from infomux import bear as backend

        return backend
    except ImportError:
        return None


def create_bear_note(
    title: str,
    text: str,
    tags: list[str],
    *,
    open_note: bool = False,
) -> None:
    backend = _bear_backend()
    if backend is not None:
        backend.create_note(title, text, tags, open_note=open_note)
        return
    _create_bear_note_local(title, text, tags, open_note=open_note)


def replace_bear_note(
    title: str,
    text: str,
    tags: list[str],
    *,
    open_note: bool = False,
) -> None:
    backend = _bear_backend()
    if backend is not None and hasattr(backend, "replace_note"):
        backend.replace_note(title, text, tags, open_note=open_note)
        return
    _replace_bear_note_local(title, text, tags, open_note=open_note)


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
    _run_open(url)


def _replace_bear_note_local(
    title: str,
    text: str,
    tags: list[str],
    *,
    open_note: bool = False,
) -> None:
    import urllib.parse

    params = {
        "title": title,
        "text": text,
        "mode": "replace",
        "tags": ",".join(tags),
        "exclude_trashed": "yes",
        "open_note": "yes" if open_note else "no",
    }
    url = "bear://x-callback-url/add-text?" + urllib.parse.urlencode(
        params,
        quote_via=urllib.parse.quote,
    )
    _run_open(url)


def _run_open(url: str) -> None:
    import subprocess

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


def registry_path(output_dir: Path) -> Path:
    return output_dir / BEAR_REGISTRY_NAME


def load_bear_registry(output_dir: Path) -> set[str]:
    path = registry_path(output_dir)
    if not path.is_file():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    titles = payload.get("titles")
    if not isinstance(titles, list):
        return set()
    return {str(title) for title in titles}


def save_bear_registry(output_dir: Path, titles: set[str]) -> None:
    path = registry_path(output_dir)
    path.write_text(
        json.dumps({"titles": sorted(titles)}, indent=2) + "\n",
        encoding="utf-8",
    )


def sync_bear_note(
    title: str,
    text: str,
    tags: list[str],
    *,
    mode: BearExportMode,
    known_titles: set[str],
    open_note: bool = False,
) -> Literal["created", "updated"]:
    if mode == "update" or (mode == "upsert" and title in known_titles):
        replace_bear_note(title, text, tags, open_note=open_note)
        known_titles.add(title)
        return "updated"

    create_bear_note(title, text, tags, open_note=open_note)
    known_titles.add(title)
    return "created"


def export_reports_to_bear(
    output_dir: Path,
    *,
    open_index: bool = True,
    mode: BearExportMode = "upsert",
) -> BearExportResult:
    if sys.platform != "darwin":
        raise RuntimeError("Bear export only works on macOS with Bear.app installed.")

    projects_dir = output_dir / "projects"
    index_path = output_dir / "index.md"
    if not projects_dir.is_dir():
        raise RuntimeError(f"No projects/ directory under {output_dir}")

    tags = get_bear_tags()
    known_titles = load_bear_registry(output_dir)
    result = BearExportResult()

    for brief_path in sorted(projects_dir.glob("*.md")):
        title = note_title_from_markdown(brief_path)
        body = brief_path.read_text(encoding="utf-8")
        action = sync_bear_note(
            title,
            body,
            tags,
            mode=mode,
            known_titles=known_titles,
            open_note=False,
        )
        known_titles.add(title)
        if action == "created":
            result.created += 1
        else:
            result.updated += 1
        time.sleep(BEAR_NOTE_DELAY_S)

    if index_path.is_file():
        action = sync_bear_note(
            INDEX_NOTE_TITLE,
            index_path.read_text(encoding="utf-8"),
            tags,
            mode=mode,
            known_titles=known_titles,
            open_note=open_index,
        )
        known_titles.add(INDEX_NOTE_TITLE)
        if action == "created":
            result.created += 1
        else:
            result.updated += 1

    save_bear_registry(output_dir, known_titles)
    return result
