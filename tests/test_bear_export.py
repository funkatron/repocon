from pathlib import Path
from unittest.mock import patch

import pytest

from repocon.analyzer import (
    GitSummary,
    ProjectReport,
    StructureSignals,
    detect_project_families,
    render_index_markdown,
)
from repocon.bear_export import (
    export_reports_to_bear,
    load_bear_registry,
    note_title_from_markdown,
    registry_path,
    save_bear_registry,
    sync_bear_note,
)


def _report(name: str) -> ProjectReport:
    return ProjectReport(
        name=name,
        path=f"/src/{name}",
        stack=["Python"],
        top_level_folders=["src"],
        one_liner=f"{name} one-liner",
        plain_english_summary="plain",
        technical_summary="technical",
        initial_intent="intent",
        git=GitSummary(tracked=False),
        current_state="Healthy",
        health_signals=[],
        risks=[],
        recommendations=[],
        priority_recommendation="priority",
        monetization_potential="low",
        similarity_tokens=[],
        structure=StructureSignals(),
    )


def test_detect_project_families_groups_prefix_clusters() -> None:
    reports = [
        _report("draw-things"),
        _report("draw-things-grpcservercli-installer"),
        _report("dts-utils"),
        _report("now-playing"),
    ]
    families = detect_project_families(reports)
    labels = {family.label for family in families}
    assert "draw-things" in labels
    draw_family = next(family for family in families if family.label == "draw-things")
    assert "draw-things-grpcservercli-installer" in draw_family.members


def test_render_index_includes_families_section() -> None:
    reports = [_report("draw-things"), _report("draw-things-batch")]
    index_md = render_index_markdown(
        reports,
        Path("/src"),
        Path("/tmp/reports"),
        families=detect_project_families(reports),
    )
    assert "## Families" in index_md
    assert "### draw-things" in index_md
    assert "| Run | Tests |" in index_md


def test_note_title_from_markdown_uses_heading(tmp_path: Path) -> None:
    path = tmp_path / "example.md"
    path.write_text("# now-playing\n\nBody\n", encoding="utf-8")
    assert note_title_from_markdown(path) == "now-playing"


def test_sync_bear_note_upsert_updates_known_title() -> None:
    known = {"repocon"}
    with patch("repocon.bear_export.replace_bear_note") as mock_replace:
        action = sync_bear_note(
            "repocon",
            "body",
            ["repocon"],
            mode="upsert",
            known_titles=known,
        )
    assert action == "updated"
    mock_replace.assert_called_once()


def test_sync_bear_note_upsert_creates_unknown_title() -> None:
    known: set[str] = set()
    with patch("repocon.bear_export.create_bear_note") as mock_create:
        action = sync_bear_note(
            "repocon",
            "body",
            ["repocon"],
            mode="upsert",
            known_titles=known,
        )
    assert action == "created"
    mock_create.assert_called_once()
    assert "repocon" in known


@patch("repocon.bear_export.sync_bear_note")
@patch("repocon.bear_export.time.sleep")
@patch("sys.platform", "darwin")
def test_export_reports_to_bear_upsert_writes_registry(
    _sleep: object,
    mock_sync: object,
    tmp_path: Path,
) -> None:
    projects = tmp_path / "projects"
    projects.mkdir()
    (projects / "repocon.md").write_text("# repocon\n\nBrief\n", encoding="utf-8")
    (tmp_path / "index.md").write_text("# Project Briefs\n", encoding="utf-8")
    mock_sync.return_value = "created"

    result = export_reports_to_bear(tmp_path, open_index=True, mode="upsert")

    assert result.total == 2
    assert result.created == 2
    assert load_bear_registry(tmp_path) == {"Project Briefs", "repocon"}
    assert registry_path(tmp_path).is_file()


@patch("repocon.bear_export.replace_bear_note")
@patch("repocon.bear_export.create_bear_note")
@patch("repocon.bear_export.time.sleep")
@patch("sys.platform", "darwin")
def test_export_reports_to_bear_second_run_updates(
    _sleep: object,
    mock_create: object,
    mock_replace: object,
    tmp_path: Path,
) -> None:
    projects = tmp_path / "projects"
    projects.mkdir()
    (projects / "repocon.md").write_text("# repocon\n\nBrief\n", encoding="utf-8")
    (tmp_path / "index.md").write_text("# Project Briefs\n", encoding="utf-8")
    save_bear_registry(tmp_path, {"repocon", "Project Briefs"})

    result = export_reports_to_bear(tmp_path, open_index=False, mode="upsert")

    assert result.total == 2
    assert result.updated == 2
    assert result.created == 0
    mock_replace.assert_called()
    mock_create.assert_not_called()


@patch("sys.platform", "linux")
def test_export_reports_to_bear_requires_macos() -> None:
    with pytest.raises(RuntimeError, match="macOS"):
        export_reports_to_bear(Path("/tmp/reports"))
